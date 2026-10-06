"""Tests for Phase 1 power-flow simulation and metrics."""

from pathlib import Path
import subprocess
import sys
from typing import Iterator

import numpy as np
import pandapower as pp
from pandapower.auxiliary import pandapowerNet
from pandapower.powerflow import LoadflowNotConverged
import pandas as pd
import pytest

from src.grid_loader import load_ieee14
from src.metrics import compare_grid_states, extract_grid_metrics, failed_grid_metrics
from src.simulator import run_power_flow, simulate_line_outage


pytestmark = pytest.mark.filterwarnings(
    "ignore:tap_dependency_table is missing in net.*:DeprecationWarning"
)

METRIC_KEYS = {
    "converged",
    "error",
    "lines",
    "buses",
    "total_load_mw",
    "total_generation_mw",
    "max_line_loading_percent",
    "min_bus_voltage_pu",
    "overloaded_lines",
}
LINE_COLUMNS = [
    "line_index",
    "from_bus",
    "to_bus",
    "in_service",
    "active_power_mw",
    "loading_percent",
]
BUS_COLUMNS = ["bus_index", "voltage_pu", "supplied"]
COMPARISON_LINE_COLUMNS = [
    "line_index",
    "from_bus",
    "to_bus",
    "in_service_before",
    "in_service_after",
    "active_power_mw_before",
    "active_power_mw_after",
    "loading_percent_before",
    "loading_percent_after",
    "loading_change_percent",
]
COMPARISON_BUS_COLUMNS = [
    "bus_index",
    "supplied_before",
    "supplied_after",
    "voltage_pu_before",
    "voltage_pu_after",
    "voltage_change_pu",
]
COMPARISON_KEYS = {
    "lines",
    "buses",
    "baseline_converged",
    "outage_converged",
    "max_line_loading_before",
    "max_line_loading_after",
    "min_bus_voltage_before",
    "min_bus_voltage_after",
    "total_served_load_before",
    "total_served_load_after",
    "overloaded_lines_before",
    "overloaded_lines_after",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def solved_net() -> Iterator[pandapowerNet]:
    net = load_ieee14()
    pp.runpp(net)
    yield net


def test_metrics_contain_expected_line_bus_and_summary_fields(
    solved_net: pandapowerNet,
) -> None:
    metrics = extract_grid_metrics(solved_net)

    assert set(metrics) == METRIC_KEYS
    assert metrics["converged"] is True
    assert metrics["error"] is None
    assert metrics["lines"].columns.tolist() == LINE_COLUMNS
    assert metrics["buses"].columns.tolist() == BUS_COLUMNS
    assert len(metrics["lines"]) == len(solved_net.line)
    assert len(metrics["buses"]) == len(solved_net.bus)


def test_total_generation_includes_external_grid(
    solved_net: pandapowerNet,
) -> None:
    metrics = extract_grid_metrics(solved_net)
    expected = solved_net.res_gen.p_mw.sum() + solved_net.res_ext_grid.p_mw.sum()

    assert metrics["total_generation_mw"] == pytest.approx(expected)
    assert solved_net.res_ext_grid.p_mw.sum() != 0.0


def test_served_load_excludes_unsupplied_bus(solved_net: pandapowerNet) -> None:
    bus_index = int(solved_net.load.iloc[0].bus)
    supplied_loads = solved_net.load.bus.ne(bus_index)
    expected = solved_net.res_load.loc[supplied_loads, "p_mw"].sum()
    solved_net.res_bus.loc[bus_index, "vm_pu"] = np.nan

    metrics = extract_grid_metrics(solved_net)

    assert metrics["total_load_mw"] == pytest.approx(expected)


def test_served_load_excludes_out_of_service_load(
    solved_net: pandapowerNet,
) -> None:
    load_index = solved_net.load.index[0]
    expected = solved_net.res_load.p_mw.sum() - solved_net.res_load.at[load_index, "p_mw"]
    solved_net.load.at[load_index, "in_service"] = False

    metrics = extract_grid_metrics(solved_net)

    assert metrics["total_load_mw"] == pytest.approx(expected)


def test_served_load_excludes_out_of_service_bus(
    solved_net: pandapowerNet,
) -> None:
    bus_index = int(solved_net.load.iloc[0].bus)
    supplied_loads = solved_net.load.bus.ne(bus_index)
    expected = solved_net.res_load.loc[supplied_loads, "p_mw"].sum()
    solved_net.bus.at[bus_index, "in_service"] = False

    metrics = extract_grid_metrics(solved_net)

    assert metrics["total_load_mw"] == pytest.approx(expected)


def test_total_generation_handles_empty_result_tables(
    solved_net: pandapowerNet,
) -> None:
    solved_net.res_gen = solved_net.res_gen.iloc[0:0].copy()
    solved_net.res_ext_grid = solved_net.res_ext_grid.iloc[0:0].copy()

    metrics = extract_grid_metrics(solved_net)

    assert metrics["total_generation_mw"] == 0.0


def test_failed_metrics_are_explicit_and_empty() -> None:
    metrics = failed_grid_metrics("solver stopped")

    assert set(metrics) == METRIC_KEYS
    assert metrics["converged"] is False
    assert metrics["error"] == "solver stopped"
    assert metrics["lines"].empty
    assert metrics["lines"].columns.tolist() == LINE_COLUMNS
    assert metrics["buses"].empty
    assert metrics["buses"].columns.tolist() == BUS_COLUMNS
    assert metrics["total_load_mw"] is None
    assert metrics["total_generation_mw"] is None
    assert metrics["max_line_loading_percent"] is None
    assert metrics["min_bus_voltage_pu"] is None
    assert metrics["overloaded_lines"] == []


def test_normal_power_flow_converges() -> None:
    metrics = run_power_flow(load_ieee14())

    assert metrics["converged"] is True
    assert set(metrics) == METRIC_KEYS
    assert not metrics["lines"].empty
    assert not metrics["buses"].empty


def test_line_outage_does_not_modify_original() -> None:
    net = load_ieee14()
    original_lines = net.line.copy(deep=True)
    line_index = net.line.index[0]

    simulate_line_outage(net, line_index)

    pd.testing.assert_frame_equal(net.line, original_lines)


def test_selected_line_is_disconnected_only_in_copy() -> None:
    net = load_ieee14()
    line_index = net.line.index[0]

    outage_net, _ = simulate_line_outage(net, line_index)

    assert bool(outage_net.line.at[line_index, "in_service"]) is False
    assert bool(net.line.at[line_index, "in_service"]) is True


def test_line_outage_returns_expected_metric_fields() -> None:
    net = load_ieee14()

    outage_net, metrics = simulate_line_outage(net, net.line.index[0])

    assert isinstance(outage_net, pandapowerNet)
    assert set(metrics) == METRIC_KEYS
    assert isinstance(metrics["converged"], bool)


def test_line_outage_rejects_unknown_index() -> None:
    net = load_ieee14()
    unknown_index = int(net.line.index.max()) + 1

    with pytest.raises(ValueError, match=str(unknown_index)):
        simulate_line_outage(net, unknown_index)


def test_non_convergence_returns_failed_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_non_convergence(*args: object, **kwargs: object) -> None:
        raise LoadflowNotConverged("did not converge")

    monkeypatch.setattr(pp, "runpp", raise_non_convergence)

    metrics = run_power_flow(load_ieee14())

    assert metrics["converged"] is False
    assert metrics["error"] == "did not converge"
    assert metrics["lines"].empty
    assert metrics["buses"].empty


def test_comparison_contains_line_bus_and_summary_changes() -> None:
    net = load_ieee14()
    baseline = run_power_flow(net)
    _, outage = simulate_line_outage(net, net.line.index[0])

    comparison = compare_grid_states(baseline, outage)

    assert set(comparison) == COMPARISON_KEYS
    assert comparison["lines"].columns.tolist() == COMPARISON_LINE_COLUMNS
    assert comparison["buses"].columns.tolist() == COMPARISON_BUS_COLUMNS
    assert len(comparison["lines"]) == len(net.line)
    assert len(comparison["buses"]) == len(net.bus)
    assert comparison["baseline_converged"] is True
    assert comparison["outage_converged"] is True
    assert comparison["max_line_loading_before"] == pytest.approx(
        baseline["max_line_loading_percent"]
    )
    assert comparison["max_line_loading_after"] == pytest.approx(
        outage["max_line_loading_percent"]
    )
    assert comparison["min_bus_voltage_before"] == pytest.approx(
        baseline["min_bus_voltage_pu"]
    )
    assert comparison["min_bus_voltage_after"] == pytest.approx(
        outage["min_bus_voltage_pu"]
    )
    assert comparison["total_served_load_before"] == pytest.approx(
        baseline["total_load_mw"]
    )
    assert comparison["total_served_load_after"] == pytest.approx(
        outage["total_load_mw"]
    )
    assert comparison["overloaded_lines_before"] == baseline["overloaded_lines"]
    assert comparison["overloaded_lines_after"] == outage["overloaded_lines"]


def test_comparison_preserves_unavailable_after_values(
    solved_net: pandapowerNet,
) -> None:
    baseline = extract_grid_metrics(solved_net)
    failed = failed_grid_metrics("outage did not converge")

    comparison = compare_grid_states(baseline, failed)

    assert comparison["lines"]["active_power_mw_after"].isna().all()
    assert comparison["lines"]["loading_percent_after"].isna().all()
    assert comparison["lines"]["loading_change_percent"].isna().all()
    assert comparison["buses"]["voltage_pu_after"].isna().all()
    assert comparison["buses"]["voltage_change_pu"].isna().all()
    assert comparison["max_line_loading_after"] is None
    assert comparison["min_bus_voltage_after"] is None
    assert comparison["total_served_load_after"] is None
    assert comparison["overloaded_lines_after"] is None


def test_demo_writes_csv_and_prints_summary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_baseline.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "IEEE 14-Bus Grid" in result.stdout
    assert "BASELINE" in result.stdout
    assert "CONTINGENCY" in result.stdout
    assert "AFTER FAILURE" in result.stdout
    assert "Results saved to:" in result.stdout

    output_path = PROJECT_ROOT / "outputs" / "baseline_results.csv"
    assert output_path.exists()
    output = pd.read_csv(output_path)
    assert not output.empty
    assert {
        "line_index",
        "active_power_mw_before",
        "active_power_mw_after",
        "loading_percent_before",
        "loading_percent_after",
        "loading_change_percent",
    }.issubset(output.columns)
