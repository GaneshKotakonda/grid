"""Tests for deterministic overload-driven cascade simulation."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd
from pandapower.auxiliary import pandapowerNet
import pytest

from src.cascade import find_overloaded_lines, simulate_cascade
from src.grid_loader import load_ieee14
from src.metrics import failed_grid_metrics


pytestmark = pytest.mark.filterwarnings(
    "ignore:tap_dependency_table is missing in net.*:DeprecationWarning"
)

RESULT_KEYS = {
    "status",
    "final_status",
    "initial_outages",
    "failed_lines",
    "failure_sequence",
    "initial_load_mw",
    "final_served_load_mw",
    "load_lost_mw",
    "load_served_percent",
    "total_failed_lines",
    "cascade_length",
    "overload_threshold",
    "max_steps",
    "history",
}
STEP_KEYS = {
    "step",
    "failed_lines",
    "newly_failed_lines",
    "max_line_loading_percent",
    "overloaded_lines",
    "min_bus_voltage_pu",
    "served_load_mw",
    "total_generation_mw",
    "converged",
    "error",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _metrics_for(
    net: pandapowerNet,
    loading_by_line: dict[int, float] | None = None,
    served_load_mw: float = 259.0,
) -> dict[str, Any]:
    loading_by_line = loading_by_line or {}
    lines = net.line.loc[:, ["from_bus", "to_bus", "in_service"]].copy()
    lines["active_power_mw"] = 0.0
    lines["loading_percent"] = [
        loading_by_line.get(int(index), 10.0) for index in lines.index
    ]
    lines = lines.rename_axis("line_index").reset_index()
    return {
        "converged": True,
        "error": None,
        "lines": lines,
        "buses": pd.DataFrame(
            {
                "bus_index": net.bus.index,
                "voltage_pu": 1.0,
                "supplied": True,
            }
        ),
        "total_load_mw": served_load_mw,
        "total_generation_mw": 105.0,
        "max_line_loading_percent": float(lines["loading_percent"].max()),
        "min_bus_voltage_pu": 1.0,
        "overloaded_lines": [],
    }


def test_overload_detection_is_strict_and_in_service_only() -> None:
    metrics = {
        "lines": pd.DataFrame(
            {
                "line_index": [0, 1, 2, 3],
                "in_service": [True, False, True, True],
                "loading_percent": [100.0, 150.0, 100.1, float("nan")],
            }
        )
    }

    assert find_overloaded_lines(metrics, overload_threshold=100.0) == [2]


def test_cascade_preserves_original_and_applies_initial_outage() -> None:
    net = load_ieee14()
    original = deepcopy(net)

    cascade_net, result = simulate_cascade(net, [0])

    pd.testing.assert_frame_equal(net.line, original.line)
    pd.testing.assert_frame_equal(net.res_line, original.res_line)
    assert bool(net.line.at[0, "in_service"]) is True
    assert bool(cascade_net.line.at[0, "in_service"]) is False
    assert result["initial_outages"] == [0]
    assert result["failed_lines"] == [0]


def test_stable_cascade_records_complete_history() -> None:
    _, result = simulate_cascade(load_ieee14(), [0])

    assert set(result) == RESULT_KEYS
    assert result["status"] == "STABLE"
    assert result["final_status"] == "STABLE"
    assert result["initial_load_mw"] == pytest.approx(259.0)
    assert result["final_served_load_mw"] == pytest.approx(259.0)
    assert result["load_lost_mw"] == pytest.approx(0.0)
    assert result["load_served_percent"] == pytest.approx(100.0)
    assert result["total_failed_lines"] == 1
    assert result["failure_sequence"] == [[0]]
    assert result["cascade_length"] == 0
    assert result["overload_threshold"] == 100.0
    assert result["max_steps"] == 20
    assert len(result["history"]) == 1
    step = result["history"][0]
    assert set(step) == STEP_KEYS
    assert step["step"] == 0
    assert step["failed_lines"] == [0]
    assert step["newly_failed_lines"] == [0]
    assert step["overloaded_lines"] == []
    assert step["converged"] is True


def test_state_capture_is_opt_in_and_preserves_each_solved_topology() -> None:
    _, default_result = simulate_cascade(load_ieee14(), [0])

    cascade_net, captured_result = simulate_cascade(
        load_ieee14(),
        [0],
        capture_network_states=True,
    )

    assert set(default_result["history"][0]) == STEP_KEYS
    captured_step = captured_result["history"][0]
    assert set(captured_step) == STEP_KEYS | {"network_state"}
    snapshot = captured_step["network_state"]
    assert snapshot is not cascade_net
    assert bool(snapshot.line.at[0, "in_service"]) is False

    cascade_net.line.at[0, "in_service"] = True

    assert bool(snapshot.line.at[0, "in_service"]) is False


def test_duplicate_initial_outages_are_normalized() -> None:
    cascade_net, result = simulate_cascade(load_ieee14(), [0, 0])

    assert result["initial_outages"] == [0]
    assert result["failure_sequence"] == [[0]]
    assert result["failed_lines"] == [0]
    assert bool(cascade_net.line.at[0, "in_service"]) is False


def test_overloaded_lines_trip_in_next_wave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def solved_state(net: pandapowerNet) -> dict[str, Any]:
        if bool(net.line.at[1, "in_service"]):
            return _metrics_for(net, {1: 150.0})
        return _metrics_for(net)

    monkeypatch.setattr("src.cascade.run_power_flow", solved_state)
    net = load_ieee14()

    cascade_net, result = simulate_cascade(net, [0])

    assert result["status"] == "STABLE"
    assert result["failure_sequence"] == [[0], [1]]
    assert result["cascade_length"] == 1
    assert [step["newly_failed_lines"] for step in result["history"]] == [
        [0],
        [1],
    ]
    assert result["history"][0]["overloaded_lines"] == [1]
    assert result["history"][1]["overloaded_lines"] == []
    assert bool(cascade_net.line.at[1, "in_service"]) is False
    assert bool(net.line.at[1, "in_service"]) is True


def test_max_steps_stops_before_unapplied_overload_wave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def sequential_overloads(net: pandapowerNet) -> dict[str, Any]:
        if bool(net.line.at[1, "in_service"]):
            return _metrics_for(net, {1: 150.0})
        return _metrics_for(net, {2: 175.0})

    monkeypatch.setattr("src.cascade.run_power_flow", sequential_overloads)

    cascade_net, result = simulate_cascade(load_ieee14(), [0], max_steps=1)

    assert result["status"] == "MAX_STEPS_REACHED"
    assert result["failure_sequence"] == [[0], [1]]
    assert result["cascade_length"] == 1
    assert len(result["history"]) == 2
    assert result["history"][-1]["overloaded_lines"] == [2]
    assert bool(cascade_net.line.at[1, "in_service"]) is False
    assert bool(cascade_net.line.at[2, "in_service"]) is True


def test_zero_max_steps_records_only_initial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.cascade.run_power_flow",
        lambda net: _metrics_for(net, {1: 150.0}),
    )

    cascade_net, result = simulate_cascade(load_ieee14(), [0], max_steps=0)

    assert result["status"] == "MAX_STEPS_REACHED"
    assert len(result["history"]) == 1
    assert result["failure_sequence"] == [[0]]
    assert result["history"][0]["overloaded_lines"] == [1]
    assert bool(cascade_net.line.at[1, "in_service"]) is True


def test_non_convergence_is_recorded_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.cascade.run_power_flow",
        lambda net: failed_grid_metrics("cascade did not converge"),
    )

    _, result = simulate_cascade(load_ieee14(), [0])

    assert result["status"] == "NON_CONVERGED"
    assert result["final_status"] == "NON_CONVERGED"
    assert result["final_served_load_mw"] is None
    assert result["load_lost_mw"] is None
    assert result["load_served_percent"] is None
    assert result["failure_sequence"] == [[0]]
    assert len(result["history"]) == 1
    assert result["history"][0]["converged"] is False
    assert result["history"][0]["error"] == "cascade did not converge"
    assert result["history"][0]["max_line_loading_percent"] is None
    assert result["history"][0]["overloaded_lines"] == []


def test_partial_blackout_is_classified_from_significant_load_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.cascade.run_power_flow",
        lambda net: _metrics_for(net, served_load_mw=129.5),
    )

    _, result = simulate_cascade(load_ieee14(), [0])

    assert result["status"] == "PARTIAL_BLACKOUT"
    assert result["final_status"] == "PARTIAL_BLACKOUT"
    assert result["initial_load_mw"] == pytest.approx(259.0)
    assert result["final_served_load_mw"] == pytest.approx(129.5)
    assert result["load_lost_mw"] == pytest.approx(129.5)
    assert result["load_served_percent"] == pytest.approx(50.0)


def test_total_blackout_is_classified_when_served_load_is_near_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.cascade.run_power_flow",
        lambda net: _metrics_for(net, served_load_mw=1e-9),
    )

    _, result = simulate_cascade(load_ieee14(), [0])

    assert result["status"] == "TOTAL_BLACKOUT"
    assert result["final_status"] == "TOTAL_BLACKOUT"
    assert result["final_served_load_mw"] == pytest.approx(1e-9)
    assert result["load_lost_mw"] == pytest.approx(259.0)
    assert result["load_served_percent"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    ("initial_outages", "threshold", "max_steps", "message"),
    [
        ([], 100.0, 20, "initial_outages"),
        ([999], 100.0, 20, "999"),
        ([0], 0.0, 20, "overload_threshold"),
        ([0], 100.0, -1, "max_steps"),
    ],
)
def test_cascade_rejects_invalid_inputs(
    initial_outages: list[int],
    threshold: float,
    max_steps: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        simulate_cascade(
            load_ieee14(),
            initial_outages,
            overload_threshold=threshold,
            max_steps=max_steps,
        )


def test_cascade_demo_prints_complete_trace() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_cascade_demo.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Initial outage:" in result.stdout
    assert "Step 0:" in result.stdout
    assert "New failures:" in result.stdout
    assert "CASCADE ENDED" in result.stdout
    assert "Synthetic stress scenario: True" in result.stdout
    assert "Total failed lines:" in result.stdout
    assert "Load lost:" in result.stdout
    assert "Load served: 0.00%" in result.stdout
    assert "Final status: TOTAL_BLACKOUT" in result.stdout
