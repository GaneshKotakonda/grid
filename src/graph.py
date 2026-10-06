"""Convert solved pandapower networks into raw graph-learning samples."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from typing import Any

import numpy as np
from pandapower.auxiliary import pandapowerNet


NODE_FEATURE_NAMES = (
    "voltage_magnitude_pu",
    "voltage_angle_degree",
    "active_load_mw",
    "reactive_load_mvar",
    "active_generation_mw",
    "reactive_generation_mvar",
    "bus_in_service",
    "supplied",
)

EDGE_FEATURE_NAMES = (
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


@dataclass(frozen=True)
class GraphSample:
    """One fixed-schema supervised power-grid graph sample."""

    sample_id: str
    bus_indices: np.ndarray
    node_features: np.ndarray
    edge_index: np.ndarray
    edge_features: np.ndarray
    edge_line_indices: np.ndarray
    line_indices: np.ndarray
    target: np.ndarray


def _native_label(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def _finite_or_zero(value: Any) -> float:
    numeric = float(value)
    return numeric if np.isfinite(numeric) else 0.0


def _result_sum(
    net: pandapowerNet,
    element_name: str,
    result_name: str,
    bus: Any,
    column: str,
) -> float:
    elements = getattr(net, element_name)
    results = getattr(net, result_name)
    if elements.empty or results.empty or column not in results:
        return 0.0
    active = elements["in_service"].fillna(False).astype(bool)
    indices = elements.index[active & (elements["bus"] == bus)]
    values = results[column].reindex(indices)
    return float(values.replace([np.inf, -np.inf], np.nan).fillna(0.0).sum())


def make_target(
    line_indices: np.ndarray,
    next_failed_lines: Iterable[int],
) -> np.ndarray:
    """Create a physical-line-ordered multi-label next-failure target."""
    labels = [_native_label(value) for value in line_indices.tolist()]
    positions = {label: position for position, label in enumerate(labels)}
    target = np.zeros(len(labels), dtype=np.uint8)
    for line_index in next_failed_lines:
        native_index = _native_label(line_index)
        if native_index not in positions:
            raise ValueError(f"Unknown target line index: {native_index}")
        target[positions[native_index]] = 1
    return target


def network_to_graph(
    net: pandapowerNet,
    sample_id: str,
    next_failed_lines: Iterable[int],
) -> GraphSample:
    """Convert a solved network to finite raw node/edge arrays and a target."""
    if not bool(net.get("converged", False)):
        raise ValueError("network must have a converged power-flow solution")

    bus_indices = np.asarray(
        sorted(_native_label(index) for index in net.bus.index.tolist()),
        dtype=np.int64,
    )
    bus_positions = {
        bus_index: position for position, bus_index in enumerate(bus_indices.tolist())
    }
    node_features = np.zeros(
        (len(bus_indices), len(NODE_FEATURE_NAMES)),
        dtype=np.float32,
    )

    for position, bus_index in enumerate(bus_indices.tolist()):
        bus_in_service = bool(net.bus.at[bus_index, "in_service"])
        voltage = net.res_bus.at[bus_index, "vm_pu"]
        angle = net.res_bus.at[bus_index, "va_degree"]
        supplied = bus_in_service and bool(np.isfinite(voltage))
        node_features[position] = [
            _finite_or_zero(voltage),
            _finite_or_zero(angle),
            _result_sum(net, "load", "res_load", bus_index, "p_mw"),
            _result_sum(net, "load", "res_load", bus_index, "q_mvar"),
            _result_sum(net, "gen", "res_gen", bus_index, "p_mw")
            + _result_sum(net, "ext_grid", "res_ext_grid", bus_index, "p_mw"),
            _result_sum(net, "gen", "res_gen", bus_index, "q_mvar")
            + _result_sum(net, "ext_grid", "res_ext_grid", bus_index, "q_mvar"),
            float(bus_in_service),
            float(supplied),
        ]

    line_indices = np.asarray(
        sorted(_native_label(index) for index in net.line.index.tolist()),
        dtype=np.int64,
    )
    edge_index_rows: list[tuple[int, int]] = []
    edge_feature_rows: list[list[float]] = []
    edge_line_indices: list[int] = []

    for line_index in line_indices.tolist():
        line = net.line.loc[line_index]
        from_bus = _native_label(line["from_bus"])
        to_bus = _native_label(line["to_bus"])
        in_service = bool(line["in_service"])
        result = net.res_line.loc[line_index]
        loading = _finite_or_zero(result["loading_percent"]) if in_service else 0.0
        shared = [
            loading,
            _finite_or_zero(line["r_ohm_per_km"]),
            _finite_or_zero(line["x_ohm_per_km"]),
            float(in_service),
            _finite_or_zero(line["max_i_ka"]),
            _finite_or_zero(line["length_km"]),
            _finite_or_zero(line["max_loading_percent"]),
        ]
        directions = (
            (
                from_bus,
                to_bus,
                _finite_or_zero(result["p_from_mw"]) if in_service else 0.0,
                _finite_or_zero(result["q_from_mvar"]) if in_service else 0.0,
            ),
            (
                to_bus,
                from_bus,
                _finite_or_zero(result["p_to_mw"]) if in_service else 0.0,
                _finite_or_zero(result["q_to_mvar"]) if in_service else 0.0,
            ),
        )
        for source, destination, active_power, reactive_power in directions:
            edge_index_rows.append(
                (bus_positions[source], bus_positions[destination])
            )
            edge_feature_rows.append(
                [
                    float(source),
                    float(destination),
                    active_power,
                    reactive_power,
                    *shared,
                ]
            )
            edge_line_indices.append(line_index)

    sample = GraphSample(
        sample_id=str(sample_id),
        bus_indices=bus_indices,
        node_features=node_features,
        edge_index=np.asarray(edge_index_rows, dtype=np.int64).T,
        edge_features=np.asarray(edge_feature_rows, dtype=np.float32),
        edge_line_indices=np.asarray(edge_line_indices, dtype=np.int64),
        line_indices=line_indices,
        target=make_target(line_indices, next_failed_lines),
    )
    validate_graph_sample(sample)
    return sample


def _metadata_list(metadata: Mapping[str, Any], key: str) -> list[int]:
    value = metadata.get(key, [])
    parsed = json.loads(value) if isinstance(value, str) else value
    return [_native_label(item) for item in parsed]


def validate_graph_sample(
    sample: GraphSample,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Reject malformed, non-finite, or metadata-inconsistent graph samples."""
    node_count = len(sample.bus_indices)
    line_count = len(sample.line_indices)
    directed_edge_count = 2 * line_count
    expected_shapes = {
        "node features": (node_count, len(NODE_FEATURE_NAMES)),
        "edge index": (2, directed_edge_count),
        "edge features": (directed_edge_count, len(EDGE_FEATURE_NAMES)),
        "edge-line indices": (directed_edge_count,),
        "target": (line_count,),
    }
    arrays = {
        "node features": sample.node_features,
        "edge index": sample.edge_index,
        "edge features": sample.edge_features,
        "edge-line indices": sample.edge_line_indices,
        "target": sample.target,
    }
    for name, expected_shape in expected_shapes.items():
        if arrays[name].shape != expected_shape:
            raise ValueError(
                f"{sample.sample_id}: {name} shape {arrays[name].shape} "
                f"does not match {expected_shape}"
            )
    for name in ("node features", "edge features"):
        if not np.isfinite(arrays[name]).all():
            raise ValueError(f"{sample.sample_id}: {name} contain NaN or Inf")
    if not np.isin(sample.target, [0, 1]).all():
        raise ValueError(f"{sample.sample_id}: target must be binary")
    for line_index in sample.line_indices.tolist():
        if int(np.count_nonzero(sample.edge_line_indices == line_index)) != 2:
            raise ValueError(
                f"{sample.sample_id}: line {line_index} must map to two edges"
            )

    status_column = EDGE_FEATURE_NAMES.index("in_service")
    if not np.isin(sample.edge_features[:, status_column], [0.0, 1.0]).all():
        raise ValueError(f"{sample.sample_id}: line status must be binary")

    if metadata is None:
        return
    current_failed = _metadata_list(metadata, "current_failed_lines")
    for line_index in current_failed:
        edges = sample.edge_line_indices == line_index
        if not edges.any() or np.any(sample.edge_features[edges, status_column] != 0.0):
            raise ValueError(
                f"{sample.sample_id}: failed line {line_index} is not out of service"
            )
    expected_target = make_target(
        sample.line_indices,
        _metadata_list(metadata, "next_failed_lines"),
    )
    if not np.array_equal(sample.target, expected_target):
        raise ValueError(f"{sample.sample_id}: target does not match next failures")
