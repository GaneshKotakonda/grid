"""Run Phase 6 evaluation comparing No-Recovery vs Greedy-Recovery across damaged scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import EndToEndPipeline
from src.recovery import RecoveryConfig
from src.rl_training import load_split_scenarios


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 6 post-cascade power grid recovery.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "predictive_v2",
        help="Path to predictive_v2 dataset metadata and GCN model",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help="Output directory for recovery evaluation artifacts",
    )
    parser.add_argument(
        "--scenarios-count",
        type=int,
        default=100,
        help="Number of held-out scenarios to evaluate (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    return parser


def run_recovery_evaluation(
    data_dir: Path,
    output_dir: Path,
    scenarios_count: int = 100,
    seed: int = 42,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = data_dir / "gnn_samples_metadata.csv"
    train_scenarios, test_scenarios = load_split_scenarios(metadata_path)

    # Subsample test scenarios
    if len(test_scenarios) > scenarios_count:
        rng = np.random.default_rng(seed)
        sub_indices = rng.choice(len(test_scenarios), size=scenarios_count, replace=False)
        eval_scenarios = [test_scenarios[i] for i in sorted(sub_indices)]
    else:
        eval_scenarios = test_scenarios

    print(f"Initializing End-to-End Pipeline on {len(eval_scenarios)} held-out scenarios...", flush=True)
    pipeline = EndToEndPipeline(
        gcn_model_path=data_dir / "models" / "best_gcn.pt",
        gcn_data_dir=data_dir,
        ppo_model_path=output_dir / "models" / "ppo_predictive.zip",
    )

    evaluation_records: list[dict[str, Any]] = []
    recovery_action_records: list[dict[str, Any]] = []

    print("Executing incidents with and without recovery...", flush=True)
    for i, scen in enumerate(eval_scenarios):
        # 1. Condition A: No Recovery (cascade outcome as-is)
        res_no_rec = pipeline.run_incident(scen, enable_mitigation=True, enable_recovery=False, seed=seed + i)
        # 2. Condition B: Greedy Recovery
        res_rec = pipeline.run_incident(scen, enable_mitigation=True, enable_recovery=True, seed=seed + i)

        record = {
            "scenario_id": scen.get("scenario_id", f"scen_{i}"),
            "initial_load_mw": res_rec["initial_load_mw"],
            "initial_outages": str(res_rec["initial_outages"]),
            # Condition A: No Recovery
            "no_rec_served_mw": res_no_rec["post_cascade_served_mw"],
            "no_rec_served_percent": round(res_no_rec["post_cascade_served_mw"] / res_no_rec["initial_load_mw"] * 100.0 if res_no_rec["initial_load_mw"] > 0 else 0.0, 2),
            "no_rec_status": res_no_rec["post_cascade_status"],
            "no_rec_blackout": bool(res_no_rec["post_cascade_status"] == "TOTAL_BLACKOUT"),
            # Condition B: Greedy Recovery
            "post_cascade_served_mw": res_rec["post_cascade_served_mw"],
            "post_cascade_served_percent": round(res_rec["post_cascade_served_mw"] / res_rec["initial_load_mw"] * 100.0 if res_rec["initial_load_mw"] > 0 else 0.0, 2),
            "final_recovered_served_mw": res_rec["final_restored_mw"],
            "final_recovered_percent": res_rec["final_load_served_percent"],
            "mw_restored": res_rec["mw_restored"],
            "reconnected_lines_count": res_rec["reconnected_lines_count"],
            "recovery_steps": res_rec["recovery_steps"],
            "final_status": res_rec["final_status"],
            "final_blackout": bool(res_rec["final_status"] == "TOTAL_BLACKOUT"),
            "final_stable": bool(res_rec["final_status"] == "STABLE"),
            "non_converged": bool(res_rec["final_status"] == "NON_CONVERGED"),
            "recovery_success": bool(res_rec["mw_restored"] > 0 or (res_rec["post_cascade_status"] != "STABLE" and res_rec["final_status"] == "STABLE")),
        }
        evaluation_records.append(record)

        # Log recovery step actions
        for log_entry in res_rec["audit_log"]:
            if "RECOVERY_STEP" in log_entry["stage"]:
                recovery_action_records.append({
                    "scenario_id": scen.get("scenario_id", f"scen_{i}"),
                    "action": log_entry["action"],
                    "committed": log_entry["committed"],
                    "served_load_mw": log_entry["served_load_mw"],
                    "reason": log_entry["reason"],
                })

    df_eval = pd.DataFrame(evaluation_records)
    df_eval.to_csv(output_dir / "recovery_evaluation.csv", index=False)

    df_actions = pd.DataFrame(recovery_action_records)
    df_actions.to_csv(output_dir / "recovery_actions.csv", index=False)

    # Summary table comparing No Recovery vs Greedy Recovery
    summary_data = [
        {
            "method": "No Recovery",
            "scenario_count": len(df_eval),
            "average_served_load_mw": round(float(df_eval["no_rec_served_mw"].mean()), 2),
            "average_load_served_percent": round(float(df_eval["no_rec_served_percent"].mean()), 2),
            "average_mw_restored": 0.0,
            "average_reconnected_lines": 0.0,
            "average_recovery_steps": 0.0,
            "stable_grid_rate": round(float((df_eval["no_rec_status"] == "STABLE").mean() * 100.0), 2),
            "total_blackout_rate": round(float(df_eval["no_rec_blackout"].mean() * 100.0), 2),
            "non_converged_rate": round(float((df_eval["no_rec_status"] == "NON_CONVERGED").mean() * 100.0), 2),
            "recovery_success_rate": 0.0,
        },
        {
            "method": "Greedy Recovery",
            "scenario_count": len(df_eval),
            "average_served_load_mw": round(float(df_eval["final_recovered_served_mw"].mean()), 2),
            "average_load_served_percent": round(float(df_eval["final_recovered_percent"].mean()), 2),
            "average_mw_restored": round(float(df_eval["mw_restored"].mean()), 2),
            "average_reconnected_lines": round(float(df_eval["reconnected_lines_count"].mean()), 2),
            "average_recovery_steps": round(float(df_eval["recovery_steps"].mean()), 2),
            "stable_grid_rate": round(float(df_eval["final_stable"].mean() * 100.0), 2),
            "total_blackout_rate": round(float(df_eval["final_blackout"].mean() * 100.0), 2),
            "non_converged_rate": round(float(df_eval["non_converged"].mean() * 100.0), 2),
            "recovery_success_rate": round(float(df_eval["recovery_success"].mean() * 100.0), 2),
        },
    ]
    df_summary = pd.DataFrame(summary_data)
    df_summary.to_csv(output_dir / "recovery_summary.csv", index=False)

    rec_cfg = RecoveryConfig()
    config_dict = {
        "phase": "6",
        "scenario_count": len(df_eval),
        "seed": seed,
        "recovery_config": {
            "voltage_min_pu": rec_cfg.voltage_min_pu,
            "voltage_max_pu": rec_cfg.voltage_max_pu,
            "overload_threshold": rec_cfg.overload_threshold,
            "max_recovery_steps": rec_cfg.max_recovery_steps,
            "load_restore_fraction": rec_cfg.load_restore_fraction,
        },
        "summary": summary_data,
    }
    (output_dir / "recovery_config.json").write_text(json.dumps(config_dict, indent=2) + "\n", encoding="utf-8")

    return {
        "evaluation": df_eval,
        "summary": df_summary,
        "actions": df_actions,
        "config": config_dict,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started = time.perf_counter()
    res = run_recovery_evaluation(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        scenarios_count=args.scenarios_count,
        seed=args.seed,
    )
    elapsed = time.perf_counter() - started
    print(f"\nPhase 6 Recovery Evaluation completed in {elapsed:.2f} seconds.")
    print("\nRECOVERY COMPARISON SUMMARY:")
    print(res["summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
