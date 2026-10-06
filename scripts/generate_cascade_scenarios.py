"""Generate the default Phase 2 IEEE 14-bus cascade datasets."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.grid_loader import load_ieee14  # noqa: E402
from src.scenarios import generate_scenarios, save_scenario_results  # noqa: E402


def main() -> int:
    """Run all default profile/line combinations and save both datasets."""
    summary, steps = generate_scenarios(load_ieee14())
    summary_path, steps_path = save_scenario_results(
        summary,
        steps,
        PROJECT_ROOT / "outputs",
    )

    print("GridResilience Phase 2 Scenario Generation")
    print(f"Scenarios generated: {len(summary)}")
    print(f"Cascade-step records: {len(steps)}")
    print(f"Summary CSV: {summary_path.relative_to(PROJECT_ROOT)}")
    print(f"Detailed steps CSV: {steps_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
