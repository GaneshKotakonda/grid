"""Generate reproducible supervised graph samples from cascade simulations."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
from pandapower.auxiliary import pandapowerNet

from src.cascade import simulate_cascade
from src.graph import (
    EDGE_FEATURE_NAMES,
    NODE_FEATURE_NAMES,
    GraphSample,
    network_to_graph,
    validate_graph_sample,
)
from src.scenarios import stress_grid
from src.simulator import run_power_flow


METADATA_COLUMNS = [
    "sample_id",
    "scenario_id",
    "cascade_step",
    "random_seed",
    "load_scale",
    "generation_scale",
    "capacity_scale",
    "load_multipliers",
    "reactive_load_multipliers",
    "generator_dispatch_mw",
    "initial_outages",
    "current_failed_lines",
    "next_failed_lines",
    "final_status",
    "is_synthetic_stress",
    "split",
]

SCENARIO_COLUMNS = [
    "scenario_id",
    "random_seed",
    "load_scale",
    "generation_scale",
    "capacity_scale",
    "load_multipliers",
    "reactive_load_multipliers",
    "generator_dispatch_mw",
    "initial_outages",
    "final_status",
    "is_synthetic_stress",
    "split",
    "graph_samples",
]


@dataclass
class DatasetBuild:
    """In-memory Phase 3 dataset and its scenario/sample metadata."""

    samples: list[GraphSample]
    metadata: pd.DataFrame
    scenarios: pd.DataFrame
    line_indices: np.ndarray
    config: dict[str, Any]
    generation_seconds: float


def assign_scenario_splits(
    scenario_ids: Sequence[str],
    seed: int,
) -> dict[str, str]:
    """Deterministically assign whole scenarios to 70/15/15 splits."""
    normalized = [str(scenario_id) for scenario_id in scenario_ids]
    if len(set(normalized)) != len(normalized):
        raise ValueError("scenario_ids must be unique")
    if not normalized:
        return {}

    shuffled = np.asarray(normalized, dtype=str)
    np.random.default_rng(seed).shuffle(shuffled)
    count = len(shuffled)
    if count >= 3:
        train_count = max(1, int(count * 0.70))
        validation_count = max(1, int(count * 0.15))
        if train_count + validation_count > count - 1:
            train_count = count - validation_count - 1
    elif count == 2:
        train_count, validation_count = 1, 0
    else:
        train_count, validation_count = 1, 0

    assignments: dict[str, str] = {}
    for position, scenario_id in enumerate(shuffled.tolist()):
        if position < train_count:
            split = "train"
        elif position < train_count + validation_count:
            split = "validation"
        else:
            split = "test"
        assignments[scenario_id] = split
    return assignments


def _as_list(value: Any) -> list[int]:
    parsed = json.loads(value) if isinstance(value, str) else value
    return [item.item() if hasattr(item, "item") else item for item in parsed]


def extract_cascade_samples(
    cascade: Mapping[str, Any],
    scenario_metadata: Mapping[str, Any],
    split: str,
) -> tuple[list[GraphSample], list[dict[str, Any]]]:
    """Convert eligible solved cascade states into next-wave samples."""
    if split not in {"train", "validation", "test"}:
        raise ValueError(f"Unknown split: {split}")

    history = list(cascade["history"])
    samples: list[GraphSample] = []
    records: list[dict[str, Any]] = []
    scenario_id = str(scenario_metadata["scenario_id"])
    initial_outages = _as_list(scenario_metadata["initial_outages"])

    for position, step in enumerate(history):
        if not step["converged"] or "network_state" not in step:
            continue
        if position + 1 < len(history):
            next_step_failures = history[position + 1]["newly_failed_lines"]
            next_failed_lines = list(next_step_failures)
            if initial_outages and set(initial_outages).intersection(next_failed_lines):
                raise ValueError(
                    f"{scenario_id}: initial outage appears as a secondary failure"
                )
        elif step["overloaded_lines"]:
            # The cap prevented an observed next trip wave, so this is neither
            # a positive observation nor a stable negative.
            continue
        else:
            next_failed_lines = []

        cascade_step = int(step["step"])
        sample_id = f"{scenario_id}-step-{cascade_step:02d}"
        sample = network_to_graph(
            step["network_state"],
            sample_id,
            next_failed_lines,
        )
        record = {
            "sample_id": sample_id,
            "scenario_id": scenario_id,
            "cascade_step": cascade_step,
            "random_seed": int(scenario_metadata["random_seed"]),
            "load_scale": float(scenario_metadata["load_scale"]),
            "generation_scale": float(scenario_metadata["generation_scale"]),
            "capacity_scale": float(scenario_metadata["capacity_scale"]),
            "load_multipliers": str(scenario_metadata["load_multipliers"]),
            "reactive_load_multipliers": str(
                scenario_metadata["reactive_load_multipliers"]
            ),
            "generator_dispatch_mw": str(scenario_metadata["generator_dispatch_mw"]),
            "initial_outages": json.dumps(initial_outages),
            "current_failed_lines": json.dumps(list(step["failed_lines"])),
            "next_failed_lines": json.dumps(next_failed_lines),
            "final_status": str(
                scenario_metadata.get("final_status", cascade["status"])
            ),
            "is_synthetic_stress": bool(
                scenario_metadata.get("is_synthetic_stress", True)
            ),
            "split": split,
        }
        validate_graph_sample(sample, record)
        samples.append(sample)
        records.append(record)

    return samples, records


def _validate_range(name: str, value: tuple[float, float]) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two values")
    lower, upper = (float(value[0]), float(value[1]))
    if lower <= 0.0 or upper <= 0.0 or lower > upper:
        raise ValueError(f"{name} must be positive and ordered")
    return lower, upper


def generate_gnn_dataset(
    net: pandapowerNet,
    scenario_count: int,
    seed: int,
    load_scale_range: tuple[float, float] = (0.8, 1.5),
    generation_scale_range: tuple[float, float] = (0.9, 1.1),
    capacity_scale_range: tuple[float, float] = (0.000005, 0.02),
    overload_threshold: float = 100.0,
    max_steps: int = 20,
    max_initial_outages: int = 2,
    multiple_outage_probability: float = 0.2,
    load_variation_range: tuple[float, float] = (0.8, 1.2),
    reactive_load_variation_range: tuple[float, float] = (0.9, 1.1),
    generator_dispatch_variation_range: tuple[float, float] = (0.8, 1.2),
) -> DatasetBuild:
    """Generate deterministic synthetic cascades and graph samples."""
    if (
        not isinstance(scenario_count, int)
        or isinstance(scenario_count, bool)
        or scenario_count <= 0
    ):
        raise ValueError("scenario_count must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    load_range = _validate_range("load_scale_range", load_scale_range)
    generation_range = _validate_range(
        "generation_scale_range",
        generation_scale_range,
    )
    capacity_range = _validate_range("capacity_scale_range", capacity_scale_range)
    load_variation = _validate_range("load_variation_range", load_variation_range)
    reactive_variation = _validate_range(
        "reactive_load_variation_range", reactive_load_variation_range
    )
    dispatch_variation = _validate_range(
        "generator_dispatch_variation_range", generator_dispatch_variation_range
    )
    if not 0.0 <= multiple_outage_probability <= 1.0:
        raise ValueError("multiple_outage_probability must be between 0 and 1")

    in_service_lines = sorted(
        index.item() if hasattr(index, "item") else index
        for index in net.line.index[
            net.line["in_service"].fillna(False).astype(bool)
        ].tolist()
    )
    if (
        not isinstance(max_initial_outages, int)
        or isinstance(max_initial_outages, bool)
        or not 1 <= max_initial_outages <= len(in_service_lines)
    ):
        raise ValueError(
            "max_initial_outages must be between 1 and the in-service line count"
        )

    scenario_ids = [f"scenario-{index:06d}" for index in range(scenario_count)]
    split_assignments = assign_scenario_splits(scenario_ids, seed)
    root_rng = np.random.default_rng(seed)
    scenario_seeds = root_rng.integers(
        0,
        2**32,
        size=scenario_count,
        dtype=np.uint64,
    )

    samples: list[GraphSample] = []
    metadata_records: list[dict[str, Any]] = []
    scenario_records: list[dict[str, Any]] = []
    started = time.perf_counter()

    for scenario_id, raw_scenario_seed in zip(
        scenario_ids,
        scenario_seeds.tolist(),
        strict=True,
    ):
        scenario_seed = int(raw_scenario_seed)
        scenario_rng = np.random.default_rng(scenario_seed)
        load_scale = float(scenario_rng.uniform(*load_range))
        generation_scale = float(scenario_rng.uniform(*generation_range))
        capacity_scale = float(scenario_rng.uniform(*capacity_range))
        load_multipliers = scenario_rng.uniform(
            *load_variation, size=len(net.load)
        ).tolist()
        reactive_load_multipliers = scenario_rng.uniform(
            *reactive_variation, size=len(net.load)
        ).tolist()
        dispatch_factors = scenario_rng.uniform(
            *dispatch_variation, size=len(net.gen)
        )
        generator_dispatch_mw = (
            net.gen["p_mw"].to_numpy(dtype=float)
            * generation_scale
            * dispatch_factors
        )
        if "min_p_mw" in net.gen:
            generator_dispatch_mw = np.maximum(
                generator_dispatch_mw, net.gen["min_p_mw"].to_numpy(dtype=float)
            )
        if "max_p_mw" in net.gen:
            generator_dispatch_mw = np.minimum(
                generator_dispatch_mw, net.gen["max_p_mw"].to_numpy(dtype=float)
            )
        generator_dispatch_mw_list = generator_dispatch_mw.tolist()
        outage_count = 1
        if (
            max_initial_outages > 1
            and scenario_rng.random() < multiple_outage_probability
        ):
            outage_count = int(scenario_rng.integers(2, max_initial_outages + 1))
        initial_outages = sorted(
            int(value)
            for value in scenario_rng.choice(
                in_service_lines,
                size=outage_count,
                replace=False,
            ).tolist()
        )
        split = split_assignments[scenario_id]
        stressed = stress_grid(
            net,
            load_scale=load_scale,
            generation_scale=generation_scale,
            capacity_scale=capacity_scale,
            load_multipliers=load_multipliers,
            reactive_load_multipliers=reactive_load_multipliers,
            generator_dispatch_mw=generator_dispatch_mw_list,
        )
        baseline = run_power_flow(stressed)
        scenario_context: dict[str, Any] = {
            "scenario_id": scenario_id,
            "random_seed": scenario_seed,
            "load_scale": load_scale,
            "generation_scale": generation_scale,
            "capacity_scale": capacity_scale,
            "load_multipliers": json.dumps(load_multipliers),
            "reactive_load_multipliers": json.dumps(reactive_load_multipliers),
            "generator_dispatch_mw": json.dumps(generator_dispatch_mw_list),
            "initial_outages": initial_outages,
            "is_synthetic_stress": True,
        }

        if not baseline["converged"]:
            final_status = "BASELINE_NON_CONVERGED"
            scenario_samples: list[GraphSample] = []
            scenario_metadata_records: list[dict[str, Any]] = []
        else:
            _, cascade = simulate_cascade(
                stressed,
                initial_outages,
                overload_threshold=overload_threshold,
                max_steps=max_steps,
                capture_network_states=True,
            )
            final_status = str(cascade["status"])
            scenario_context["final_status"] = final_status
            scenario_samples, scenario_metadata_records = extract_cascade_samples(
                cascade,
                scenario_context,
                split,
            )

        samples.extend(scenario_samples)
        metadata_records.extend(scenario_metadata_records)
        scenario_records.append(
            {
                "scenario_id": scenario_id,
                "random_seed": scenario_seed,
                "load_scale": load_scale,
                "generation_scale": generation_scale,
                "capacity_scale": capacity_scale,
                "load_multipliers": json.dumps(load_multipliers),
                "reactive_load_multipliers": json.dumps(reactive_load_multipliers),
                "generator_dispatch_mw": json.dumps(generator_dispatch_mw_list),
                "initial_outages": json.dumps(initial_outages),
                "final_status": final_status,
                "is_synthetic_stress": True,
                "split": split,
                "graph_samples": len(scenario_samples),
            }
        )

    build = DatasetBuild(
        samples=samples,
        metadata=pd.DataFrame(metadata_records, columns=METADATA_COLUMNS),
        scenarios=pd.DataFrame(scenario_records, columns=SCENARIO_COLUMNS),
        line_indices=np.asarray(sorted(in_service_lines), dtype=np.int64),
        config={
            "scenario_count": scenario_count,
            "seed": seed,
            "load_scale_range": list(load_range),
            "generation_scale_range": list(generation_range),
            "capacity_scale_range": list(capacity_range),
            "load_variation_range": list(load_variation),
            "reactive_load_variation_range": list(reactive_variation),
            "generator_dispatch_variation_range": list(dispatch_variation),
            "overload_threshold": float(overload_threshold),
            "max_steps": max_steps,
            "max_initial_outages": max_initial_outages,
            "multiple_outage_probability": float(multiple_outage_probability),
        },
        generation_seconds=time.perf_counter() - started,
    )
    validate_dataset(build)
    return build


def validate_dataset(build: DatasetBuild) -> None:
    """Validate graph/metadata alignment and scenario-level split isolation."""
    if len(build.samples) != len(build.metadata):
        raise ValueError("sample and metadata counts do not match")
    if build.metadata["sample_id"].duplicated().any():
        raise ValueError("sample IDs must be unique")

    metadata_ids = build.metadata["sample_id"].tolist()
    sample_ids = [sample.sample_id for sample in build.samples]
    if sample_ids != metadata_ids:
        raise ValueError("sample order does not match metadata")

    for sample, (_, record) in zip(
        build.samples,
        build.metadata.iterrows(),
        strict=True,
    ):
        if not np.array_equal(sample.line_indices, build.line_indices):
            raise ValueError(f"{sample.sample_id}: physical line mapping changed")
        initial = set(_as_list(record["initial_outages"]))
        next_failures = set(_as_list(record["next_failed_lines"]))
        if initial & next_failures:
            raise ValueError(
                f"{sample.sample_id}: an initial outage is labeled as a next failure"
            )
        validate_graph_sample(sample, record.to_dict())

    valid_splits = {"train", "validation", "test"}
    if not set(build.scenarios["split"]).issubset(valid_splits):
        raise ValueError("scenario table contains an unknown split")
    if not set(build.metadata["split"]).issubset(valid_splits):
        raise ValueError("metadata contains an unknown split")
    if (
        not build.scenarios.empty
        and build.scenarios.groupby("scenario_id")["split"].nunique().max() > 1
    ):
        raise ValueError("a scenario appears in more than one split")
    if (
        not build.metadata.empty
        and build.metadata.groupby("scenario_id")["split"].nunique().max() > 1
    ):
        raise ValueError("a scenario appears in more than one sample split")

    scenario_splits = build.scenarios.set_index("scenario_id")["split"].to_dict()
    scenario_rows = build.scenarios.set_index("scenario_id")
    for row in build.metadata.itertuples(index=False):
        if scenario_splits.get(row.scenario_id) != row.split:
            raise ValueError(
                f"{row.scenario_id}: sample split does not match scenario split"
            )
        scenario = scenario_rows.loc[row.scenario_id]
        for column in (
            "random_seed", "load_scale", "generation_scale", "capacity_scale",
            "load_multipliers", "reactive_load_multipliers",
            "generator_dispatch_mw", "initial_outages",
        ):
            if str(getattr(row, column)) != str(scenario[column]):
                raise ValueError(
                    f"{row.scenario_id}: sample {column} does not match scenario"
                )


def build_line_failure_coverage(build: DatasetBuild) -> pd.DataFrame:
    """Summarize initiating outages and observed secondary failures per line."""
    positive_count = sum(bool(sample.target.any()) for sample in build.samples)
    scenario_initials: dict[str, set[int]] = {}
    for row in build.scenarios.itertuples(index=False):
        scenario_initials[str(row.scenario_id)] = set(_as_list(row.initial_outages))

    records: list[dict[str, Any]] = []
    for position, line_index in enumerate(build.line_indices.tolist()):
        initial_count = sum(
            line_index in outages for outages in scenario_initials.values()
        )
        secondary_count = 0
        positive_samples_containing = 0
        for sample in build.samples:
            if int(sample.target[position]):
                secondary_count += 1
                positive_samples_containing += 1
        records.append(
            {
                "line_index": int(line_index),
                "initial_outage_count": int(initial_count),
                "secondary_failure_count": int(secondary_count),
                "positive_samples_containing_line": int(
                    positive_samples_containing
                ),
                "percentage_positive_samples_containing_line": (
                    100.0 * positive_samples_containing / positive_count
                    if positive_count else 0.0
                ),
            }
        )
    return pd.DataFrame(records)


def build_dataset_summary(build: DatasetBuild) -> pd.DataFrame:
    """Build a one-row scenario, split, and class-imbalance summary."""
    total_samples = len(build.samples)
    positive_samples = sum(bool(sample.target.any()) for sample in build.samples)
    negative_samples = total_samples - positive_samples
    record: dict[str, Any] = {
        "total_scenarios": len(build.scenarios),
        "total_graph_samples": total_samples,
        "positive_samples": positive_samples,
        "negative_samples": negative_samples,
        "positive_sample_percent": (
            100.0 * positive_samples / total_samples if total_samples else 0.0
        ),
        "negative_sample_percent": (
            100.0 * negative_samples / total_samples if total_samples else 0.0
        ),
        "train_samples": int((build.metadata["split"] == "train").sum()),
        "validation_samples": int(
            (build.metadata["split"] == "validation").sum()
        ),
        "test_samples": int((build.metadata["split"] == "test").sum()),
        "generation_seconds": float(build.generation_seconds),
    }

    for position, line_index in enumerate(build.line_indices.tolist()):
        failure_count = sum(
            int(sample.target[position]) for sample in build.samples
        )
        record[f"line_{line_index}_next_failure_count"] = failure_count
        record[f"line_{line_index}_next_failure_frequency"] = (
            failure_count / total_samples if total_samples else 0.0
        )

    for status, count in build.scenarios["final_status"].value_counts().items():
        record[f"final_status_{status}_scenarios"] = int(count)
    return pd.DataFrame([record])


def _split_arrays(
    samples: list[GraphSample],
    template: GraphSample,
    line_indices: np.ndarray,
) -> dict[str, np.ndarray]:
    count = len(samples)
    if samples:
        return {
            "node_features": np.stack(
                [sample.node_features for sample in samples]
            ),
            "edge_index": np.stack([sample.edge_index for sample in samples]),
            "edge_features": np.stack(
                [sample.edge_features for sample in samples]
            ),
            "edge_line_indices": np.stack(
                [sample.edge_line_indices for sample in samples]
            ),
            "targets": np.stack([sample.target for sample in samples]),
            "bus_indices": template.bus_indices,
            "line_indices": line_indices,
            "sample_ids": np.asarray(
                [sample.sample_id for sample in samples],
                dtype=str,
            ),
        }
    return {
        "node_features": np.empty(
            (count, *template.node_features.shape),
            dtype=template.node_features.dtype,
        ),
        "edge_index": np.empty(
            (count, *template.edge_index.shape),
            dtype=template.edge_index.dtype,
        ),
        "edge_features": np.empty(
            (count, *template.edge_features.shape),
            dtype=template.edge_features.dtype,
        ),
        "edge_line_indices": np.empty(
            (count, *template.edge_line_indices.shape),
            dtype=template.edge_line_indices.dtype,
        ),
        "targets": np.empty(
            (count, *template.target.shape),
            dtype=template.target.dtype,
        ),
        "bus_indices": template.bus_indices,
        "line_indices": line_indices,
        "sample_ids": np.asarray([], dtype="U1"),
    }


def save_gnn_dataset(
    build: DatasetBuild,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Validate and serialize split tensors, metadata, summary, and schema."""
    validate_dataset(build)
    if not build.samples:
        raise ValueError("cannot serialize a dataset with no graph samples")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    template = build.samples[0]
    paths: dict[str, Path] = {}

    for split in ("train", "validation", "test"):
        split_samples = [
            sample
            for sample, row in zip(
                build.samples,
                build.metadata.itertuples(index=False),
                strict=True,
            )
            if row.split == split
        ]
        split_path = output_path / f"gnn_{split}.npz"
        np.savez_compressed(
            split_path,
            **_split_arrays(split_samples, template, build.line_indices),
        )
        paths[split] = split_path

    metadata_path = output_path / "gnn_samples_metadata.csv"
    summary_path = output_path / "gnn_dataset_summary.csv"
    manifest_path = output_path / "gnn_dataset_manifest.json"
    coverage_path = output_path / "gnn_line_failure_coverage.csv"
    build.metadata.to_csv(metadata_path, index=False)
    build_dataset_summary(build).to_csv(summary_path, index=False)
    build_line_failure_coverage(build).to_csv(coverage_path, index=False)
    manifest = {
        "format_version": 1,
        "node_feature_names": list(NODE_FEATURE_NAMES),
        "edge_feature_names": list(EDGE_FEATURE_NAMES),
        "bus_indices": template.bus_indices.tolist(),
        "line_indices": build.line_indices.tolist(),
        "directed_edges_per_physical_line": 2,
        "target_semantics": "physical lines failing in the next cascade wave",
        "split_policy": {
            "unit": "scenario",
            "train": 0.70,
            "validation": 0.15,
            "test": 0.15,
        },
        "config": build.config,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.update(
        {
            "metadata": metadata_path,
            "summary": summary_path,
            "manifest": manifest_path,
            "coverage": coverage_path,
        }
    )
    return paths
