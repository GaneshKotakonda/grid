"""Train and compare Phase 4 MLP, GCN, and GAT next-line predictors."""

import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.gnn_training import run_training  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train Phase 4 next-cascade-step line predictors.",
    )
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a short three-model check before the full training run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = {
        "epochs": 2 if args.smoke else args.epochs,
        "patience": 2 if args.smoke else args.patience,
        "learning_rate": args.learning_rate,
        "hidden_dim": 32 if args.smoke else args.hidden_dim,
        "dropout": args.dropout,
        "batch_size": 256 if args.smoke else args.batch_size,
        "seed": args.seed,
        "positive_weight_max": 20.0,
        "early_stopping_metric": "validation BCEWithLogitsLoss",
        "threshold_metric": "validation pooled micro F1",
    }
    started = time.perf_counter()
    result = run_training(args.data_dir, config)
    elapsed = time.perf_counter() - started
    print("GridResilience Phase 4 model comparison")
    print(f"Training/evaluation wall time: {elapsed:.2f} seconds")
    for row in result["comparison"]:
        print(
            f"{row['model']}: test micro-F1={row['micro_f1']:.4f}, "
            f"macro-F1={row['macro_f1']:.4f}, threshold={row['threshold']:.2f}"
        )
    for model_type, threshold in result["thresholds"].items():
        print(f"{model_type.upper()} selected validation threshold: {threshold:.2f}")
    print(f"Outputs saved under: {args.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
