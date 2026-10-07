"""Generate versioned Phase 4.5 dataset predicting secondary propagation failures."""

from pathlib import Path
import sys
import json
import time
from typing import Any
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.graph import make_target, GraphSample, validate_graph_sample, NODE_FEATURE_NAMES, EDGE_FEATURE_NAMES
from src.gnn_dataset import (
    _as_list,
    _split_arrays,
    METADATA_COLUMNS,
)
V1_DIR = PROJECT_ROOT / "outputs"
V2_DIR = PROJECT_ROOT / "outputs" / "predictive_v2"


def generate_predictive_v2(
    source_dir: Path = V1_DIR,
    target_dir: Path = V2_DIR,
) -> dict[str, Any]:
    """Generate predictive v2 dataset with secondary cascade failure targets."""
    started = time.perf_counter()
    target_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = source_dir / "gnn_samples_metadata.csv"
    manifest_path = source_dir / "gnn_dataset_manifest.json"
    if not metadata_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Source metadata or manifest missing in {source_dir}")

    metadata_df = pd.read_csv(metadata_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_v1 = json.load(f)

    # 1. Compute secondary targets per sample
    # Group by scenario_id and order by cascade_step
    secondary_targets: dict[str, list[int]] = {}
    current_overloads: dict[str, list[int]] = {}
    
    for scenario_id, group in metadata_df.groupby("scenario_id"):
        group_sorted = group.sort_values("cascade_step")
        sample_ids = group_sorted["sample_id"].tolist()
        overloaded_waves = [_as_list(x) for x in group_sorted["next_failed_lines"]]
        initial_outages = set(_as_list(group_sorted.iloc[0]["initial_outages"]))

        for i in range(len(sample_ids)):
            sid = sample_ids[i]
            o_current = overloaded_waves[i]
            # Secondary failures are the overloads that trip at the next wave (t+2)
            # after o_current trips and power redistributes
            s_secondary = overloaded_waves[i + 1] if i + 1 < len(overloaded_waves) else []
            
            # Assertions to guarantee zero leakage:
            overlap_current = set(s_secondary).intersection(set(o_current))
            if overlap_current:
                raise ValueError(f"Leakage detected in {sid}: secondary failures overlap with current overloads: {overlap_current}")
            overlap_initial = set(s_secondary).intersection(initial_outages)
            if overlap_initial:
                raise ValueError(f"Leakage detected in {sid}: secondary failures overlap with initial outages: {overlap_initial}")

            secondary_targets[sid] = s_secondary
            current_overloads[sid] = o_current

    # 2. Update metadata
    metadata_v2 = metadata_df.copy()
    metadata_v2["current_overloaded_lines"] = [
        json.dumps(current_overloads[sid]) for sid in metadata_v2["sample_id"]
    ]
    metadata_v2["secondary_failed_lines"] = [
        json.dumps(secondary_targets[sid]) for sid in metadata_v2["sample_id"]
    ]
    # Keep next_failed_lines pointing to the prediction target for schema compatibility
    metadata_v2["next_failed_lines"] = metadata_v2["secondary_failed_lines"]

    # 3. Load split arrays and update targets
    line_indices = np.array(manifest_v1["line_indices"], dtype=np.int64)
    bus_indices = np.array(manifest_v1["bus_indices"], dtype=np.int64)

    split_targets = {}
    total_positives = 0
    total_samples = 0
    samples_with_secondary = 0

    for split in ("train", "validation", "test"):
        npz_path = source_dir / f"gnn_{split}.npz"
        with np.load(npz_path, allow_pickle=False) as data:
            node_features = data["node_features"]
            edge_index = data["edge_index"]
            edge_features = data["edge_features"]
            edge_line_indices = data["edge_line_indices"]
            sample_ids = data["sample_ids"].astype(str)

        new_targets = np.zeros((len(sample_ids), len(line_indices)), dtype=np.uint8)
        for idx, sid in enumerate(sample_ids):
            target_lines = secondary_targets[sid]
            new_targets[idx] = make_target(line_indices, target_lines)
            if len(target_lines) > 0:
                samples_with_secondary += 1

        total_positives += int(new_targets.sum())
        total_samples += len(sample_ids)
        split_targets[split] = new_targets

        # Validate each sample
        for idx, sid in enumerate(sample_ids):
            sample = GraphSample(
                sample_id=sid,
                bus_indices=bus_indices,
                node_features=node_features[idx],
                edge_index=edge_index[idx],
                edge_features=edge_features[idx],
                edge_line_indices=edge_line_indices[idx],
                line_indices=line_indices,
                target=new_targets[idx],
            )
            meta_record = metadata_v2.loc[metadata_v2["sample_id"] == sid].iloc[0].to_dict()
            validate_graph_sample(sample, meta_record)

        # Save new split npz
        v2_npz_path = target_dir / f"gnn_{split}.npz"
        np.savez_compressed(
            v2_npz_path,
            node_features=node_features,
            edge_index=edge_index,
            edge_features=edge_features,
            edge_line_indices=edge_line_indices,
            targets=new_targets,
            bus_indices=bus_indices,
            line_indices=line_indices,
            sample_ids=sample_ids,
        )

    # 4. Save metadata
    v2_metadata_path = target_dir / "gnn_samples_metadata.csv"
    metadata_v2.to_csv(v2_metadata_path, index=False)

    # 5. Build summary CSV
    positive_samples = samples_with_secondary
    negative_samples = total_samples - positive_samples
    summary_record: dict[str, Any] = {
        "total_scenarios": metadata_df["scenario_id"].nunique(),
        "total_graph_samples": total_samples,
        "positive_samples": positive_samples,
        "negative_samples": negative_samples,
        "positive_sample_percent": 100.0 * positive_samples / total_samples,
        "negative_sample_percent": 100.0 * negative_samples / total_samples,
        "train_samples": int((metadata_v2["split"] == "train").sum()),
        "validation_samples": int((metadata_v2["split"] == "validation").sum()),
        "test_samples": int((metadata_v2["split"] == "test").sum()),
        "generation_seconds": float(time.perf_counter() - started),
    }

    all_targets = np.concatenate([split_targets[s] for s in ("train", "validation", "test")], axis=0)
    for position, line_index in enumerate(line_indices.tolist()):
        count = int(all_targets[:, position].sum())
        summary_record[f"line_{line_index}_next_failure_count"] = count
        summary_record[f"line_{line_index}_next_failure_frequency"] = count / total_samples

    for status, count in metadata_df.groupby("scenario_id")["final_status"].first().value_counts().items():
        summary_record[f"final_status_{status}_scenarios"] = int(count)

    pd.DataFrame([summary_record]).to_csv(target_dir / "gnn_dataset_summary.csv", index=False)

    # 6. Build line failure coverage CSV
    coverage_records = []
    initial_counts = {}
    for sc_id, group in metadata_df.groupby("scenario_id"):
        inits = _as_list(group.iloc[0]["initial_outages"])
        for l in inits:
            initial_counts[l] = initial_counts.get(l, 0) + 1

    for position, line_index in enumerate(line_indices.tolist()):
        secondary_count = int(all_targets[:, position].sum())
        coverage_records.append({
            "line_index": int(line_index),
            "initial_outage_count": int(initial_counts.get(line_index, 0)),
            "secondary_failure_count": int(secondary_count),
            "positive_samples_containing_line": int(secondary_count),
            "percentage_positive_samples_containing_line": (
                100.0 * secondary_count / positive_samples if positive_samples else 0.0
            ),
        })
    pd.DataFrame(coverage_records).to_csv(target_dir / "gnn_line_failure_coverage.csv", index=False)

    # 7. Manifest
    manifest_v2 = dict(manifest_v1)
    manifest_v2["format_version"] = 2
    manifest_v2["target_semantics"] = (
        "secondary physical lines failing after current overloaded lines trip and power redistributes "
        "(t+2 / downstream cascade propagation horizon)"
    )
    (target_dir / "gnn_dataset_manifest.json").write_text(
        json.dumps(manifest_v2, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - started
    print(f"Generated Predictive Dataset v2 in {elapsed:.2f} seconds.")
    print(f"Target directory: {target_dir}")
    print(f"Total graph samples: {total_samples}")
    print(f"Positive samples with secondary failures: {positive_samples} ({summary_record['positive_sample_percent']:.2f}%)")
    print(f"Total secondary line failure events: {total_positives}")
    
    return {
        "total_samples": total_samples,
        "positive_samples": positive_samples,
        "total_positives": total_positives,
        "elapsed": elapsed,
        "target_dir": target_dir,
    }


if __name__ == "__main__":
    generate_predictive_v2()
