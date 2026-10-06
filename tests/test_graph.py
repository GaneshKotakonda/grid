"""Tests for converting solved power-grid states into graph samples."""

from dataclasses import replace

import numpy as np
import pytest

from src.graph import (
    EDGE_FEATURE_NAMES,
    NODE_FEATURE_NAMES,
    make_target,
    network_to_graph,
    validate_graph_sample,
)
from src.grid_loader import load_ieee14
from src.simulator import run_power_flow, simulate_line_outage


pytestmark = pytest.mark.filterwarnings(
    "ignore:tap_dependency_table is missing in net.*:DeprecationWarning"
)


def _solved_ieee14():
    net = load_ieee14()
    assert run_power_flow(net)["converged"] is True
    return net


def test_graph_conversion_contains_raw_node_and_edge_features() -> None:
    net = _solved_ieee14()

    sample = network_to_graph(net, "sample-0", [2, 6])

    assert NODE_FEATURE_NAMES == (
        "voltage_magnitude_pu",
        "voltage_angle_degree",
        "active_load_mw",
        "reactive_load_mvar",
        "active_generation_mw",
        "reactive_generation_mvar",
        "bus_in_service",
        "supplied",
    )
    assert EDGE_FEATURE_NAMES == (
        "from_bus",
        "to_bus",
        "active_power_mw",
        "reactive_power_mvar",
        "loading_percent",
        "resistance_ohm_per_km",
        "reactance_ohm_per_km",
        "in_service",
        "max_current_ka",
        "length_km",
        "max_loading_percent",
    )
    assert sample.sample_id == "sample-0"
    assert sample.node_features.shape == (14, 8)
    assert sample.edge_index.shape == (2, 30)
    assert sample.edge_features.shape == (30, 11)
    assert sample.edge_line_indices.shape == (30,)
    assert sample.line_indices.tolist() == list(range(15))
    assert sample.target.shape == (15,)
    assert np.flatnonzero(sample.target).tolist() == [2, 6]
    assert np.isfinite(sample.node_features).all()
    assert np.isfinite(sample.edge_features).all()

    bus_position = sample.bus_indices.tolist().index(1)
    bus_loads = net.load.index[net.load["bus"] == 1]
    bus_generators = net.gen.index[net.gen["bus"] == 1]
    assert sample.node_features[bus_position, 0] == pytest.approx(
        net.res_bus.at[1, "vm_pu"]
    )
    assert sample.node_features[bus_position, 1] == pytest.approx(
        net.res_bus.at[1, "va_degree"]
    )
    assert sample.node_features[bus_position, 2] == pytest.approx(
        net.res_load.loc[bus_loads, "p_mw"].sum()
    )
    assert sample.node_features[bus_position, 3] == pytest.approx(
        net.res_load.loc[bus_loads, "q_mvar"].sum()
    )
    assert sample.node_features[bus_position, 4] == pytest.approx(
        net.res_gen.loc[bus_generators, "p_mw"].sum()
    )
    assert sample.node_features[bus_position, 5] == pytest.approx(
        net.res_gen.loc[bus_generators, "q_mvar"].sum()
    )
    assert sample.node_features[bus_position, 6:].tolist() == [1.0, 1.0]

    line = net.line.loc[0]
    assert sample.edge_line_indices[:2].tolist() == [0, 0]
    assert sample.edge_index[:, 0].tolist() == [line.from_bus, line.to_bus]
    assert sample.edge_index[:, 1].tolist() == [line.to_bus, line.from_bus]
    assert sample.edge_features[0, 2] == pytest.approx(
        net.res_line.at[0, "p_from_mw"]
    )
    assert sample.edge_features[1, 2] == pytest.approx(
        net.res_line.at[0, "p_to_mw"]
    )
    assert sample.edge_features[0, 5] == pytest.approx(line.r_ohm_per_km)
    assert sample.edge_features[0, 6] == pytest.approx(line.x_ohm_per_km)
    assert sample.edge_features[0, 8] == pytest.approx(line.max_i_ka)


def test_target_uses_explicit_sorted_line_mapping() -> None:
    line_indices = np.array([10, 30, 50], dtype=np.int64)

    target = make_target(line_indices, [50, 10])

    assert target.dtype == np.uint8
    assert target.tolist() == [1, 0, 1]


def test_stable_target_is_all_zero() -> None:
    target = make_target(np.array([4, 8, 12], dtype=np.int64), [])

    assert target.tolist() == [0, 0, 0]


def test_failed_line_remains_finite_and_out_of_service() -> None:
    outage_net, metrics = simulate_line_outage(load_ieee14(), 0)
    assert metrics["converged"] is True

    sample = network_to_graph(outage_net, "failed-line", [])

    failed_edges = sample.edge_line_indices == 0
    assert failed_edges.sum() == 2
    assert sample.edge_features[failed_edges, 2:5].tolist() == [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ]
    assert sample.edge_features[failed_edges, 7].tolist() == [0.0, 0.0]
    assert np.isfinite(sample.edge_features[failed_edges]).all()
    validate_graph_sample(
        sample,
        {"current_failed_lines": "[0]", "next_failed_lines": "[]"},
    )


def test_graph_validation_rejects_nan_features() -> None:
    sample = network_to_graph(_solved_ieee14(), "nan-sample", [])
    invalid_nodes = sample.node_features.copy()
    invalid_nodes[0, 0] = np.nan
    invalid = replace(sample, node_features=invalid_nodes)

    with pytest.raises(ValueError, match="nan-sample.*node features"):
        validate_graph_sample(invalid)
