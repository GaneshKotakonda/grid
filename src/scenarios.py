"""Controlled operating-point stress and cascade scenario generation."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pandapower.auxiliary import pandapowerNet

from src.cascade import simulate_cascade
from src.simulator import run_power_flow


DEFAULT_STRESS_PROFILES: list[dict[str, Any]] = [
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

SUMMARY_COLUMNS = [
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
]

DETAIL_COLUMNS = [
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
]


def stress_grid(
    net: pandapowerNet,
    load_scale: float = 1.0,
    generation_scale: float = 1.0,
    capacity_scale: float = 1.0,
    load_multipliers: list[float] | None = None,
    reactive_load_multipliers: list[float] | None = None,
    generator_dispatch_mw: list[float] | None = None,
) -> pandapowerNet:
    """Return a stressed deep copy without changing the caller's network."""
    scales = {
        "load_scale": load_scale,
        "generation_scale": generation_scale,
        "capacity_scale": capacity_scale,
    }
    for name, value in scales.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    stressed = deepcopy(net)
    stressed.load.loc[:, "p_mw"] *= load_scale
    stressed.load.loc[:, "q_mvar"] *= load_scale
    stressed.gen.loc[:, "p_mw"] *= generation_scale
    if load_multipliers is not None:
        if len(load_multipliers) != len(stressed.load):
            raise ValueError("load_multipliers must match the load count")
        if any(value <= 0 for value in load_multipliers):
            raise ValueError("load_multipliers must be positive")
        stressed.load.loc[:, "p_mw"] *= load_multipliers
    if reactive_load_multipliers is not None:
        if len(reactive_load_multipliers) != len(stressed.load):
            raise ValueError("reactive_load_multipliers must match the load count")
        if any(value <= 0 for value in reactive_load_multipliers):
            raise ValueError("reactive_load_multipliers must be positive")
        stressed.load.loc[:, "q_mvar"] *= reactive_load_multipliers
    if generator_dispatch_mw is not None:
        if len(generator_dispatch_mw) != len(stressed.gen):
            raise ValueError("generator_dispatch_mw must match the generator count")
        dispatch = pd.Series(generator_dispatch_mw, index=stressed.gen.index)
        if "min_p_mw" in stressed.gen:
            dispatch = dispatch.clip(lower=stressed.gen["min_p_mw"])
        if "max_p_mw" in stressed.gen:
            dispatch = dispatch.clip(upper=stressed.gen["max_p_mw"])
        stressed.gen.loc[:, "p_mw"] = dispatch
    stressed.line.loc[:, "max_i_ka"] *= capacity_scale
    return stressed


def _native_label(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def generate_scenarios(
    net: pandapowerNet,
    profiles: list[dict[str, Any]] | None = None,
    line_indices: list[int] | None = None,
    overload_threshold: float = 100.0,
    max_steps: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run deterministic profile/contingency combinations and build datasets."""
    selected_profiles = profiles if profiles is not None else DEFAULT_STRESS_PROFILES
    if not selected_profiles:
        raise ValueError("profiles must contain at least one stress profile")

    if line_indices is None:
        selected_lines = [
            _native_label(index)
            for index in net.line.index[
                net.line["in_service"].fillna(False).astype(bool)
            ].tolist()
        ]
    else:
        selected_lines = [_native_label(index) for index in line_indices]
    if not selected_lines:
        raise ValueError("line_indices must contain at least one line")

    for line_index in selected_lines:
        if line_index not in net.line.index:
            raise ValueError(f"Unknown line index: {line_index}")
        if not bool(net.line.at[line_index, "in_service"]):
            raise ValueError(f"Line {line_index} is not in service")

    summary_records: list[dict[str, Any]] = []
    detail_records: list[dict[str, Any]] = []

    for profile in selected_profiles:
        profile_name = str(profile["name"])
        is_synthetic_stress = bool(profile.get("is_synthetic_stress", True))
        load_scale = float(profile["load_scale"])
        generation_scale = float(profile["generation_scale"])
        capacity_scale = float(profile["capacity_scale"])
        stressed = stress_grid(
            net,
            load_scale=load_scale,
            generation_scale=generation_scale,
            capacity_scale=capacity_scale,
        )
        baseline = run_power_flow(stressed)
        if not baseline["converged"]:
            raise RuntimeError(
                f"Stress profile {profile_name!r} did not converge: "
                f"{baseline['error']}"
            )
        baseline_served = float(baseline["total_load_mw"])

        for line_index in selected_lines:
            scenario_id = f"{profile_name}-line-{line_index}"
            _, cascade = simulate_cascade(
                stressed,
                [line_index],
                overload_threshold=overload_threshold,
                max_steps=max_steps,
            )
            final_step = cascade["history"][-1]
            final_converged = bool(final_step["converged"])
            final_served = final_step["served_load_mw"] if final_converged else None
            load_lost = (
                max(0.0, baseline_served - float(final_served))
                if final_served is not None
                else None
            )
            load_served_percent = (
                100.0 * float(final_served) / baseline_served
                if final_served is not None and baseline_served > 0.0
                else None
            )
            initial_json = json.dumps([line_index])
            summary_records.append(
                {
                    "scenario_id": scenario_id,
                    "is_synthetic_stress": is_synthetic_stress,
                    "stress_profile": profile_name,
                    "load_scale": load_scale,
                    "generation_scale": generation_scale,
                    "capacity_scale": capacity_scale,
                    "initial_outages": initial_json,
                    "cascade_length": cascade["cascade_length"],
                    "failed_line_sequence": json.dumps(cascade["failure_sequence"]),
                    "total_failed_lines": len(cascade["failed_lines"]),
                    "initial_load_mw": baseline_served,
                    "baseline_served_load_mw": baseline_served,
                    "final_served_load_mw": final_served,
                    "load_lost_mw": load_lost,
                    "load_served_percent": load_served_percent,
                    "final_converged": final_converged,
                    "final_status": cascade["status"],
                    "final_max_loading_percent": (
                        final_step["max_line_loading_percent"]
                        if final_converged
                        else None
                    ),
                }
            )

            for step in cascade["history"]:
                detail_records.append(
                    {
                        "scenario_id": scenario_id,
                        "is_synthetic_stress": is_synthetic_stress,
                        "stress_profile": profile_name,
                        "load_scale": load_scale,
                        "generation_scale": generation_scale,
                        "capacity_scale": capacity_scale,
                        "initial_outages": initial_json,
                        "step": step["step"],
                        "failed_lines": json.dumps(step["failed_lines"]),
                        "newly_failed_lines": json.dumps(
                            step["newly_failed_lines"]
                        ),
                        "max_line_loading_percent": step[
                            "max_line_loading_percent"
                        ],
                        "overloaded_lines": json.dumps(step["overloaded_lines"]),
                        "min_bus_voltage_pu": step["min_bus_voltage_pu"],
                        "served_load_mw": step["served_load_mw"],
                        "total_generation_mw": step["total_generation_mw"],
                        "converged": step["converged"],
                        "error": step["error"],
                    }
                )

    return (
        pd.DataFrame(summary_records, columns=SUMMARY_COLUMNS),
        pd.DataFrame(detail_records, columns=DETAIL_COLUMNS),
    )


def save_scenario_results(
    summary: pd.DataFrame,
    steps: pd.DataFrame,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write scenario summary and step datasets to CSV files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "cascade_scenario_summary.csv"
    steps_path = output_path / "cascade_steps.csv"
    summary.to_csv(summary_path, index=False)
    steps.to_csv(steps_path, index=False)
    return summary_path, steps_path
