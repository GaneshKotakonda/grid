"""Extract and compare power-flow metrics."""

from typing import Any

import numpy as np
import pandas as pd
from pandapower.auxiliary import pandapowerNet


LINE_COLUMNS = [
    "line_index",
    "from_bus",
    "to_bus",
    "in_service",
    "active_power_mw",
    "loading_percent",
]
BUS_COLUMNS = ["bus_index", "voltage_pu", "supplied"]


def _empty_lines() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "line_index": pd.Series(dtype="int64"),
            "from_bus": pd.Series(dtype="int64"),
            "to_bus": pd.Series(dtype="int64"),
            "in_service": pd.Series(dtype="bool"),
            "active_power_mw": pd.Series(dtype="float64"),
            "loading_percent": pd.Series(dtype="float64"),
        }
    )


def _empty_buses() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bus_index": pd.Series(dtype="int64"),
            "voltage_pu": pd.Series(dtype="float64"),
            "supplied": pd.Series(dtype="bool"),
        }
    )


def _sum_result_column(net: pandapowerNet, table_name: str) -> float:
    table = getattr(net, table_name, None)
    if table is None or table.empty or "p_mw" not in table:
        return 0.0
    return float(table["p_mw"].sum())


def extract_grid_metrics(net: pandapowerNet) -> dict[str, Any]:
    """Extract line, bus, load, and generation metrics from a solved network."""
    lines = net.line.loc[:, ["from_bus", "to_bus", "in_service"]].copy()
    lines["in_service"] = lines["in_service"].fillna(False).astype(bool)
    lines["active_power_mw"] = net.res_line["p_from_mw"].reindex(lines.index)
    lines["loading_percent"] = net.res_line["loading_percent"].reindex(lines.index)
    lines = lines.rename_axis("line_index").reset_index().loc[:, LINE_COLUMNS]

    voltage = net.res_bus["vm_pu"].reindex(net.bus.index)
    bus_in_service = net.bus["in_service"].fillna(False).astype(bool)
    supplied = bus_in_service & np.isfinite(voltage)
    buses = pd.DataFrame(
        {"voltage_pu": voltage, "supplied": supplied},
        index=net.bus.index,
    )
    buses = buses.rename_axis("bus_index").reset_index().loc[:, BUS_COLUMNS]

    load_in_service = net.load["in_service"].fillna(False).astype(bool)
    load_bus_supplied = net.load["bus"].map(supplied).fillna(False).astype(bool)
    solved_load = net.res_load["p_mw"].reindex(net.load.index)
    served_load = solved_load.loc[load_in_service & load_bus_supplied].sum()

    active_loading = lines.loc[
        lines["in_service"] & lines["loading_percent"].notna(),
        "loading_percent",
    ]
    supplied_voltage = buses.loc[buses["supplied"], "voltage_pu"]
    overloaded = lines.loc[
        lines["in_service"] & (lines["loading_percent"] > 100.0),
        "line_index",
    ].tolist()

    return {
        "converged": True,
        "error": None,
        "lines": lines,
        "buses": buses,
        "total_load_mw": float(served_load),
        "total_generation_mw": _sum_result_column(net, "res_gen")
        + _sum_result_column(net, "res_ext_grid"),
        "max_line_loading_percent": (
            float(active_loading.max()) if not active_loading.empty else None
        ),
        "min_bus_voltage_pu": (
            float(supplied_voltage.min()) if not supplied_voltage.empty else None
        ),
        "overloaded_lines": overloaded,
    }


def failed_grid_metrics(error: str) -> dict[str, Any]:
    """Return a stable metric schema for a failed power-flow solve."""
    return {
        "converged": False,
        "error": error,
        "lines": _empty_lines(),
        "buses": _empty_buses(),
        "total_load_mw": None,
        "total_generation_mw": None,
        "max_line_loading_percent": None,
        "min_bus_voltage_pu": None,
        "overloaded_lines": [],
    }


def compare_grid_states(
    baseline: dict[str, Any],
    outage: dict[str, Any],
) -> dict[str, Any]:
    """Compare line loading, bus voltage, and aggregate solved-state metrics."""
    before_lines = baseline["lines"].rename(
        columns={
            "in_service": "in_service_before",
            "active_power_mw": "active_power_mw_before",
            "loading_percent": "loading_percent_before",
        }
    )
    after_lines = outage["lines"].loc[
        :, ["line_index", "in_service", "active_power_mw", "loading_percent"]
    ].rename(
        columns={
            "in_service": "in_service_after",
            "active_power_mw": "active_power_mw_after",
            "loading_percent": "loading_percent_after",
        }
    )
    lines = before_lines.merge(after_lines, on="line_index", how="outer")
    lines["loading_change_percent"] = (
        lines["loading_percent_after"] - lines["loading_percent_before"]
    )
    lines = lines.sort_values("line_index").reset_index(drop=True)
    lines = lines.loc[
        :,
        [
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
        ],
    ]

    before_buses = baseline["buses"].rename(
        columns={
            "voltage_pu": "voltage_pu_before",
            "supplied": "supplied_before",
        }
    )
    after_buses = outage["buses"].rename(
        columns={
            "voltage_pu": "voltage_pu_after",
            "supplied": "supplied_after",
        }
    )
    buses = before_buses.merge(after_buses, on="bus_index", how="outer")
    buses["voltage_change_pu"] = (
        buses["voltage_pu_after"] - buses["voltage_pu_before"]
    )
    buses = buses.sort_values("bus_index").reset_index(drop=True)
    buses = buses.loc[
        :,
        [
            "bus_index",
            "supplied_before",
            "supplied_after",
            "voltage_pu_before",
            "voltage_pu_after",
            "voltage_change_pu",
        ],
    ]

    baseline_converged = bool(baseline["converged"])
    outage_converged = bool(outage["converged"])
    return {
        "lines": lines,
        "buses": buses,
        "baseline_converged": baseline_converged,
        "outage_converged": outage_converged,
        "max_line_loading_before": baseline["max_line_loading_percent"],
        "max_line_loading_after": outage["max_line_loading_percent"],
        "min_bus_voltage_before": baseline["min_bus_voltage_pu"],
        "min_bus_voltage_after": outage["min_bus_voltage_pu"],
        "total_served_load_before": baseline["total_load_mw"],
        "total_served_load_after": outage["total_load_mw"],
        "overloaded_lines_before": (
            baseline["overloaded_lines"] if baseline_converged else None
        ),
        "overloaded_lines_after": (
            outage["overloaded_lines"] if outage_converged else None
        ),
    }
