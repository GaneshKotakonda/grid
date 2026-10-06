"""Run one deterministic stressed IEEE 14-bus cascade demonstration."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cascade import simulate_cascade  # noqa: E402
from src.grid_loader import load_ieee14  # noqa: E402
from src.scenarios import DEFAULT_STRESS_PROFILES, stress_grid  # noqa: E402
from src.simulator import run_power_flow  # noqa: E402


def _format_metric(value: float | None, suffix: str, digits: int = 2) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.{digits}f}{suffix}"


def main() -> int:
    """Print the complete trip-wave history for a cascading severe scenario."""
    profile = DEFAULT_STRESS_PROFILES[2]
    initial_line = 5
    stressed = stress_grid(
        load_ieee14(),
        load_scale=profile["load_scale"],
        generation_scale=profile["generation_scale"],
        capacity_scale=profile["capacity_scale"],
    )
    baseline = run_power_flow(stressed)
    if not baseline["converged"]:
        print(f"Stressed baseline failed to converge: {baseline['error']}")
        return 1

    _, cascade = simulate_cascade(stressed, [initial_line])

    print("GridResilience Phase 2 Cascade Demo")
    print(f"Stress profile: {profile['name']}")
    print(f"Synthetic stress scenario: {profile['is_synthetic_stress']}")
    print(f"Capacity scale: {profile['capacity_scale']}")
    print(f"Initial outage: Line {initial_line}")
    for step in cascade["history"]:
        print()
        print(f"Step {step['step']}:")
        print(f"New failures: {step['newly_failed_lines']}")
        print(f"Failed lines: {step['failed_lines']}")
        print(
            "Max loading: "
            + _format_metric(step["max_line_loading_percent"], "%")
        )
        print(f"Overloaded lines: {step['overloaded_lines']}")
        print(
            "Minimum voltage: "
            + _format_metric(step["min_bus_voltage_pu"], " pu", digits=4)
        )
        print(
            "Served load: " + _format_metric(step["served_load_mw"], " MW")
        )
        print(f"Converged: {step['converged']}")

    print()
    print("CASCADE ENDED")
    print(f"Total failed lines: {cascade['total_failed_lines']}")
    print(f"Failed-line sequence: {cascade['failure_sequence']}")
    print(
        "Initial load: "
        + _format_metric(cascade["initial_load_mw"], " MW")
    )
    print(
        "Final served load: "
        + _format_metric(cascade["final_served_load_mw"], " MW")
    )
    print("Load lost: " + _format_metric(cascade["load_lost_mw"], " MW"))
    print(
        "Load served: "
        + _format_metric(cascade["load_served_percent"], "%")
    )
    print(f"Final status: {cascade['final_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
