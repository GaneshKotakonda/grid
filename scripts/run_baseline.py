"""Run the deterministic GridResilience Phase 1 baseline demonstration."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.grid_loader import load_ieee14  # noqa: E402
from src.metrics import compare_grid_states  # noqa: E402
from src.simulator import run_power_flow, simulate_line_outage  # noqa: E402


def main() -> int:
    """Run the baseline and first valid line outage, then save their comparison."""
    net = load_ieee14()
    baseline = run_power_flow(net)

    print("IEEE 14-Bus Grid")
    print()
    print(f"Buses: {len(net.bus)}")
    print(f"Lines: {len(net.line)}")
    print(f"Loads: {len(net.load)}")
    print(f"Generators: {len(net.gen)}")
    print()
    print("BASELINE")

    if not baseline["converged"]:
        print(f"Power flow failed to converge: {baseline['error']}")
        return 1

    print(
        "Maximum line loading: "
        f"{baseline['max_line_loading_percent']:.2f}%"
    )
    print(f"Total served load: {baseline['total_load_mw']:.2f} MW")
    print(f"Total generation: {baseline['total_generation_mw']:.2f} MW")

    in_service_lines = net.line.index[
        net.line["in_service"].fillna(False).astype(bool)
    ]
    if in_service_lines.empty:
        print("No in-service transmission line is available for the contingency.")
        return 1

    line_index = sorted(in_service_lines)[0]
    from_bus = int(net.line.at[line_index, "from_bus"])
    to_bus = int(net.line.at[line_index, "to_bus"])

    print()
    print("CONTINGENCY")
    print(f"Disconnected line: {line_index}")
    print(f"From Bus: {from_bus}")
    print(f"To Bus: {to_bus}")

    _, outage = simulate_line_outage(net, line_index)
    comparison = compare_grid_states(baseline, outage)

    print()
    print("AFTER FAILURE")
    if outage["converged"]:
        print(
            "Maximum line loading: "
            f"{outage['max_line_loading_percent']:.2f}%"
        )
        print(f"Overloaded lines: {outage['overloaded_lines']}")
        print(f"Minimum voltage: {outage['min_bus_voltage_pu']:.4f} pu")
        print(f"Total served load: {outage['total_load_mw']:.2f} MW")
        print(f"Total generation: {outage['total_generation_mw']:.2f} MW")
    else:
        print(f"Power flow failed to converge: {outage['error']}")

    output_path = PROJECT_ROOT / "outputs" / "baseline_results.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison["lines"].to_csv(output_path, index=False)
    print()
    print(f"Results saved to: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
