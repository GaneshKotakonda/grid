"""Tests for controlled stress and cascade scenario generation."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pandapower.auxiliary import pandapowerNet
import pytest

from src.grid_loader import load_ieee14
from src.metrics import failed_grid_metrics
from src.scenarios import (
    DEFAULT_STRESS_PROFILES,
    generate_scenarios,
    save_scenario_results,
    stress_grid,
)
from src.simulator import run_power_flow


pytestmark = pytest.mark.filterwarnings(
    "ignore:tap_dependency_table is missing in net.*:DeprecationWarning"
)

SUMMARY_COLUMNS = {
    "scenario_id",
    "is_synthetic_stress",
    "stress_profile",
    "load_scale",
    "generation_scale",
    "capacity_scale",
    "initial_outages",
    "cascade_length",
    "failed_line_sequence",
    "total_failed_lines",
    "initial_load_mw",
    "baseline_served_load_mw",
    "final_served_load_mw",
    "load_lost_mw",
    "load_served_percent",
    "final_converged",
    "final_status",
    "final_max_loading_percent",
}
DETAIL_COLUMNS = {
    "scenario_id",
    "is_synthetic_stress",
    "stress_profile",
    "load_scale",
    "generation_scale",
    "capacity_scale",
    "initial_outages",
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


def test_stress_grid_scales_copy_without_modifying_original() -> None:
    net = load_ieee14()
    original = deepcopy(net)

    stressed = stress_grid(
        net,
        load_scale=1.4,
        generation_scale=1.1,
        capacity_scale=0.6,
    )

    assert stressed is not net
    pd.testing.assert_series_equal(stressed.load.p_mw, original.load.p_mw * 1.4)
    pd.testing.assert_series_equal(stressed.load.q_mvar, original.load.q_mvar * 1.4)
    pd.testing.assert_series_equal(stressed.gen.p_mw, original.gen.p_mw * 1.1)
    pd.testing.assert_series_equal(stressed.line.max_i_ka, original.line.max_i_ka * 0.6)
    pd.testing.assert_frame_equal(net.load, original.load)
    pd.testing.assert_frame_equal(net.gen, original.gen)
    pd.testing.assert_frame_equal(net.line, original.line)


@pytest.mark.parametrize(
    ("load_scale", "generation_scale", "capacity_scale", "message"),
    [
        (0.0, 1.0, 1.0, "load_scale"),
        (1.0, -1.0, 1.0, "generation_scale"),
        (1.0, 1.0, 0.0, "capacity_scale"),
    ],
)
def test_stress_grid_rejects_non_positive_scale(
    load_scale: float,
    generation_scale: float,
    capacity_scale: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        stress_grid(
            load_ieee14(),
            load_scale=load_scale,
            generation_scale=generation_scale,
            capacity_scale=capacity_scale,
        )


def test_default_stress_profiles_match_phase_2_design() -> None:
    assert DEFAULT_STRESS_PROFILES == [
        {
            "name": "nominal",
            "is_synthetic_stress": True,
            "load_scale": 1.0,
            "generation_scale": 1.0,
            "capacity_scale": 1.0,
        },
        {
            "name": "stressed",
            "is_synthetic_stress": True,
            "load_scale": 1.2,
            "generation_scale": 1.05,
            "capacity_scale": 0.02,
        },
        {
            "name": "severe",
            "is_synthetic_stress": True,
            "load_scale": 1.4,
            "generation_scale": 1.1,
            "capacity_scale": 0.012,
        },
    ]


def test_stressed_ieee14_operating_point_converges() -> None:
    stressed = stress_grid(
        load_ieee14(),
        load_scale=1.4,
        generation_scale=1.1,
        capacity_scale=0.012,
    )

    metrics = run_power_flow(stressed)

    assert metrics["converged"] is True
    assert metrics["total_load_mw"] == pytest.approx(362.6)


def test_generate_scenarios_is_deterministic_and_records_each_step() -> None:
    profiles = [DEFAULT_STRESS_PROFILES[0]]

    summary, details = generate_scenarios(
        load_ieee14(),
        profiles=profiles,
        line_indices=[0, 1],
        max_steps=2,
    )

    assert summary["scenario_id"].tolist() == ["nominal-line-0", "nominal-line-1"]
    assert SUMMARY_COLUMNS.issubset(summary.columns)
    assert DETAIL_COLUMNS.issubset(details.columns)
    assert len(summary) == 2
    assert details.groupby("scenario_id").size().ge(1).all()
    assert summary["final_status"].tolist() == ["STABLE", "STABLE"]
    assert summary["is_synthetic_stress"].all()
    assert summary["final_converged"].all()
    assert summary["initial_load_mw"].tolist() == pytest.approx([259.0, 259.0])
    assert summary["final_served_load_mw"].tolist() == pytest.approx([259.0, 259.0])
    assert summary["load_lost_mw"].tolist() == pytest.approx([0.0, 0.0])
    assert summary["load_served_percent"].tolist() == pytest.approx([100.0, 100.0])


def test_generate_scenarios_rejects_unknown_line() -> None:
    with pytest.raises(ValueError, match="999"):
        generate_scenarios(
            load_ieee14(),
            profiles=[DEFAULT_STRESS_PROFILES[0]],
            line_indices=[999],
        )


def test_non_converged_summary_does_not_report_zero_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_cascade(
        net: pandapowerNet,
        initial_outages: list[int],
        overload_threshold: float,
        max_steps: int,
    ) -> tuple[pandapowerNet, dict[str, Any]]:
        result = {
            "status": "NON_CONVERGED",
            "final_status": "NON_CONVERGED",
            "initial_outages": list(initial_outages),
            "failed_lines": list(initial_outages),
            "failure_sequence": [list(initial_outages)],
            "initial_load_mw": 259.0,
            "final_served_load_mw": None,
            "load_lost_mw": None,
            "load_served_percent": None,
            "total_failed_lines": 1,
            "cascade_length": 0,
            "overload_threshold": overload_threshold,
            "max_steps": max_steps,
            "history": [
                {
                    "step": 0,
                    "failed_lines": list(initial_outages),
                    "newly_failed_lines": list(initial_outages),
                    "max_line_loading_percent": None,
                    "overloaded_lines": [],
                    "min_bus_voltage_pu": None,
                    "served_load_mw": None,
                    "total_generation_mw": None,
                    "converged": False,
                    "error": "did not converge",
                }
            ],
        }
        return net, result

    monkeypatch.setattr("src.scenarios.simulate_cascade", failed_cascade)

    summary, _ = generate_scenarios(
        load_ieee14(),
        profiles=[DEFAULT_STRESS_PROFILES[0]],
        line_indices=[0],
    )

    row = summary.iloc[0]
    assert bool(row["final_converged"]) is False
    assert row["final_status"] == "NON_CONVERGED"
    assert pd.isna(row["final_served_load_mw"])
    assert pd.isna(row["load_lost_mw"])
    assert pd.isna(row["load_served_percent"])
    assert pd.isna(row["final_max_loading_percent"])


def test_non_converged_precontingency_profile_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.scenarios.run_power_flow",
        lambda net: failed_grid_metrics("baseline failed"),
    )

    with pytest.raises(RuntimeError, match="nominal"):
        generate_scenarios(
            load_ieee14(),
            profiles=[DEFAULT_STRESS_PROFILES[0]],
            line_indices=[0],
        )


def test_saved_scenario_lists_are_valid_json(tmp_path: Path) -> None:
    summary, details = generate_scenarios(
        load_ieee14(),
        profiles=[DEFAULT_STRESS_PROFILES[0]],
        line_indices=[0],
    )

    summary_path, details_path = save_scenario_results(summary, details, tmp_path)

    assert summary_path == tmp_path / "cascade_scenario_summary.csv"
    assert details_path == tmp_path / "cascade_steps.csv"
    assert summary_path.exists()
    assert details_path.exists()
    saved_summary = pd.read_csv(summary_path)
    saved_details = pd.read_csv(details_path)
    assert json.loads(saved_summary.at[0, "initial_outages"]) == [0]
    assert json.loads(saved_summary.at[0, "failed_line_sequence"]) == [[0]]
    assert json.loads(saved_details.at[0, "failed_lines"]) == [0]
    assert json.loads(saved_details.at[0, "newly_failed_lines"]) == [0]
    assert json.loads(saved_details.at[0, "overloaded_lines"]) == []
