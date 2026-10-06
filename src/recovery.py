"""Post-cascade power-grid recovery and service restoration for IEEE-14.

Phase 6 of GridResilience.
Provides a safety-constrained recovery environment and a greedy baseline
controller that restores tripped transmission lines and shed customer load.
"""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pandapower as pp
from pandapower.auxiliary import pandapowerNet
from pandapower.powerflow import LoadflowNotConverged

from src.cascade import find_overloaded_lines, _load_outcome, _load_based_status
from src.metrics import extract_grid_metrics, failed_grid_metrics
from src.rl_env import fast_power_flow, _clone_ieee14


@dataclass
class RecoveryConfig:
    """Configuration and safety bounds for post-cascade recovery."""

    voltage_min_pu: float = 0.90
    voltage_max_pu: float = 1.10
    overload_threshold: float = 100.0
    max_recovery_steps: int = 15
    load_restore_fraction: float = 0.50  # Restore 50% of shed load per action step


@dataclass
class SafetyCheckResult:
    """Outcome of safety check on candidate recovery action."""

    is_safe: bool
    converged: bool
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)
    served_load_mw: float = 0.0
    max_loading_percent: float = 0.0
    voltage_violations: list[int] = field(default_factory=list)
    overloaded_lines: list[int] = field(default_factory=list)


def check_recovery_safety(
    net: pandapowerNet,
    config: RecoveryConfig | None = None,
) -> SafetyCheckResult:
    """Run AC power flow and test whether network meets operational safety limits."""
    cfg = config or RecoveryConfig()
    
    # 1. AC power flow
    metrics = fast_power_flow(net)
    if not metrics.get("converged", False):
        return SafetyCheckResult(
            is_safe=False,
            converged=False,
            reason="Power flow diverged (non-convergent AC solution)",
            metrics=metrics,
        )

    # 2. Check bus voltages on in-service buses
    v_viol = []
    if "vm_pu" in net.res_bus:
        for b in net.bus.index:
            if bool(net.bus.at[b, "in_service"]):
                vm = float(net.res_bus.at[b, "vm_pu"])
                if np.isnan(vm) or vm < cfg.voltage_min_pu or vm > cfg.voltage_max_pu:
                    v_viol.append(int(b))

    if v_viol:
        return SafetyCheckResult(
            is_safe=False,
            converged=True,
            reason=f"Voltage violation on buses {v_viol} (bounds: [{cfg.voltage_min_pu}, {cfg.voltage_max_pu}])",
            metrics=metrics,
            voltage_violations=v_viol,
            served_load_mw=float(metrics.get("total_load_mw", 0.0)),
        )

    # 3. Check line overloads on in-service lines
    overloaded = find_overloaded_lines(metrics, cfg.overload_threshold)
    max_loading = float(metrics.get("max_line_loading_percent", 0.0))
    if overloaded:
        return SafetyCheckResult(
            is_safe=False,
            converged=True,
            reason=f"Thermal overloads on lines {overloaded} (max {max_loading:.1f}%)",
            metrics=metrics,
            overloaded_lines=overloaded,
            max_loading_percent=max_loading,
            served_load_mw=float(metrics.get("total_load_mw", 0.0)),
        )

    # 4. Check generator limits
    for g in net.gen.index:
        if bool(net.gen.at[g, "in_service"]) and "p_mw" in net.res_gen:
            p_gen = float(net.gen.at[g, "p_mw"])
            min_p = float(net.gen.at[g, "min_p_mw"]) if "min_p_mw" in net.gen else 0.0
            max_p = float(net.gen.at[g, "max_p_mw"]) if "max_p_mw" in net.gen else 999.0
            if p_gen < min_p - 1e-3 or p_gen > max_p + 1e-3:
                return SafetyCheckResult(
                    is_safe=False,
                    converged=True,
                    reason=f"Generator {g} power ({p_gen:.1f} MW) violates limits [{min_p}, {max_p}]",
                    metrics=metrics,
                    served_load_mw=float(metrics.get("total_load_mw", 0.0)),
                )

    served_mw = float(metrics.get("total_load_mw", 0.0))
    return SafetyCheckResult(
        is_safe=True,
        converged=True,
        reason="Network operates within all voltage, thermal, and generator limits",
        metrics=metrics,
        served_load_mw=served_mw,
        max_loading_percent=max_loading,
    )


class GridRecoveryEnv:
    """Environment managing post-cascade physical restoration and load recovery."""

    def __init__(
        self,
        damaged_net: pandapowerNet,
        initial_target_load_mw: float,
        target_load_by_bus: dict[int, float],
        disconnected_lines: list[int],
        initial_status: str | None = None,
        config: RecoveryConfig | None = None,
    ) -> None:
        self.config = config or RecoveryConfig()
        self.initial_target_load_mw = float(initial_target_load_mw)
        self.target_load_by_bus = dict(target_load_by_bus)
        self.disconnected_lines = list(set(disconnected_lines))
        self.initial_status = initial_status

        # Clone network to isolate recovery episode
        self.net = _clone_ieee14(damaged_net)

        # Baseline starting state
        base_safety = check_recovery_safety(self.net, self.config)
        self.initial_converged = bool(base_safety.converged)
        self.initial_served_load_mw = base_safety.served_load_mw if base_safety.converged else 0.0
        self.step_count = 0
        self.reconnected_lines: list[int] = []
        self.restored_load_mw = 0.0
        self.history: list[dict[str, Any]] = []

    def get_eligible_actions(self) -> list[dict[str, Any]]:
        """List currently eligible restoration actions that could safely be attempted."""
        actions: list[dict[str, Any]] = [{"action_type": "do_nothing", "label": "do_nothing"}]

        # 1. Line reconnection actions (for currently out-of-service lines that were tripped)
        for l in sorted(self.disconnected_lines):
            if l not in self.reconnected_lines and not bool(self.net.line.at[l, "in_service"]):
                actions.append({
                    "action_type": "reconnect_line",
                    "line_id": int(l),
                    "label": f"reconnect_line_{l}",
                })

        # 2. Load restoration actions (for load buses that have unserved/shed load)
        for b, target_p in self.target_load_by_bus.items():
            matches = self.net.load.index[self.net.load["bus"] == b]
            curr_p = float(self.net.load.loc[matches, "p_mw"].sum()) if not matches.empty else 0.0
            deficit = target_p - curr_p
            if deficit > 1.0:  # More than 1 MW shed remaining
                actions.append({
                    "action_type": "restore_load",
                    "bus": int(b),
                    "deficit_mw": float(deficit),
                    "label": f"restore_load_bus_{b}",
                })

        # 3. Generator redispatch headroom actions (+10 MW on gens 0..3 if below max)
        for g in range(len(self.net.gen)):
            curr_g = float(self.net.gen.at[g, "p_mw"])
            max_g = float(self.net.gen.at[g, "max_p_mw"]) if "max_p_mw" in self.net.gen else 100.0
            if curr_g + 5.0 <= max_g:
                actions.append({
                    "action_type": "gen_up",
                    "gen_id": int(g),
                    "delta_mw": 10.0,
                    "label": f"gen_{g}_up_10mw",
                })

        return actions

    def preview_action(self, action: dict[str, Any]) -> tuple[pandapowerNet, SafetyCheckResult]:
        """Apply candidate action on a trial copy and evaluate safety without committing."""
        trial_net = _clone_ieee14(self.net)
        atype = action.get("action_type", "do_nothing")

        if atype == "reconnect_line":
            lid = action["line_id"]
            trial_net.line.at[lid, "in_service"] = True

        elif atype == "restore_load":
            bus = action["bus"]
            restore_frac = self.config.load_restore_fraction
            matches = trial_net.load.index[trial_net.load["bus"] == bus]
            for idx in matches:
                curr = float(trial_net.load.at[idx, "p_mw"])
                target = self.target_load_by_bus.get(bus, curr)
                restore_amount = (target - curr) * restore_frac
                trial_net.load.at[idx, "p_mw"] = curr + restore_amount

        elif atype == "gen_up":
            gid = action["gen_id"]
            delta = float(action.get("delta_mw", 10.0))
            curr = float(trial_net.gen.at[gid, "p_mw"])
            max_p = float(trial_net.gen.at[gid, "max_p_mw"]) if "max_p_mw" in trial_net.gen else 100.0
            trial_net.gen.at[gid, "p_mw"] = min(max_p, curr + delta)

        safety = check_recovery_safety(trial_net, self.config)
        return trial_net, safety

    def step(self, action: dict[str, Any]) -> tuple[bool, SafetyCheckResult, dict[str, Any]]:
        """Execute a recovery action with strict safety verification."""
        self.step_count += 1
        atype = action.get("action_type", "do_nothing")
        label = action.get("label", "do_nothing")

        if atype == "do_nothing":
            safety = check_recovery_safety(self.net, self.config)
            info = {
                "step": self.step_count,
                "action": label,
                "committed": False,
                "reason": "Recovery terminated by do_nothing",
                "served_load_mw": safety.served_load_mw,
                "done": True,
            }
            self.history.append(info)
            return True, safety, info

        # Preview action on copied grid
        trial_net, safety = self.preview_action(action)

        if not safety.is_safe:
            # Action rejected due to violation
            current_safety = check_recovery_safety(self.net, self.config)
            info = {
                "step": self.step_count,
                "action": label,
                "committed": False,
                "reason": f"Rejected: {safety.reason}",
                "served_load_mw": current_safety.served_load_mw,
                "done": self.step_count >= self.config.max_recovery_steps,
            }
            self.history.append(info)
            return info["done"], current_safety, info

        # Safety check passed: verify invariant that served load does not decrease
        prev_served = self.current_served_load_mw()
        if safety.served_load_mw < prev_served - 1e-4:
            current_safety = check_recovery_safety(self.net, self.config)
            info = {
                "step": self.step_count,
                "action": label,
                "committed": False,
                "reason": f"Rejected: Action reduced served load from {prev_served:.2f} MW to {safety.served_load_mw:.2f} MW (invariant violation)",
                "served_load_mw": current_safety.served_load_mw,
                "done": self.step_count >= self.config.max_recovery_steps,
            }
            self.history.append(info)
            return info["done"], current_safety, info

        # Commit to network state
        self.net = trial_net

        if atype == "reconnect_line":
            lid = action["line_id"]
            if lid not in self.reconnected_lines:
                self.reconnected_lines.append(lid)

        new_served = safety.served_load_mw
        mw_gained = max(0.0, new_served - prev_served)
        self.restored_load_mw += mw_gained

        done = bool(
            self.step_count >= self.config.max_recovery_steps
            or (len(self.reconnected_lines) == len(self.disconnected_lines) and new_served >= self.initial_target_load_mw - 0.5)
        )

        info = {
            "step": self.step_count,
            "action": label,
            "committed": True,
            "reason": "Committed safely",
            "served_load_mw": new_served,
            "load_gained_mw": mw_gained,
            "reconnected_lines_count": len(self.reconnected_lines),
            "done": done,
        }
        self.history.append(info)
        return done, safety, info

    def current_served_load_mw(self) -> float:
        """Current actively served load from power flow."""
        res = check_recovery_safety(self.net, self.config)
        return res.served_load_mw if res.converged else 0.0

    def summary(self) -> dict[str, Any]:
        """Complete summary of the recovery episode."""
        safety = check_recovery_safety(self.net, self.config)
        final_served = safety.served_load_mw if safety.converged else 0.0
        restored_pct = (
            (final_served / self.initial_target_load_mw * 100.0)
            if self.initial_target_load_mw > 0
            else 0.0
        )
        lost_mw, _ = _load_outcome(self.initial_target_load_mw, final_served)
        if not safety.converged:
            final_status = "NON_CONVERGED"
        else:
            status = _load_based_status(self.initial_target_load_mw, final_served, restored_pct)
            if self.initial_status == "STABLE" and status not in ("NON_CONVERGED", "TOTAL_BLACKOUT"):
                final_status = "STABLE"
            else:
                final_status = status

        return {
            "recovery_steps": self.step_count,
            "initial_served_mw": round(self.initial_served_load_mw, 2),
            "final_served_mw": round(final_served, 2),
            "initial_target_load_mw": round(self.initial_target_load_mw, 2),
            "restored_mw": round(max(0.0, final_served - self.initial_served_load_mw), 2),
            "load_served_percent": round(restored_pct, 2),
            "reconnected_lines": sorted(self.reconnected_lines),
            "reconnected_lines_count": len(self.reconnected_lines),
            "remaining_disconnected_lines": sorted(
                l for l in self.disconnected_lines if l not in self.reconnected_lines
            ),
            "converged": bool(safety.converged),
            "is_safe": bool(safety.is_safe),
            "final_status": final_status,
            "success": bool(final_served > self.initial_served_load_mw or (self.initial_served_load_mw > 0 and safety.is_safe)),
        }


class GreedyRecoveryController:
    """Greedy heuristic controller that prioritizes safe line reconnection and load pickup."""

    def __init__(self, max_trials_per_step: int = 15) -> None:
        self.max_trials_per_step = max_trials_per_step

    def choose_action(self, env: GridRecoveryEnv) -> dict[str, Any]:
        """Select the safe action yielding maximum served load improvement."""
        eligible = env.get_eligible_actions()
        curr_served = env.current_served_load_mw()

        best_action = {"action_type": "do_nothing", "label": "do_nothing"}
        best_score = -1e9

        for act in eligible:
            if act["action_type"] == "do_nothing":
                continue

            trial_net, safety = env.preview_action(act)
            if not safety.is_safe:
                continue

            # Invariant: action must never reduce served load
            if safety.served_load_mw < curr_served - 1e-4:
                continue

            # Scoring:
            # Heavily reward net load pickup
            # Bonus for reconnecting transmission lines (improves redundancy)
            # Penalty for line loading approaching limit
            delta_load = safety.served_load_mw - curr_served
            line_bonus = 5.0 if act["action_type"] == "reconnect_line" else 0.0
            overload_penalty = (safety.max_loading_percent / 100.0) * 0.5
            score = delta_load + line_bonus - overload_penalty

            if score > best_score and score > 0:
                best_score = score
                best_action = act

        return best_action

    def run_recovery(self, env: GridRecoveryEnv) -> dict[str, Any]:
        """Execute greedy recovery loop until grid stabilizes or actions are exhausted."""
        done = False
        while not done:
            action = self.choose_action(env)
            done, safety, info = env.step(action)
            if action["action_type"] == "do_nothing":
                break
        return env.summary()
