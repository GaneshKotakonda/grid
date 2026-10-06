"""Run Phase 5 PPO training and baseline evaluation."""

import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rl_training import run_phase5_experiment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and evaluate Phase 5 PPO mitigation agent.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "predictive_v2",
        help="Path to predictive_v2 dataset with GCN model",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help="Output directory for RL models and metrics",
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=30000,
        help="Total training steps for PPO (default: 30,000)",
    )
    parser.add_argument(
        "--eval-scenarios",
        type=int,
        default=300,
        help="Number of held-out test scenarios for evaluation (default: 300)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel environment workers (default: 4)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a quick smoke test before full training",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    timesteps = 500 if args.smoke else args.timesteps
    eval_count = 10 if args.smoke else args.eval_scenarios
    workers = 1 if args.smoke else args.num_workers

    print(f"Starting Phase 5.5 PPO Experiment (steps={timesteps}, eval_scenarios={eval_count}, workers={workers})...")
    started = time.perf_counter()
    results = run_phase5_experiment(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        total_timesteps=timesteps,
        eval_scenario_count=eval_count,
        num_workers=workers,
        seed=args.seed,
    )
    elapsed = time.perf_counter() - started
    print(f"\nPhase 5.5 Experiment completed in {elapsed:.2f} seconds.")
    print("\nMETHOD COMPARISON SUMMARY:")
    print(results["comparison"].to_string(index=False))
    if "bootstrap" in results and not results["bootstrap"].empty:
        print("\nPAIRED BOOTSTRAP CONFIDENCE INTERVALS (Predictive PPO - No-GCN PPO):")
        print(results["bootstrap"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
