"""End-to-End GridResilience Incident Lifecycle Pipeline.

Integrates:
Contingency -> Predictive GCN -> PPO Mitigation -> Cascade -> Recovery -> Restored Grid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from src.cascade import find_overloaded_lines, _load_outcome, _load_based_status
from src.gnn_training import load_checkpoint, load_dataset
from src.grid_loader import load_ieee14
from src.recovery import GridRecoveryEnv, GreedyRecoveryController, RecoveryConfig, check_recovery_safety
from src.rl_controllers import PPOController
from src.rl_env import GridMitigationEnv, RewardConfig, load_gcn_predictor, fast_power_flow, _clone_ieee14, ACTION_NAMES


class EndToEndPipeline:
    """Coordinates the full mitigation and post-cascade recovery lifecycle."""

    def __init__(
        self,
        gcn_model_path: str | Path = "outputs/predictive_v2/models/best_gcn.pt",
        gcn_data_dir: str | Path = "outputs/predictive_v2",
        ppo_model_path: str | Path = "outputs/models/ppo_predictive.zip",
    ) -> None:
        self.gcn_data_dir = Path(gcn_data_dir)
        self.gcn_model_path = Path(gcn_model_path)
        self.ppo_model_path = Path(ppo_model_path)

        # 1. Load Predictive-v2 GCN
        self.gcn_model, self.gcn_stats = load_gcn_predictor(self.gcn_model_path, self.gcn_data_dir)

        # 2. Load trained PPO Predictive Mitigation policy
        self.ppo_sb3 = PPO.load(str(self.ppo_model_path))
        self.ppo_controller = PPOController(self.ppo_sb3)

        # 3. Greedy Recovery Controller
        self.recovery_controller = GreedyRecoveryController()

    def run_incident(
        self,
        scenario: dict[str, Any],
        enable_mitigation: bool = True,
        enable_recovery: bool = True,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Execute full pipeline for a single scenario."""
        audit_log: list[dict[str, Any]] = []

        # Step 1: Initialize mitigation environment
        env = GridMitigationEnv(
            gcn_model=self.gcn_model,
            gcn_stats=self.gcn_stats,
            use_gcn_predictions=True,
            reward_config=RewardConfig(),
            seed=seed,
        )
        obs, reset_info = env.reset(options={"scenario": scenario})
        initial_load_mw = env.initial_load_mw

        # Extract target load by bus for restoration reference
        target_load_by_bus = {
            int(b): float(env.net.load.loc[env.net.load["bus"] == b, "p_mw"].sum())
            for b in env.net.bus.index
        }

        audit_log.append({
            "stage": "1_CONTINGENCY",
            "initial_outages": list(env.initial_outages),
            "initial_load_mw": initial_load_mw,
            "overloaded_lines_post_contingency": list(reset_info.get("overloaded_lines", [])),
            "gcn_risk_mean": reset_info.get("gcn_risk_mean", 0.0),
        })

        # Step 2: Mitigation Phase (PPO)
        done = False
        step_idx = 0
        mitigation_actions = []

        while not done:
            step_idx += 1
            if enable_mitigation:
                action, _ = self.ppo_controller.predict(obs, deterministic=True)
            else:
                action = 0  # Do nothing baseline

            action_name = ACTION_NAMES[action]
            mitigation_actions.append(action_name)
            obs, reward, terminated, truncated, step_info = env.step(action)
            done = terminated or truncated

            audit_log.append({
                "stage": f"2_MITIGATION_STEP_{step_idx}",
                "action": action_name,
                "reward": round(reward, 3),
                "failed_lines_count": step_info.get("failed_lines_count"),
                "newly_failed": step_info.get("newly_failed_lines", []),
                "load_served_percent": round(step_info.get("load_served_percent", 0.0), 2),
                "load_shed_mw": round(step_info.get("load_shed_mw", 0.0), 2),
                "final_status": step_info.get("final_status"),
                "done": done,
            })

        post_cascade_net = _clone_ieee14(env.net)
        post_cascade_status = step_info.get("final_status", "UNKNOWN")
        if post_cascade_status in ("NON_CONVERGED", "TOTAL_BLACKOUT"):
            post_cascade_served_mw = 0.0
        else:
            post_cascade_served_mw = (
                float(step_info.get("load_served_percent", 0.0) / 100.0 * initial_load_mw)
                if initial_load_mw > 0
                else 0.0
            )
        tripped_lines = list(env.failed_lines)

        audit_log.append({
            "stage": "3_CASCADE_RESULT",
            "tripped_lines": tripped_lines,
            "tripped_lines_count": len(tripped_lines),
            "served_load_mw": round(post_cascade_served_mw, 2),
            "load_served_percent": round(post_cascade_served_mw / initial_load_mw * 100.0 if initial_load_mw > 0 else 0.0, 2),
            "status": post_cascade_status,
        })

        # Step 3: Recovery Phase
        recovery_summary = {}
        if enable_recovery and post_cascade_net is not None:
            rec_env = GridRecoveryEnv(
                damaged_net=post_cascade_net,
                initial_target_load_mw=initial_load_mw,
                target_load_by_bus=target_load_by_bus,
                disconnected_lines=tripped_lines,
                initial_status=post_cascade_status,
                config=RecoveryConfig(),
            )
            recovery_summary = self.recovery_controller.run_recovery(rec_env)

            for step_record in rec_env.history:
                audit_log.append({
                    "stage": f"4_RECOVERY_STEP_{step_record['step']}",
                    "action": step_record["action"],
                    "committed": step_record["committed"],
                    "served_load_mw": round(step_record["served_load_mw"], 2),
                    "reason": step_record["reason"],
                })

            final_restored_mw = recovery_summary.get("final_served_mw", post_cascade_served_mw)
            final_status = recovery_summary.get("final_status", post_cascade_status)
        else:
            final_restored_mw = post_cascade_served_mw
            final_status = post_cascade_status

        mw_restored = max(0.0, final_restored_mw - post_cascade_served_mw)
        final_served_pct = (
            (final_restored_mw / initial_load_mw * 100.0) if initial_load_mw > 0 else 0.0
        )

        # Build detailed line failure predictions with risk ranking
        gcn_probs_list = [round(float(p), 4) for p in env.last_gcn_probs] if env.last_gcn_probs is not None else [0.0] * 15
        line_predictions = []
        for l in range(15):
            prob = gcn_probs_list[l] if l < len(gcn_probs_list) else 0.0
            fb = int(env.net.line.at[l, "from_bus"])
            tb = int(env.net.line.at[l, "to_bus"])
            line_predictions.append({
                "line_index": l,
                "from_bus": fb,
                "to_bus": tb,
                "probability": prob,
                "is_initial_outage": bool(l in env.initial_outages),
                "risk_level": "CRITICAL" if prob >= 0.50 else "HIGH" if prob >= 0.20 else "MODERATE" if prob >= 0.05 else "LOW",
            })
        sorted_by_prob = sorted(line_predictions, key=lambda x: x["probability"], reverse=True)
        for rank_i, item in enumerate(sorted_by_prob):
            item["risk_rank"] = rank_i + 1

        return {
            "scenario_id": scenario.get("scenario_id", "incident_0"),
            "initial_outages": env.initial_outages,
            "initial_load_mw": round(initial_load_mw, 2),
            "gcn_probabilities": gcn_probs_list,
            "line_predictions": line_predictions,
            "gcn_risk_mean": round(float(env.last_gcn_probs.mean()), 4) if env.last_gcn_probs is not None else 0.0,
            "post_cascade_served_mw": round(post_cascade_served_mw, 2),
            "post_cascade_status": post_cascade_status,
            "final_restored_mw": round(final_restored_mw, 2),
            "mw_restored": round(mw_restored, 2),
            "final_load_served_percent": round(final_served_pct, 2),
            "final_status": final_status,
            "failed_lines": tripped_lines,
            "reconnected_lines": recovery_summary.get("reconnected_lines", []),
            "reconnected_lines_count": recovery_summary.get("reconnected_lines_count", 0),
            "recovery_steps": recovery_summary.get("recovery_steps", 0),
            "mitigation_actions": mitigation_actions,
            "total_load_shed_mw": round(env.total_load_shed_mw, 2),
            "audit_log": audit_log,
        }
