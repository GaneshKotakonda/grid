"""Generate validated Phase 3 graph-learning datasets from IEEE 14-bus."""

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.gnn_dataset import (  # noqa: E402
    build_line_failure_coverage,
    build_dataset_summary,
    generate_gnn_dataset,
    save_gnn_dataset,
)
from src.grid_loader import load_ieee14  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate reproducible IEEE-14 cascade graph samples.",
    )
    parser.add_argument("--scenarios", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--load-scale-min", type=float, default=0.8)
    parser.add_argument("--load-scale-max", type=float, default=1.5)
    parser.add_argument("--generation-scale-min", type=float, default=0.9)
    parser.add_argument("--generation-scale-max", type=float, default=1.1)
    parser.add_argument("--capacity-scale-min", type=float, default=0.000005)
    parser.add_argument("--capacity-scale-max", type=float, default=0.02)
    parser.add_argument("--overload-threshold", type=float, default=100.0)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--max-initial-outages", type=int, default=2)
    parser.add_argument(
        "--multiple-outage-probability",
        type=float,
        default=0.2,
    )
    parser.add_argument("--load-variation-min", type=float, default=0.8)
    parser.add_argument("--load-variation-max", type=float, default=1.2)
    parser.add_argument("--reactive-load-variation-min", type=float, default=0.9)
    parser.add_argument("--reactive-load-variation-max", type=float, default=1.1)
    parser.add_argument("--generator-dispatch-variation-min", type=float, default=0.8)
    parser.add_argument("--generator-dispatch-variation-max", type=float, default=1.2)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Generate, validate, serialize, and report one graph dataset."""
    args = _parser().parse_args(argv)
    build = generate_gnn_dataset(
        load_ieee14(),
        scenario_count=args.scenarios,
        seed=args.seed,
        load_scale_range=(args.load_scale_min, args.load_scale_max),
        generation_scale_range=(
            args.generation_scale_min,
            args.generation_scale_max,
        ),
        capacity_scale_range=(
            args.capacity_scale_min,
            args.capacity_scale_max,
        ),
        overload_threshold=args.overload_threshold,
        max_steps=args.max_steps,
        max_initial_outages=args.max_initial_outages,
        multiple_outage_probability=args.multiple_outage_probability,
        load_variation_range=(args.load_variation_min, args.load_variation_max),
        reactive_load_variation_range=(
            args.reactive_load_variation_min,
            args.reactive_load_variation_max,
        ),
        generator_dispatch_variation_range=(
            args.generator_dispatch_variation_min,
            args.generator_dispatch_variation_max,
        ),
    )
    paths = save_gnn_dataset(build, args.output_dir)
    summary = build_dataset_summary(build).iloc[0]

    print("GridResilience Phase 3 GNN Dataset Generation")
    print(f"Scenarios generated: {int(summary['total_scenarios'])}")
    print(f"Graph samples: {int(summary['total_graph_samples'])}")
    print(
        f"Positive samples: {int(summary['positive_samples'])} "
        f"({summary['positive_sample_percent']:.2f}%)"
    )
    print(
        f"Negative samples: {int(summary['negative_samples'])} "
        f"({summary['negative_sample_percent']:.2f}%)"
    )
    print(
        "Train/validation/test samples: "
        f"{int(summary['train_samples'])}/"
        f"{int(summary['validation_samples'])}/"
        f"{int(summary['test_samples'])}"
    )
    print(f"Generation time: {build.generation_seconds:.2f} seconds")
    positive = int(summary["positive_samples"])
    negative = int(summary["negative_samples"])
    print(
        f"Positive/negative ratio: {positive / negative:.3f}:1"
        if negative else f"Positive/negative ratio: {positive}:0"
    )
    print("Per-line failure coverage (line: initial / secondary):")
    for row in build_line_failure_coverage(build).itertuples(index=False):
        print(
            f"  {row.line_index}: {row.initial_outage_count} / "
            f"{row.secondary_failure_count}"
        )
    for name, path in paths.items():
        print(f"Saved {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
