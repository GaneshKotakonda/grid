"""Training and evaluation pipeline for Phase 5.5 PPO cascade mitigation.

Includes training curriculum, parallel SubprocVecEnv rollout, 300 held-out
scenario evaluation, action effectiveness logging, and paired bootstrap CIs.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv

from src.rl_controllers import DoNothingController, RuleMitigationController, PPOController
from src.rl_env import GridMitigationEnv, RewardConfig, load_gcn_predictor, ACTION_NAMES


class MetricsCallback(BaseCallback):
    """Callback recording episode returns and outcomes during training."""

    def __init__(self, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.history: list[dict[str, Any]] = []

    def _on_step(self) -> bool:
        # Check for completed episodes in infos
        for info in self.locals.get("infos", []):
            if "final_status" in info:
                self.history.append({
                    "step": self.num_timesteps,
                    "final_status": info.get("final_status"),
                    "failed_lines_count": info.get("failed_lines_count"),
                    "load_served_percent": info.get("load_served_percent"),
                    "load_shed_mw": info.get("load_shed_mw"),
                    "stable": info.get("stable"),
                })
        return True


def load_split_scenarios(
    metadata_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract train and test scenario specifications from saved metadata."""
    df = pd.read_csv(metadata_path)
    train_scenarios = (
        df.loc[df["split"] == "train"]
        .groupby("scenario_id")
        .first()
        .reset_index()
        .to_dict(orient="records")
    )
    test_scenarios = (
        df.loc[df["split"] == "test"]
        .groupby("scenario_id")
        .first()
        .reset_index()
        .to_dict(orient="records")
    )
    return train_scenarios, test_scenarios


def generate_curriculum_scenarios(
    train_scenarios: list[dict[str, Any]],
    total_count: int = 1500,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate a balanced curriculum with moderate, high-stress, and extreme scenarios."""
    rng = np.random.default_rng(seed)
    scenarios: list[dict[str, Any]] = []

    # 1. Moderate scenarios (35%): single initial outage, manageable load scale, higher capacity
    # These scenarios CAN be saved from cascading failure by proactive mitigation.
    mod_count = int(total_count * 0.35)
    for i in range(mod_count):
        outage = int(rng.integers(0, 15))
        scenarios.append({
            "scenario_id": f"curr_mod_{i}",
            "stress_category": "moderate",
            "load_scale": float(rng.uniform(0.95, 1.15)),
            "generation_scale": float(rng.uniform(0.95, 1.05)),
            "capacity_scale": float(rng.uniform(0.018, 0.035)),
            "initial_outages": [outage],
        })

    # 2. High-stress scenarios (35%): 1 or 2 outages, moderate capacity limit
    high_count = int(total_count * 0.35)
    for i in range(high_count):
        k = 1 if rng.random() > 0.4 else 2
        outages = sorted(int(x) for x in rng.choice(15, size=k, replace=False))
        scenarios.append({
            "scenario_id": f"curr_high_{i}",
            "stress_category": "high_stress",
            "load_scale": float(rng.uniform(1.15, 1.30)),
            "generation_scale": float(rng.uniform(0.95, 1.05)),
            "capacity_scale": float(rng.uniform(0.012, 0.020)),
            "initial_outages": outages,
        })

    # 3. Extreme scenarios (30%): severe multi-line contingencies from dataset
    ext_count = total_count - mod_count - high_count
    if train_scenarios:
        sampled_indices = rng.choice(len(train_scenarios), size=ext_count, replace=True)
        for idx in sampled_indices:
            item = dict(train_scenarios[idx])
            item["stress_category"] = "extreme"
            scenarios.append(item)

    rng.shuffle(scenarios)
    return scenarios


def _make_worker_env(
    data_dir_str: str,
    use_gcn: bool,
    scenarios: list[dict[str, Any]],
    reward_cfg: RewardConfig,
    seed: int,
):
    """Picklable worker environment factory for SubprocVecEnv."""
    def _init():
        data_dir = Path(data_dir_str)
        gcn_model, gcn_stats = load_gcn_predictor(data_dir / "models" / "best_gcn.pt", data_dir)
        return GridMitigationEnv(
            gcn_model=gcn_model,
            gcn_stats=gcn_stats,
            use_gcn_predictions=use_gcn,
            scenarios=scenarios,
            reward_config=reward_cfg,
            seed=seed,
        )
    return _init


def evaluate_controller(
    controller: Any,
    env: GridMitigationEnv,
    test_scenarios: list[dict[str, Any]],
    controller_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate a controller on fixed held-out scenarios and log action effectiveness."""
    episode_records: list[dict[str, Any]] = []
    step_records: list[dict[str, Any]] = []

    for i, scenario in enumerate(test_scenarios):
        obs, info = env.reset(options={"scenario": scenario})
        done = False
        episode_reward = 0.0
        actions_taken = []

        while not done:
            action, _ = controller.predict(obs, deterministic=True)
            actions_taken.append(action)
            obs, reward, terminated, truncated, step_info = env.step(action)
            episode_reward += reward
            done = terminated or truncated

            # Record step action effectiveness
            step_records.append({
                "controller": controller_name,
                "scenario_id": scenario.get("scenario_id", f"test_{i}"),
                "action_index": int(action),
                "action_name": step_info.get("action_taken", ACTION_NAMES[action]),
                "overload_reduced": bool(step_info.get("overload_reduced", False)),
                "load_preserved": bool(step_info.get("load_preserved", False)),
                "cascade_prevented": bool(step_info.get("cascade_prevented", False)),
                "converged": bool(step_info.get("action_converged", True)),
            })

            if done:
                record = {
                    "controller": controller_name,
                    "scenario_id": scenario.get("scenario_id", f"test_{i}"),
                    "reward": float(episode_reward),
                    "final_status": step_info.get("final_status"),
                    "failed_lines_count": int(step_info.get("failed_lines_count", 0)),
                    "cascade_length": int(step_info.get("cascade_length", 0)),
                    "load_served_percent": float(step_info.get("load_served_percent", 0.0)),
                    "load_shed_mw": float(step_info.get("load_shed_mw", 0.0)),
                    "stable": bool(step_info.get("stable", False)),
                    "total_blackout": bool(step_info.get("final_status") == "TOTAL_BLACKOUT"),
                    "partial_blackout": bool(step_info.get("final_status") == "PARTIAL_BLACKOUT"),
                    "non_converged": bool(step_info.get("final_status") == "NON_CONVERGED"),
                    "actions_count": len(actions_taken),
                }
                episode_records.append(record)

    df_episodes = pd.DataFrame(episode_records)
    summary = {
        "controller": controller_name,
        "sample_count": len(df_episodes),
        "average_reward": float(df_episodes["reward"].mean()),
        "average_failed_lines": float(df_episodes["failed_lines_count"].mean()),
        "average_cascade_length": float(df_episodes["cascade_length"].mean()),
        "average_load_served_percent": float(df_episodes["load_served_percent"].mean()),
        "average_load_shed_mw": float(df_episodes["load_shed_mw"].mean()),
        "stable_rate": float(df_episodes["stable"].mean() * 100.0),
        "total_blackout_rate": float(df_episodes["total_blackout"].mean() * 100.0),
        "partial_blackout_rate": float(df_episodes["partial_blackout"].mean() * 100.0),
        "non_converged_rate": float(df_episodes["non_converged"].mean() * 100.0),
    }
    return summary, episode_records, step_records


def summarize_action_effectiveness(all_steps: list[dict[str, Any]]) -> pd.DataFrame:
    """Aggregate action selection frequency and outcome effectiveness across controllers."""
    df_steps = pd.DataFrame(all_steps)
    if df_steps.empty:
        return pd.DataFrame()

    records = []
    for (controller, action_name), group in df_steps.groupby(["controller", "action_name"]):
        total_actions_controller = len(df_steps[df_steps["controller"] == controller])
        sel_count = len(group)
        records.append({
            "controller": controller,
            "action_name": action_name,
            "selection_count": sel_count,
            "selection_percent": round(sel_count / total_actions_controller * 100.0, 2),
            "overload_reduction_rate": round(group["overload_reduced"].mean() * 100.0, 2),
            "load_preservation_rate": round(group["load_preserved"].mean() * 100.0, 2),
            "cascade_prevention_rate": round(group["cascade_prevented"].mean() * 100.0, 2),
            "convergence_rate": round(group["converged"].mean() * 100.0, 2),
        })

    df_res = pd.DataFrame(records)
    return df_res.sort_values(by=["controller", "selection_count"], ascending=[True, False])


def compute_paired_bootstrap(
    df_episodes: pd.DataFrame,
    control_a: str = "PPO (Predictive GCN)",
    control_b: str = "PPO (No GCN)",
    n_bootstraps: int = 2000,
    seed: int = 42,
) -> pd.DataFrame:
    """Compute paired bootstrap confidence intervals for (Predictive PPO - No-GCN PPO)."""
    df_a = df_episodes[df_episodes["controller"] == control_a].set_index("scenario_id")
    df_b = df_episodes[df_episodes["controller"] == control_b].set_index("scenario_id")
    common = sorted(set(df_a.index) & set(df_b.index))
    if not common:
        return pd.DataFrame()

    metric_defs = [
        ("failed_lines_count", "Failed Lines", False),
        ("cascade_length", "Cascade Length", False),
        ("load_served_percent", "Load Served %", False),
        ("load_shed_mw", "Load Shed MW", False),
        ("stable", "Stable Grid Rate %", True),
        ("total_blackout", "Total Blackout Rate %", True),
        ("reward", "Episode Reward", False),
    ]

    rng = np.random.default_rng(seed)
    N = len(common)
    records = []

    for col, display_name, is_binary in metric_defs:
        vals_a = df_a.loc[common, col].to_numpy(dtype=float)
        vals_b = df_b.loc[common, col].to_numpy(dtype=float)
        if is_binary:
            vals_a = vals_a * 100.0
            vals_b = vals_b * 100.0

        diffs = vals_a - vals_b
        mean_diff = float(np.mean(diffs))

        boot_means = np.empty(n_bootstraps, dtype=float)
        for b in range(n_bootstraps):
            sample_idx = rng.integers(0, N, size=N)
            boot_means[b] = np.mean(diffs[sample_idx])

        ci_low = float(np.percentile(boot_means, 2.5))
        ci_high = float(np.percentile(boot_means, 97.5))

        if mean_diff >= 0:
            p_val = 2.0 * float(np.mean(boot_means <= 0.0))
        else:
            p_val = 2.0 * float(np.mean(boot_means >= 0.0))
        p_val = min(1.0, max(0.0001, p_val))

        stat_significant = bool(ci_low > 0 or ci_high < 0)

        records.append({
            "metric": display_name,
            "mean_predictive": round(float(np.mean(vals_a)), 3),
            "mean_no_gcn": round(float(np.mean(vals_b)), 3),
            "paired_diff_mean": round(mean_diff, 3),
            "ci_95_lower": round(ci_low, 3),
            "ci_95_upper": round(ci_high, 3),
            "p_value": round(p_val, 4),
            "statistically_significant": stat_significant,
        })

    return pd.DataFrame(records)


def train_ppo_agent(
    vec_env: Any,
    total_timesteps: int,
    seed: int = 42,
    log_name: str = "ppo",
) -> tuple[PPO, list[dict[str, Any]], float]:
    """Train a PPO policy with Stable-Baselines3 using vectorized rollout."""
    policy_kwargs = dict(
        net_arch=dict(pi=[64, 64], vf=[64, 64]),
    )
    n_steps = 1024
    batch_size = 64
    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=3e-4,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        policy_kwargs=policy_kwargs,
        verbose=0,
        seed=seed,
    )
    callback = MetricsCallback()
    started = time.perf_counter()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    training_time = time.perf_counter() - started
    return model, callback.history, training_time


def run_phase5_experiment(
    data_dir: Path,
    output_dir: Path,
    total_timesteps: int = 30000,
    eval_scenario_count: int = 300,
    num_workers: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    """Run full Phase 5.5 training curriculum, evaluation, and bootstrap analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = data_dir / "gnn_samples_metadata.csv"
    train_scenarios, test_scenarios = load_split_scenarios(metadata_path)

    # 1. Build curriculum for training (1,500 scenarios)
    curriculum_scenarios = generate_curriculum_scenarios(train_scenarios, total_count=1500, seed=seed)

    # 2. Subsample evaluation scenarios deterministically (at least 300)
    if len(test_scenarios) > eval_scenario_count:
        rng = np.random.default_rng(seed)
        sub_indices = rng.choice(len(test_scenarios), size=eval_scenario_count, replace=False)
        test_eval_scenarios = [test_scenarios[i] for i in sorted(sub_indices)]
    else:
        test_eval_scenarios = test_scenarios

    # Load Predictive-v2 GCN
    gcn_ckpt_path = data_dir / "models" / "best_gcn.pt"
    if not gcn_ckpt_path.exists():
        gcn_ckpt_path = Path("outputs/predictive_v2/models/best_gcn.pt")
    gcn_model, gcn_stats = load_gcn_predictor(gcn_ckpt_path, data_dir)

    reward_cfg = RewardConfig()

    training_logs: list[dict[str, Any]] = []

    # Parallel vectorized training for PPO with Predictive GCN
    print(f"Creating parallel SubprocVecEnv ({num_workers} workers) for PPO Predictive...", flush=True)
    env_fns_pred = [
        _make_worker_env(str(data_dir), True, curriculum_scenarios, reward_cfg, seed + i * 100)
        for i in range(num_workers)
    ]
    vec_env_pred = SubprocVecEnv(env_fns_pred) if num_workers > 1 else DummyVecEnv(env_fns_pred)

    print(f"Training PPO with predictive GCN for {total_timesteps} steps...", flush=True)
    ppo_pred, history_pred, time_pred = train_ppo_agent(
        vec_env_pred, total_timesteps=total_timesteps, seed=seed, log_name="ppo_predictive"
    )
    vec_env_pred.close()
    ppo_pred.save(models_dir / "ppo_predictive.zip")
    for r in history_pred:
        r["model"] = "PPO_predictive"
    training_logs.extend(history_pred)
    print(f"PPO Predictive trained in {time_pred:.2f}s", flush=True)

    # Parallel vectorized training for PPO without GCN (fair ablation)
    print(f"Creating parallel SubprocVecEnv ({num_workers} workers) for PPO No-GCN...", flush=True)
    env_fns_no_gcn = [
        _make_worker_env(str(data_dir), False, curriculum_scenarios, reward_cfg, seed + i * 100)
        for i in range(num_workers)
    ]
    vec_env_no_gcn = SubprocVecEnv(env_fns_no_gcn) if num_workers > 1 else DummyVecEnv(env_fns_no_gcn)

    print(f"Training PPO without GCN (ablation) for {total_timesteps} steps...", flush=True)
    ppo_no_gcn, history_no_gcn, time_no_gcn = train_ppo_agent(
        vec_env_no_gcn, total_timesteps=total_timesteps, seed=seed, log_name="ppo_no_gcn"
    )
    vec_env_no_gcn.close()
    ppo_no_gcn.save(models_dir / "ppo_no_gcn.zip")
    for r in history_no_gcn:
        r["model"] = "PPO_no_gcn"
    training_logs.extend(history_no_gcn)
    print(f"PPO No-GCN trained in {time_no_gcn:.2f}s", flush=True)

    # 3. Evaluation on held-out test scenarios (300 scenarios)
    eval_env_pred = GridMitigationEnv(
        gcn_model=gcn_model,
        gcn_stats=gcn_stats,
        use_gcn_predictions=True,
        reward_config=reward_cfg,
        seed=seed + 1,
    )
    eval_env_no_gcn = GridMitigationEnv(
        gcn_model=gcn_model,
        gcn_stats=gcn_stats,
        use_gcn_predictions=False,
        reward_config=reward_cfg,
        seed=seed + 1,
    )

    summaries = []
    all_episodes = []
    all_steps = []

    # Method A: Do nothing
    print(f"Evaluating Method A: Do-nothing controller ({len(test_eval_scenarios)} scenarios)...", flush=True)
    sum_a, ep_a, st_a = evaluate_controller(DoNothingController(), eval_env_pred, test_eval_scenarios, "Do-Nothing")
    summaries.append(sum_a)
    all_episodes.extend(ep_a)
    all_steps.extend(st_a)

    # Method B: Rule controller
    print(f"Evaluating Method B: Rule-based controller ({len(test_eval_scenarios)} scenarios)...", flush=True)
    sum_b, ep_b, st_b = evaluate_controller(RuleMitigationController(), eval_env_pred, test_eval_scenarios, "Rule-Controller")
    summaries.append(sum_b)
    all_episodes.extend(ep_b)
    all_steps.extend(st_b)

    # Method C: PPO without GCN
    print(f"Evaluating Method C: PPO without GCN ({len(test_eval_scenarios)} scenarios)...", flush=True)
    sum_c, ep_c, st_c = evaluate_controller(PPOController(ppo_no_gcn), eval_env_no_gcn, test_eval_scenarios, "PPO (No GCN)")
    summaries.append(sum_c)
    all_episodes.extend(ep_c)
    all_steps.extend(st_c)

    # Method D: PPO with predictive-v2 GCN
    print(f"Evaluating Method D: PPO with predictive GCN ({len(test_eval_scenarios)} scenarios)...", flush=True)
    sum_d, ep_d, st_d = evaluate_controller(PPOController(ppo_pred), eval_env_pred, test_eval_scenarios, "PPO (Predictive GCN)")
    summaries.append(sum_d)
    all_episodes.extend(ep_d)
    all_steps.extend(st_d)

    # Relative cascade prevention relative to Do-Nothing:
    do_nothing_fails = sum_a["average_failed_lines"]
    for s in summaries:
        if do_nothing_fails > 0:
            reduction = (do_nothing_fails - s["average_failed_lines"]) / do_nothing_fails * 100.0
        else:
            reduction = 0.0
        s["cascade_reduction_vs_donothing_percent"] = float(reduction)

    # Save artifacts
    df_comparison = pd.DataFrame(summaries)
    df_comparison.to_csv(output_dir / "rl_method_comparison.csv", index=False)

    df_episodes = pd.DataFrame(all_episodes)
    df_episodes.to_csv(output_dir / "rl_evaluation.csv", index=False)

    pd.DataFrame(training_logs).to_csv(output_dir / "rl_training_history.csv", index=False)

    # Action effectiveness summary
    df_actions = summarize_action_effectiveness(all_steps)
    df_actions.to_csv(output_dir / "rl_action_effectiveness.csv", index=False)

    # Paired Bootstrap Confidence Intervals
    df_bootstrap = compute_paired_bootstrap(df_episodes, "PPO (Predictive GCN)", "PPO (No GCN)", n_bootstraps=2000, seed=seed)
    df_bootstrap.to_csv(output_dir / "rl_bootstrap_comparison.csv", index=False)

    config_info = {
        "phase": "5.5",
        "total_timesteps": total_timesteps,
        "eval_scenario_count": len(test_eval_scenarios),
        "num_workers": num_workers,
        "seed": seed,
        "training_time_seconds": {
            "ppo_predictive": time_pred,
            "ppo_no_gcn": time_no_gcn,
        },
        "reward_config": {
            "weight_served_load": reward_cfg.weight_served_load,
            "weight_stability": reward_cfg.weight_stability,
            "reward_wave_prevented": reward_cfg.reward_wave_prevented,
            "reward_overload_reduction": reward_cfg.reward_overload_reduction,
            "penalty_line_failure": reward_cfg.penalty_line_failure,
            "penalty_load_loss": reward_cfg.penalty_load_loss,
            "penalty_load_shed": reward_cfg.penalty_load_shed,
            "penalty_action": reward_cfg.penalty_action,
            "penalty_overload": reward_cfg.penalty_overload,
            "penalty_non_converged": reward_cfg.penalty_non_converged,
            "penalty_total_blackout": reward_cfg.penalty_total_blackout,
            "penalty_partial_blackout": reward_cfg.penalty_partial_blackout,
        },
        "action_names": ACTION_NAMES,
        "observation_dim": 87,
    }
    (output_dir / "rl_config.json").write_text(json.dumps(config_info, indent=2) + "\n", encoding="utf-8")

    return {
        "comparison": df_comparison,
        "summaries": summaries,
        "bootstrap": df_bootstrap,
        "actions": df_actions,
        "config": config_info,
        "training_times": {"ppo_predictive": time_pred, "ppo_no_gcn": time_no_gcn},
    }
