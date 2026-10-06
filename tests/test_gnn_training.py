"""Fast focused checks for Phase 4 model and training utilities."""

import numpy as np
import pytest
import torch

from src.gnn_training import (
    GraphSplit,
    evaluate_predictions,
    fit_normalization,
    load_checkpoint,
    load_dataset,
    make_model,
    normalize_split,
    positive_weights,
    select_threshold,
    train_model,
)


def _split(count: int, offset: int = 0) -> GraphSplit:
    rng = np.random.default_rng(900 + offset)
    source = np.arange(15) % 14
    destination = (source + 1) % 14
    edge_index = np.stack(
        [np.concatenate([source, destination]), np.concatenate([destination, source])]
    )
    edge_lines = np.tile(np.arange(15), 2)
    node = rng.normal(size=(count, 14, 8)).astype(np.float32)
    edge = rng.normal(size=(count, 30, 11)).astype(np.float32)
    edge[:, :, 7] = 1.0
    edge[:, :2, 7] = 0.0
    targets = np.stack(
        [np.full(15, (row + offset) % 2, dtype=np.uint8) for row in range(count)]
    )
    return GraphSplit(
        node_features=torch.from_numpy(node),
        edge_index=torch.from_numpy(np.repeat(edge_index[None], count, axis=0)),
        edge_features=torch.from_numpy(edge),
        edge_in_service=torch.from_numpy(edge[:, :, 7].copy()),
        edge_line_indices=torch.from_numpy(np.repeat(edge_lines[None], count, axis=0)),
        targets=torch.from_numpy(targets.astype(np.float32)),
        line_indices=torch.arange(15),
        sample_ids=np.asarray([f"sample-{offset}-{i}" for i in range(count)]),
    )


def _write_split(path, split: GraphSplit) -> None:
    np.savez_compressed(
        path,
        node_features=split.node_features.numpy(),
        edge_index=split.edge_index.numpy(),
        edge_features=split.edge_features.numpy(),
        edge_line_indices=split.edge_line_indices.numpy(),
        targets=split.targets.numpy(),
        line_indices=split.line_indices.numpy(),
        sample_ids=split.sample_ids,
    )


def test_dataset_loading_reads_all_saved_splits(tmp_path) -> None:
    for name, split in (
        ("train", _split(4, 0)),
        ("validation", _split(2, 10)),
        ("test", _split(2, 20)),
    ):
        _write_split(tmp_path / f"gnn_{name}.npz", split)
    loaded = load_dataset(tmp_path)
    assert (len(loaded.train), len(loaded.validation), len(loaded.test)) == (4, 2, 2)
    assert loaded.train.node_features.shape == (4, 14, 8)
    assert loaded.test.targets.shape == (2, 15)


def test_normalization_uses_training_statistics_only() -> None:
    train = _split(4)
    validation = _split(2, 10)
    stats = fit_normalization(train)
    shifted_validation = GraphSplit(
        **{
            **validation.__dict__,
            "node_features": validation.node_features + 1000,
            "edge_features": validation.edge_features - 500,
        }
    )
    original_stats = fit_normalization(train)
    assert torch.equal(stats["node_mean"], original_stats["node_mean"])
    assert torch.equal(stats["edge_mean"], original_stats["edge_mean"])
    normalized = normalize_split(shifted_validation, stats)
    assert normalized.node_features.mean() > 100
    assert normalized.edge_features.mean() < -100


@pytest.mark.parametrize("model_type", ["mlp", "gcn", "gat"])
def test_models_output_one_logit_per_physical_line(model_type: str) -> None:
    split = _split(3)
    model = make_model(model_type, split, hidden_dim=16, dropout=0.0)
    output = model(split.node_features, split.edge_features, split.edge_in_service)
    assert output.shape == (3, 15)
    weights = positive_weights(split.targets)
    loss = torch.nn.functional.binary_cross_entropy_with_logits(
        output, split.targets, pos_weight=weights
    )
    assert torch.isfinite(loss)


def test_threshold_selection_uses_validation_f1() -> None:
    target = np.asarray([[1, 0], [1, 0], [0, 1]], dtype=np.uint8)
    probability = np.asarray([[0.8, 0.2], [0.6, 0.4], [0.4, 0.7]])
    threshold, f1 = select_threshold(
        target, probability, candidates=np.asarray([0.3, 0.5, 0.75])
    )
    metrics, _ = evaluate_predictions(target, probability, threshold)
    assert threshold == pytest.approx(0.5)
    assert f1 == pytest.approx(1.0)
    assert metrics["micro_f1"] == pytest.approx(1.0)


def test_checkpoint_round_trip_has_deterministic_inference(tmp_path) -> None:
    train, validation, test = _split(4, 0), _split(2, 10), _split(2, 20)
    from src.gnn_training import DatasetBundle

    bundle = DatasetBundle(train, validation, test)
    stats = fit_normalization(train)
    config = {
        "epochs": 2,
        "patience": 2,
        "learning_rate": 0.001,
        "hidden_dim": 8,
        "dropout": 0.0,
        "batch_size": 4,
        "seed": 42,
    }
    checkpoint_path = tmp_path / "best.pt"
    model, _, _, _, _ = train_model("mlp", bundle, stats, config, checkpoint_path)
    restored, checkpoint = load_checkpoint(checkpoint_path, train)
    normalized_test = normalize_split(test, checkpoint["normalization"])
    x = normalized_test.node_features
    e = normalized_test.edge_features
    with torch.no_grad():
        first = restored(x, e, normalized_test.edge_in_service)
        second = restored(x, e, normalized_test.edge_in_service)
    assert torch.equal(first, second)
    assert checkpoint["normalization"].keys() == stats.keys()
    assert model.training is False
