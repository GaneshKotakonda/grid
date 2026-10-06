"""Deterministic overload-driven cascading-failure simulation."""

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from pandapower.auxiliary import pandapowerNet

from src.simulator import run_power_flow


SIGNIFICANT_LOAD_LOSS_PERCENT = 1.0
BLACKOUT_ABSOLUTE_TOLERANCE_MW = 1e-6
BLACKOUT_RELATIVE_TOLERANCE = 1e-6


def _native_label(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def _initial_load_mw(net: pandapowerNet) -> float:
    in_service = net.load["in_service"].fillna(False).astype(bool)
    return float(net.load.loc[in_service, "p_mw"].sum())


def _load_outcome(
    initial_load_mw: float,
    final_served_load_mw: float | None,
) -> tuple[float | None, float | None]:
    if final_served_load_mw is None:
        return None, None

    load_lost_mw = max(0.0, initial_load_mw - final_served_load_mw)
    load_served_percent = (
        100.0 * final_served_load_mw / initial_load_mw
        if initial_load_mw > BLACKOUT_ABSOLUTE_TOLERANCE_MW
        else None
    )
    return load_lost_mw, load_served_percent


def _load_based_status(
    initial_load_mw: float,
    final_served_load_mw: float,
    load_served_percent: float | None,
) -> str:
    blackout_tolerance = max(
        BLACKOUT_ABSOLUTE_TOLERANCE_MW,
        initial_load_mw * BLACKOUT_RELATIVE_TOLERANCE,
    )
    if (
        initial_load_mw > blackout_tolerance
        and final_served_load_mw <= blackout_tolerance
    ):
        return "TOTAL_BLACKOUT"
    if (
        load_served_percent is not None
        and load_served_percent < 100.0 - SIGNIFICANT_LOAD_LOSS_PERCENT
    ):
        return "PARTIAL_BLACKOUT"
    return "STABLE"


def find_overloaded_lines(
    metrics: dict[str, Any],
    overload_threshold: float = 100.0,
) -> list[int]:
    """Return sorted in-service lines loaded strictly above the threshold."""
    if overload_threshold <= 0:
        raise ValueError("overload_threshold must be positive")

    lines = metrics["lines"]
    if lines.empty:
        return []
    overloaded = lines.loc[
        lines["in_service"].fillna(False).astype(bool)
        & (lines["loading_percent"] > overload_threshold),
        "line_index",
    ]
    return sorted(_native_label(index) for index in overloaded.tolist())


def _normalize_initial_outages(
    net: pandapowerNet,
    initial_outages: Iterable[int],
) -> list[int]:
    normalized: list[int] = []
    seen: set[Any] = set()
    for line_index in initial_outages:
        native_index = _native_label(line_index)
        if native_index not in seen:
            normalized.append(native_index)
            seen.add(native_index)

    if not normalized:
        raise ValueError("initial_outages must contain at least one line")

    unknown = [index for index in normalized if index not in net.line.index]
    if unknown:
        raise ValueError(f"Unknown line index: {unknown[0]}")
    return normalized


def simulate_cascade(
    net: pandapowerNet,
    initial_outages: Iterable[int],
    overload_threshold: float = 100.0,
    max_steps: int = 20,
    capture_network_states: bool = False,
) -> tuple[pandapowerNet, dict[str, Any]]:
    """Apply an initiating outage and propagate overload-driven trip waves."""
    if overload_threshold <= 0:
        raise ValueError("overload_threshold must be positive")
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 0:
        raise ValueError("max_steps must be a non-negative integer")

    normalized_outages = _normalize_initial_outages(net, initial_outages)
    initial_load_mw = _initial_load_mw(net)
    cascade_net = deepcopy(net)
    failure_sequence: list[list[int]] = [normalized_outages]
    failed_lines: list[int] = []
    history: list[dict[str, Any]] = []
    step = 0

    while True:
        newly_failed = failure_sequence[-1]
        for line_index in newly_failed:
            cascade_net.line.at[line_index, "in_service"] = False
            if line_index not in failed_lines:
                failed_lines.append(line_index)

        metrics = run_power_flow(cascade_net)
        overloaded_lines = (
            find_overloaded_lines(metrics, overload_threshold)
            if metrics["converged"]
            else []
        )
        history_record = {
            "step": step,
            "failed_lines": list(failed_lines),
            "newly_failed_lines": list(newly_failed),
            "max_line_loading_percent": metrics["max_line_loading_percent"],
            "overloaded_lines": overloaded_lines,
            "min_bus_voltage_pu": metrics["min_bus_voltage_pu"],
            "served_load_mw": metrics["total_load_mw"],
            "total_generation_mw": metrics["total_generation_mw"],
            "converged": bool(metrics["converged"]),
            "error": metrics["error"],
        }
        if capture_network_states and metrics["converged"]:
            history_record["network_state"] = deepcopy(cascade_net)
        history.append(history_record)

        if not metrics["converged"]:
            status = "NON_CONVERGED"
            break
        if not overloaded_lines:
            final_served_load_mw = float(metrics["total_load_mw"])
            _, load_served_percent = _load_outcome(
                initial_load_mw,
                final_served_load_mw,
            )
            status = _load_based_status(
                initial_load_mw,
                final_served_load_mw,
                load_served_percent,
            )
            break
        if step >= max_steps:
            status = "MAX_STEPS_REACHED"
            break

        failure_sequence.append(overloaded_lines)
        step += 1

    final_step = history[-1]
    final_served_load_mw = (
        float(final_step["served_load_mw"])
        if final_step["converged"] and final_step["served_load_mw"] is not None
        else None
    )
    load_lost_mw, load_served_percent = _load_outcome(
        initial_load_mw,
        final_served_load_mw,
    )
    result = {
        "status": status,
        "final_status": status,
        "initial_outages": list(normalized_outages),
        "failed_lines": list(failed_lines),
        "failure_sequence": [list(wave) for wave in failure_sequence],
        "initial_load_mw": initial_load_mw,
        "final_served_load_mw": final_served_load_mw,
        "load_lost_mw": load_lost_mw,
        "load_served_percent": load_served_percent,
        "total_failed_lines": len(failed_lines),
        "cascade_length": len(failure_sequence) - 1,
        "overload_threshold": float(overload_threshold),
        "max_steps": max_steps,
        "history": history,
    }
    return cascade_net, result
