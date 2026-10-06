"""Run baseline and single-line-outage power-flow simulations."""

from copy import deepcopy
from typing import Any

import pandapower as pp
from pandapower.auxiliary import pandapowerNet
from pandapower.powerflow import LoadflowNotConverged

from src.metrics import extract_grid_metrics, failed_grid_metrics


def run_power_flow(net: pandapowerNet) -> dict[str, Any]:
    """Solve a network and return metrics with explicit convergence status."""
    try:
        pp.runpp(net, numba=False)
    except LoadflowNotConverged as error:
        return failed_grid_metrics(str(error))
    return extract_grid_metrics(net)


def simulate_line_outage(
    net: pandapowerNet,
    line_index: int,
) -> tuple[pandapowerNet, dict[str, Any]]:
    """Disconnect one line on a deep copy, solve it, and preserve the input."""
    if line_index not in net.line.index:
        raise ValueError(f"Unknown line index: {line_index}")

    outage_net = deepcopy(net)
    outage_net.line.at[line_index, "in_service"] = False
    metrics = run_power_flow(outage_net)
    return outage_net, metrics
