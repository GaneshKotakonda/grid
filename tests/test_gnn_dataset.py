"""Tests for reproducible cascade-to-graph dataset generation."""

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.gnn_dataset import (
    METADATA_COLUMNS,
    SCENARIO_COLUMNS,
    DatasetBuild,
    assign_scenario_splits,
    build_dataset_summary,
    extract_cascade_samples,
    build_line_failure_coverage,
    generate_gnn_dataset,
    save_gnn_dataset,
    validate_dataset,
)
from src.graph import EDGE_FEATURE_NAMES, NODE_FEATURE_NAMES
from src.grid_loader import load_ieee14
from src.simulator import run_power_flow


pytestmark = pytest.mark.filterwarnings(
    "ignore:tap_dependency_table is missing in net.*:DeprecationWarning"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _solved_state_with_outages(outages: list[int]):
    net = load_ieee14()
    for line_index in outages:
        net.line.at[line_index, "in_service"] = False
    assert run_power_flow(net)["converged"] is True
    return net


def _scenario_metadata() -> dict[str, object]:
    return {
        "scenario_id": "controlled-0",
        "random_seed": 17,
        "load_scale": 1.2,
        "generation_scale": 1.0,
        "capacity_scale": 0.02,
        "load_multipliers": "[1.0]",
        "reactive_load_multipliers": "[1.0]",
        "generator_dispatch_mw": "[1.0]",
        "initial_outages": [0],
        "final_status": "STABLE",
        "is_synthetic_stress": True,
    }


def test_random_generation_is_deterministic() -> None:
    kwargs = {
        "scenario_count": 6,
        "seed": 123,
        "capacity_scale_range": (0.03, 0.05),
        "max_initial_outages": 1,
        "max_steps": 2,
    }

    first = generate_gnn_dataset(load_ieee14(), **kwargs)
    second = generate_gnn_dataset(load_ieee14(), **kwargs)

    assert first.samples
    pd.testing.assert_frame_equal(first.scenarios, second.scenarios)
    pd.testing.assert_frame_equal(first.metadata, second.metadata)
    assert first.config == second.config
    assert np.array_equal(first.line_indices, second.line_indices)
    assert len(first.samples) == len(second.samples)
    for left, right in zip(first.samples, second.samples, strict=True):
        assert left.sample_id == right.sample_id
        assert np.array_equal(left.node_features, right.node_features)
        assert np.array_equal(left.edge_index, right.edge_index)
        assert np.array_equal(left.edge_features, right.edge_features)
        assert np.array_equal(left.target, right.target)
    assert first.metadata.groupby("scenario_id")["split"].nunique().max() == 1
    validate_dataset(first)


def test_operating_point_randomization_is_seeded_and_per_element() -> None:
    kwargs = {
        "scenario_count": 4,
        "seed": 921,
        "capacity_scale_range": (0.03, 0.05),
        "max_initial_outages": 1,
        "max_steps": 1,
    }
    first = generate_gnn_dataset(load_ieee14(), **kwargs)
    second = generate_gnn_dataset(load_ieee14(), **kwargs)
    pd.testing.assert_frame_equal(first.scenarios, second.scenarios)
    load_vectors = first.scenarios["load_multipliers"].tolist()
    assert len(set(load_vectors)) == len(load_vectors)
    assert all(len(json.loads(vector)) == 11 for vector in load_vectors)
    assert all(
        len(json.loads(vector)) == 4
        for vector in first.scenarios["generator_dispatch_mw"]
    )
    assert first.scenarios["generator_dispatch_mw"].equals(
        second.scenarios["generator_dispatch_mw"]
    )


def test_line_failure_coverage_reports_initiators_and_secondary_labels() -> None:
    build = generate_gnn_dataset(
        load_ieee14(),
        scenario_count=12,
        seed=25,
        capacity_scale_range=(0.03, 0.05),
        max_initial_outages=2,
        max_steps=2,
    )
    coverage = build_line_failure_coverage(build)
    assert coverage["line_index"].tolist() == build.line_indices.tolist()
    assert coverage["initial_outage_count"].sum() == sum(
        len(json.loads(value)) for value in build.scenarios["initial_outages"]
    )
    for row in coverage.itertuples(index=False):
        pos = int(np.flatnonzero(build.line_indices == row.line_index)[0])
        expected = sum(int(sample.target[pos]) for sample in build.samples)
        assert row.secondary_failure_count == expected
        assert row.positive_samples_containing_line == expected


def test_next_step_target_excludes_initial_outage_and_adds_stable_negative() -> None:
    state_0 = _solved_state_with_outages([0])
    state_1 = _solved_state_with_outages([0, 2])
    cascade = {
        "status": "STABLE",
        "history": [
            {
                "step": 0,
                "failed_lines": [0],
                "newly_failed_lines": [0],
                "overloaded_lines": [2],
                "converged": True,
                "network_state": state_0,
            },
            {
                "step": 1,
                "failed_lines": [0, 2],
                "newly_failed_lines": [2],
                "overloaded_lines": [],
                "converged": True,
                "network_state": state_1,
            },
        ],
    }

    samples, records = extract_cascade_samples(
        cascade,
        _scenario_metadata(),
        "train",
    )

    assert len(samples) == 2
    assert np.flatnonzero(samples[0].target).tolist() == [2]
    assert samples[0].target[0] == 0
    assert samples[1].target.tolist() == [0] * 15
    assert json.loads(records[0]["current_failed_lines"]) == [0]
    assert json.loads(records[0]["next_failed_lines"]) == [2]
    assert json.loads(records[1]["next_failed_lines"]) == []


def test_capped_pending_state_is_not_emitted_as_negative() -> None:
    cascade = {
        "status": "MAX_STEPS_REACHED",
        "history": [
            {
                "step": 0,
                "failed_lines": [0],
                "newly_failed_lines": [0],
                "overloaded_lines": [2],
                "converged": True,
                "network_state": _solved_state_with_outages([0]),
            }
        ],
    }

    samples, records = extract_cascade_samples(
        cascade,
        _scenario_metadata(),
        "validation",
    )

    assert samples == []
    assert records == []


def test_pre_failure_state_keeps_nonconvergent_trip_target() -> None:
    metadata = _scenario_metadata()
    metadata["final_status"] = "NON_CONVERGED"
    cascade = {
        "status": "NON_CONVERGED",
        "history": [
            {
                "step": 0,
                "failed_lines": [0],
                "newly_failed_lines": [0],
                "overloaded_lines": [2],
                "converged": True,
                "network_state": _solved_state_with_outages([0]),
            },
            {
                "step": 1,
                "failed_lines": [0, 2],
                "newly_failed_lines": [2],
                "overloaded_lines": [],
                "converged": False,
            },
        ],
    }

    samples, records = extract_cascade_samples(cascade, metadata, "test")

    assert len(samples) == 1
    assert np.flatnonzero(samples[0].target).tolist() == [2]
    assert json.loads(records[0]["next_failed_lines"]) == [2]


def test_scenario_split_is_deterministic_and_isolated() -> None:
    scenario_ids = [f"scenario-{index:03d}" for index in range(20)]

    first = assign_scenario_splits(scenario_ids, seed=42)
    second = assign_scenario_splits(scenario_ids, seed=42)

    assert first == second
    assert {split: list(first.values()).count(split) for split in set(first.values())} == {
        "train": 14,
        "validation": 3,
        "test": 3,
    }
    split_frame = pd.DataFrame(
        {
            "scenario_id": [scenario_ids[0], scenario_ids[0], scenario_ids[1]],
            "split": [first[scenario_ids[0]], first[scenario_ids[0]], first[scenario_ids[1]]],
        }
    )
    assert split_frame.groupby("scenario_id")["split"].nunique().max() == 1


def test_validation_rejects_conflicting_splits_for_zero_sample_scenario() -> None:
    scenario_rows = [
        {
            "scenario_id": "duplicate",
            "random_seed": 1,
            "load_scale": 1.0,
            "generation_scale": 1.0,
            "capacity_scale": 1.0,
            "initial_outages": "[0]",
            "final_status": "NON_CONVERGED",
            "is_synthetic_stress": True,
            "split": split,
            "graph_samples": 0,
        }
        for split in ("train", "test")
    ]
    build = DatasetBuild(
        samples=[],
        metadata=pd.DataFrame(columns=METADATA_COLUMNS),
        scenarios=pd.DataFrame(scenario_rows, columns=SCENARIO_COLUMNS),
        line_indices=np.arange(15, dtype=np.int64),
        config={},
        generation_seconds=0.0,
    )

    with pytest.raises(ValueError, match="scenario appears in more than one split"):
        validate_dataset(build)


@pytest.fixture(scope="module")
def small_dataset_build():
    return generate_gnn_dataset(
        load_ieee14(),
        scenario_count=6,
        seed=42,
        capacity_scale_range=(0.03, 0.05),
        max_initial_outages=1,
        max_steps=2,
    )


def test_dataset_summary_reports_imbalance_failures_and_statuses(
    small_dataset_build,
) -> None:
    build = small_dataset_build

    summary = build_dataset_summary(build)

    assert len(summary) == 1
    row = summary.iloc[0]
    positive = sum(bool(sample.target.any()) for sample in build.samples)
    negative = len(build.samples) - positive
    assert row["total_scenarios"] == 6
    assert row["total_graph_samples"] == len(build.samples)
    assert row["positive_samples"] == positive
    assert row["negative_samples"] == negative
    assert row["positive_sample_percent"] == pytest.approx(
        100.0 * positive / len(build.samples)
    )
    assert row["negative_sample_percent"] == pytest.approx(
        100.0 * negative / len(build.samples)
    )
    for split in ("train", "validation", "test"):
        assert row[f"{split}_samples"] == int(
            (build.metadata["split"] == split).sum()
        )
    for position, line_index in enumerate(build.line_indices.tolist()):
        count = sum(int(sample.target[position]) for sample in build.samples)
        assert row[f"line_{line_index}_next_failure_count"] == count
        assert row[f"line_{line_index}_next_failure_frequency"] == pytest.approx(
            count / len(build.samples)
        )
    for status, count in build.scenarios["final_status"].value_counts().items():
        assert row[f"final_status_{status}_scenarios"] == count
    assert row["generation_seconds"] == pytest.approx(build.generation_seconds)


def test_dataset_serialization_round_trips_tensors_and_metadata(
    tmp_path: Path,
    small_dataset_build,
) -> None:
    build = small_dataset_build

    paths = save_gnn_dataset(build, tmp_path)

    assert set(paths) == {
        "train",
        "validation",
        "test",
        "metadata",
        "summary",
        "manifest",
        "coverage",
    }
    assert all(path.exists() for path in paths.values())
    saved_metadata = pd.read_csv(paths["metadata"])
    pd.testing.assert_frame_equal(
        saved_metadata,
        build.metadata,
        check_dtype=False,
    )

    for split in ("train", "validation", "test"):
        split_metadata = build.metadata.loc[build.metadata["split"] == split]
        with np.load(paths[split], allow_pickle=False) as archive:
            sample_count = len(split_metadata)
            assert archive["node_features"].shape == (sample_count, 14, 8)
            assert archive["edge_index"].shape == (sample_count, 2, 30)
            assert archive["edge_features"].shape == (sample_count, 30, 11)
            assert archive["edge_line_indices"].shape == (sample_count, 30)
            assert archive["targets"].shape == (sample_count, 15)
            assert archive["line_indices"].tolist() == list(range(15))
            assert archive["sample_ids"].tolist() == split_metadata[
                "sample_id"
            ].tolist()

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["node_feature_names"] == list(NODE_FEATURE_NAMES)
    assert manifest["edge_feature_names"] == list(EDGE_FEATURE_NAMES)
    assert manifest["line_indices"] == list(range(15))
    saved_summary = pd.read_csv(paths["summary"])
    assert saved_summary.at[0, "total_scenarios"] == 6


def test_cli_generates_small_dataset(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_gnn_dataset.py",
            "--scenarios",
            "4",
            "--seed",
            "42",
            "--max-steps",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Scenarios generated: 4" in result.stdout
    assert "Graph samples:" in result.stdout
    assert "Positive samples:" in result.stdout
    assert "Negative samples:" in result.stdout
    assert "Train/validation/test samples:" in result.stdout
    assert "Generation time:" in result.stdout
    assert {path.name for path in tmp_path.iterdir()} == {
        "gnn_train.npz",
        "gnn_validation.npz",
        "gnn_test.npz",
        "gnn_samples_metadata.csv",
        "gnn_dataset_summary.csv",
        "gnn_dataset_manifest.json",
        "gnn_line_failure_coverage.csv",
    }
