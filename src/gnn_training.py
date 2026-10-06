"""Phase 4 training utilities for MLP, GCN, and GAT next-line predictors."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import time
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F


SPLITS = ("train", "validation", "test")
MODEL_TYPES = ("mlp", "gcn", "gat")


@dataclass
class GraphSplit:
    """Fixed-size batched graph tensors for one dataset split."""

    node_features: torch.Tensor
    edge_index: torch.Tensor
    edge_features: torch.Tensor
    edge_in_service: torch.Tensor
    edge_line_indices: torch.Tensor
    targets: torch.Tensor
    line_indices: torch.Tensor
    sample_ids: np.ndarray

    def __len__(self) -> int:
        return int(self.targets.shape[0])


@dataclass
class DatasetBundle:
    train: GraphSplit
    validation: GraphSplit
    test: GraphSplit

    def by_name(self, name: str) -> GraphSplit:
        if name not in SPLITS:
            raise ValueError(f"Unknown split: {name}")
        return getattr(self, name)


def _load_split(path: Path) -> GraphSplit:
    required = {
        "node_features", "edge_index", "edge_features", "edge_line_indices",
        "targets", "line_indices", "sample_ids",
    }
    with np.load(path, allow_pickle=False) as archive:
        missing = required.difference(archive.files)
        if missing:
            raise ValueError(f"{path}: missing arrays {sorted(missing)}")
        arrays = {key: archive[key] for key in required}

    node = arrays["node_features"]
    edge_index = arrays["edge_index"]
    edge = arrays["edge_features"]
    edge_lines = arrays["edge_line_indices"]
    target = arrays["targets"]
    line_indices = arrays["line_indices"]
    sample_ids = arrays["sample_ids"].astype(str)
    count = len(target)
    if node.ndim != 3 or edge_index.ndim != 3 or edge.ndim != 3:
        raise ValueError(f"{path}: graph features must be batched rank-3 arrays")
    expected = {
        "node_features": (count, 14, 8),
        "edge_index": (count, 2, 30),
        "edge_features": (count, 30, 11),
        "edge_line_indices": (count, 30),
        "targets": (count, 15),
        "line_indices": (15,),
        "sample_ids": (count,),
    }
    for name, shape in expected.items():
        if arrays[name].shape != shape:
            raise ValueError(f"{path}: {name} shape {arrays[name].shape} != {shape}")
    if not all(np.isfinite(arrays[name]).all() for name in ("node_features", "edge_features")):
        raise ValueError(f"{path}: features contain NaN or Inf")
    if not np.isin(target, [0, 1]).all():
        raise ValueError(f"{path}: targets must be binary")
    if len(set(sample_ids.tolist())) != count:
        raise ValueError(f"{path}: sample IDs must be unique")

    return GraphSplit(
        node_features=torch.from_numpy(node.astype(np.float32, copy=False)),
        edge_index=torch.from_numpy(edge_index.astype(np.int64, copy=False)),
        edge_features=torch.from_numpy(edge.astype(np.float32, copy=False)),
        edge_in_service=torch.from_numpy((edge[:, :, 7] > 0.5).astype(np.float32)),
        edge_line_indices=torch.from_numpy(edge_lines.astype(np.int64, copy=False)),
        targets=torch.from_numpy(target.astype(np.float32, copy=False)),
        line_indices=torch.from_numpy(line_indices.astype(np.int64, copy=False)),
        sample_ids=sample_ids,
    )


def load_dataset(output_dir: str | Path) -> DatasetBundle:
    """Load and cross-check the saved train, validation, and test graph arrays."""
    path = Path(output_dir)
    splits = {name: _load_split(path / f"gnn_{name}.npz") for name in SPLITS}
    reference_lines = splits["train"].line_indices
    for name, split in splits.items():
        if not torch.equal(split.line_indices, reference_lines):
            raise ValueError(f"{name}: physical line mapping differs from train")
    ids = [sample_id for split in splits.values() for sample_id in split.sample_ids]
    if len(set(ids)) != len(ids):
        raise ValueError("sample IDs overlap between data splits")
    return DatasetBundle(**splits)


def fit_normalization(train: GraphSplit) -> dict[str, torch.Tensor]:
    """Calculate feature-wise means and standard deviations from train only."""
    node = train.node_features
    edge = train.edge_features
    stats = {
        "node_mean": node.mean(dim=(0, 1)),
        "node_std": node.std(dim=(0, 1), unbiased=False).clamp_min(1e-6),
        "edge_mean": edge.mean(dim=(0, 1)),
        "edge_std": edge.std(dim=(0, 1), unbiased=False).clamp_min(1e-6),
    }
    return stats


def normalize_split(split: GraphSplit, stats: dict[str, torch.Tensor]) -> GraphSplit:
    """Apply the train-fitted statistics without modifying the source tensors."""
    return GraphSplit(
        node_features=(split.node_features - stats["node_mean"]) / stats["node_std"],
        edge_index=split.edge_index,
        edge_features=(split.edge_features - stats["edge_mean"]) / stats["edge_std"],
        edge_in_service=split.edge_in_service,
        edge_line_indices=split.edge_line_indices,
        targets=split.targets,
        line_indices=split.line_indices,
        sample_ids=split.sample_ids,
    )


def positive_weights(targets: torch.Tensor, maximum: float = 20.0) -> torch.Tensor:
    """Compute TRAIN-only negative/positive weights, clipped to [1, maximum]."""
    positives = targets.sum(dim=0)
    negatives = targets.shape[0] - positives
    return (negatives / positives.clamp_min(1.0)).clamp(min=1.0, max=maximum)


def line_layout(split: GraphSplit) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return canonical edge positions and source/destination node per line."""
    edge_lines = split.edge_line_indices[0].cpu().numpy()
    positions = []
    for line_index in split.line_indices.tolist():
        matches = np.flatnonzero(edge_lines == line_index)
        if len(matches) != 2:
            raise ValueError(f"line {line_index} must map to two directed edges")
        positions.append(int(matches[0]))
    edge_positions = torch.tensor(positions, dtype=torch.long)
    source = split.edge_index[0, 0, edge_positions]
    destination = split.edge_index[0, 1, edge_positions]
    return edge_positions, source, destination


class GCNLayer(nn.Module):
    def __init__(self, input_dim: int, output_dim: int, dropout: float) -> None:
        super().__init__()
        self.linear = nn.Linear(input_dim, output_dim)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        x = F.dropout(x, p=self.dropout, training=self.training)
        if adjacency.ndim == 2:
            adjacency = adjacency.expand(x.shape[0], -1, -1)
        return F.relu(torch.bmm(adjacency, self.linear(x)))


class GATLayer(nn.Module):
    """Small dense masked graph-attention layer for this fixed 14-node graph."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        dropout: float,
        heads: int = 4,
    ) -> None:
        super().__init__()
        self.heads = heads
        self.head_dim = max(1, (hidden_dim + heads - 1) // heads)
        self.output_dim = self.heads * self.head_dim
        self.linear = nn.Linear(input_dim, self.output_dim, bias=False)
        self.attention_source = nn.Parameter(torch.empty(heads, self.head_dim))
        self.attention_destination = nn.Parameter(torch.empty(heads, self.head_dim))
        self.dropout = dropout
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.xavier_uniform_(self.attention_source)
        nn.init.xavier_uniform_(self.attention_destination)

    def forward(self, x: torch.Tensor, adjacency_mask: torch.Tensor) -> torch.Tensor:
        x = F.dropout(x, p=self.dropout, training=self.training)
        batch, nodes, _ = x.shape
        z = self.linear(x).view(batch, nodes, self.heads, self.head_dim)
        z_heads = z.permute(0, 2, 1, 3)
        src_score = (z_heads * self.attention_source[None, :, None, :]).sum(-1)
        dst_score = (z_heads * self.attention_destination[None, :, None, :]).sum(-1)
        logits = F.leaky_relu(
            dst_score.unsqueeze(-1) + src_score.unsqueeze(-2), negative_slope=0.2
        )
        mask = (
            adjacency_mask.bool()[None, None, :, :]
            if adjacency_mask.ndim == 2
            else adjacency_mask.bool()[:, None, :, :]
        )
        attention = torch.softmax(logits.masked_fill(~mask, -1e9), dim=-1)
        attention = F.dropout(attention, p=self.dropout, training=self.training)
        values = torch.matmul(attention, z_heads)
        return F.elu(values.permute(0, 2, 1, 3).reshape(batch, nodes, self.output_dim))


class GridPredictor(nn.Module):
    """MLP baseline or topology-aware GCN/GAT with a shared edge classifier."""

    def __init__(
        self,
        model_type: str,
        node_features: int,
        edge_features: int,
        line_positions: torch.Tensor,
        line_sources: torch.Tensor,
        line_destinations: torch.Tensor,
        adjacency: torch.Tensor,
        directed_sources: torch.Tensor,
        directed_destinations: torch.Tensor,
        hidden_dim: int = 64,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if model_type not in MODEL_TYPES:
            raise ValueError(f"Unknown model type: {model_type}")
        self.model_type = model_type
        self.register_buffer("line_positions", line_positions.clone())
        self.register_buffer("line_sources", line_sources.clone())
        self.register_buffer("line_destinations", line_destinations.clone())
        self.register_buffer("adjacency", adjacency.clone())
        self.register_buffer("adjacency_mask", adjacency.gt(0))
        self.register_buffer("directed_sources", directed_sources.clone())
        self.register_buffer("directed_destinations", directed_destinations.clone())
        if model_type == "mlp":
            flattened_size = node_features * 14 + edge_features * 30
            self.mlp = nn.Sequential(
                nn.Linear(flattened_size, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, 15),
            )
            self.edge_head = None
            self.layers = nn.ModuleList()
        else:
            if model_type == "gcn":
                self.layers = nn.ModuleList(
                    [
                        GCNLayer(node_features, hidden_dim, dropout),
                        GCNLayer(hidden_dim, hidden_dim, dropout),
                    ]
                )
                embedding_dim = hidden_dim
            else:
                first = GATLayer(node_features, hidden_dim, dropout)
                second = GATLayer(first.output_dim, hidden_dim, dropout)
                self.layers = nn.ModuleList([first, second])
                embedding_dim = second.output_dim
            self.edge_head = nn.Sequential(
                nn.Linear(2 * embedding_dim + edge_features, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, max(hidden_dim // 2, 8)),
                nn.ReLU(),
                nn.Linear(max(hidden_dim // 2, 8), 1),
            )
            self.mlp = None

    def forward(
        self,
        node: torch.Tensor,
        edge: torch.Tensor,
        edge_in_service: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if self.model_type == "mlp":
            return self.mlp(torch.cat((node.flatten(1), edge.flatten(1)), dim=1))
        x = node
        if edge_in_service is None:
            edge_in_service = edge.new_ones((edge.shape[0], edge.shape[1]))
        batch = node.shape[0]
        adjacency = node.new_zeros((batch, node.shape[1], node.shape[1]))
        adjacency[:, self.directed_destinations, self.directed_sources] = (
            edge_in_service.to(dtype=node.dtype)
        )
        identity = torch.eye(node.shape[1], dtype=node.dtype, device=node.device)
        adjacency = adjacency + identity[None, :, :]
        if self.model_type == "gcn":
            degree = adjacency.sum(dim=2).clamp_min(1.0)
            inverse_sqrt = degree.rsqrt()
            adjacency = inverse_sqrt[:, :, None] * adjacency * inverse_sqrt[:, None, :]
        else:
            adjacency = adjacency.gt(0)
        for layer in self.layers:
            if self.model_type == "gcn":
                x = layer(x, adjacency)
            else:
                x = layer(x, adjacency)
        source = x[:, self.line_sources]
        destination = x[:, self.line_destinations]
        physical_edges = edge[:, self.line_positions]
        line_features = torch.cat((source, destination, physical_edges), dim=-1)
        return self.edge_head(line_features).squeeze(-1)


def make_adjacency(split: GraphSplit) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build normalized GCN adjacency and the physical-line endpoint mapping."""
    positions, sources, destinations = line_layout(split)
    nodes = split.node_features.shape[1]
    raw = torch.eye(nodes, dtype=torch.float32)
    edge_index = split.edge_index[0]
    raw[edge_index[1], edge_index[0]] = 1.0
    degree = raw.sum(dim=1).clamp_min(1.0)
    inverse_sqrt = degree.rsqrt()
    normalized = inverse_sqrt[:, None] * raw * inverse_sqrt[None, :]
    return normalized, raw, positions, torch.stack((sources, destinations))


def make_model(
    model_type: str,
    split: GraphSplit,
    hidden_dim: int,
    dropout: float,
) -> GridPredictor:
    adjacency, mask, positions, endpoints = make_adjacency(split)
    model = GridPredictor(
        model_type=model_type,
        node_features=split.node_features.shape[-1],
        edge_features=split.edge_features.shape[-1],
        line_positions=positions,
        line_sources=endpoints[0],
        line_destinations=endpoints[1],
        adjacency=adjacency if model_type == "gcn" else mask,
        directed_sources=split.edge_index[0, 0],
        directed_destinations=split.edge_index[0, 1],
        hidden_dim=hidden_dim,
        dropout=dropout,
    )
    return model


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def _batches(count: int, batch_size: int, shuffle: bool, generator: torch.Generator):
    order = torch.randperm(count, generator=generator) if shuffle else torch.arange(count)
    for start in range(0, count, batch_size):
        yield order[start : start + batch_size]


@torch.no_grad()
def predict_logits(
    model: GridPredictor,
    split: GraphSplit,
    batch_size: int = 256,
) -> torch.Tensor:
    model.eval()
    outputs = []
    for indices in _batches(len(split), batch_size, False, torch.Generator()):
        outputs.append(
            model(
                split.node_features[indices],
                split.edge_features[indices],
                split.edge_in_service[indices],
            )
        )
    return torch.cat(outputs, dim=0)


def _binary_counts(target: np.ndarray, predicted: np.ndarray) -> tuple[int, int, int]:
    tp = int(np.logical_and(target == 1, predicted == 1).sum())
    fp = int(np.logical_and(target == 0, predicted == 1).sum())
    fn = int(np.logical_and(target == 1, predicted == 0).sum())
    return tp, fp, fn


def _prf(target: np.ndarray, predicted: np.ndarray) -> tuple[float, float, float]:
    tp, fp, fn = _binary_counts(target, predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _average_precision(target: np.ndarray, score: np.ndarray) -> float | None:
    positives = int(target.sum())
    if positives == 0 or positives == len(target):
        return None
    order = np.argsort(-score, kind="stable")
    ranked = target[order]
    precision = np.cumsum(ranked) / (np.arange(len(ranked)) + 1)
    return float((precision * ranked).sum() / positives)


def _roc_auc(target: np.ndarray, score: np.ndarray) -> float | None:
    positives = int(target.sum())
    negatives = len(target) - positives
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(score, kind="stable")
    sorted_score = score[order]
    ranks = np.empty(len(score), dtype=np.float64)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and sorted_score[stop] == sorted_score[start]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2.0
        start = stop
    rank_sum = ranks[target == 1].sum()
    return float((rank_sum - positives * (positives + 1) / 2) / (positives * negatives))


def select_threshold(
    targets: np.ndarray,
    probabilities: np.ndarray,
    candidates: np.ndarray | None = None,
) -> tuple[float, float]:
    """Select a validation threshold maximizing pooled/micro F1."""
    if candidates is None:
        candidates = np.linspace(0.01, 0.99, 99)
    best_threshold = 0.5
    best_f1 = -1.0
    for threshold in candidates.tolist():
        _, _, f1 = _prf(targets.reshape(-1), (probabilities >= threshold).astype(np.uint8).reshape(-1))
        if f1 > best_f1 or (f1 == best_f1 and threshold > best_threshold):
            best_threshold, best_f1 = float(threshold), float(f1)
    return best_threshold, best_f1


def evaluate_predictions(
    targets: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Calculate pooled, subset, and per-line multi-label classification metrics."""
    target = targets.astype(np.uint8)
    predicted = (probabilities >= threshold).astype(np.uint8)
    precision, recall, micro_f1 = _prf(target.reshape(-1), predicted.reshape(-1))
    per_line = []
    per_line_f1 = []
    for line_position in range(target.shape[1]):
        p, r, f1 = _prf(target[:, line_position], predicted[:, line_position])
        per_line.append(
            {
                "line_position": line_position,
                "precision": p,
                "recall": r,
                "f1": f1,
                "positive_support": int(target[:, line_position].sum()),
            }
        )
        per_line_f1.append(f1)
    flattened_target = target.reshape(-1)
    flattened_score = probabilities.reshape(-1)
    ap = _average_precision(flattened_target, flattened_score)
    auc = _roc_auc(flattened_target, flattened_score)
    metrics = {
        "precision": precision,
        "recall": recall,
        "f1": micro_f1,
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": micro_f1,
        "macro_f1": float(np.mean(per_line_f1)),
        "pr_auc_average_precision": ap,
        "roc_auc": auc,
        "exact_match_accuracy": float(np.all(predicted == target, axis=1).mean()),
        "average_predicted_failures_per_sample": float(predicted.sum(axis=1).mean()),
        "average_true_failures_per_sample": float(target.sum(axis=1).mean()),
        "threshold": float(threshold),
        "sample_count": int(len(target)),
    }
    return metrics, per_line


def _weighted_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    return F.binary_cross_entropy_with_logits(logits, target, pos_weight=weights)


def _loss_over_split(
    model: GridPredictor,
    split: GraphSplit,
    weights: torch.Tensor,
    batch_size: int,
) -> float:
    model.eval()
    total = 0.0
    count = 0
    with torch.no_grad():
        for indices in _batches(len(split), batch_size, False, torch.Generator()):
            loss = _weighted_loss(
                model(
                    split.node_features[indices],
                    split.edge_features[indices],
                    split.edge_in_service[indices],
                ),
                split.targets[indices],
                weights,
            )
            total += float(loss) * len(indices)
            count += len(indices)
    return total / max(count, 1)


def train_model(
    model_type: str,
    bundle: DatasetBundle,
    stats: dict[str, torch.Tensor],
    config: dict[str, Any],
    checkpoint_path: str | Path,
) -> tuple[GridPredictor, list[dict[str, Any]], float, dict[str, Any], list[dict[str, Any]]]:
    """Train one model with validation-loss early stopping and save best weights."""
    seed_everything(int(config["seed"]))
    normalized = {
        name: normalize_split(bundle.by_name(name), stats) for name in SPLITS
    }
    train = normalized["train"]
    validation = normalized["validation"]
    weights = positive_weights(train.targets)
    model = make_model(
        model_type,
        train,
        int(config["hidden_dim"]),
        float(config["dropout"]),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["learning_rate"]))
    shuffle_generator = torch.Generator().manual_seed(int(config["seed"]))
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    best_state = None
    best_epoch = 0
    stale_epochs = 0
    started = time.perf_counter()
    for epoch in range(1, int(config["epochs"]) + 1):
        model.train()
        for indices in _batches(len(train), int(config["batch_size"]), True, shuffle_generator):
            optimizer.zero_grad(set_to_none=True)
            logits = model(
                train.node_features[indices],
                train.edge_features[indices],
                train.edge_in_service[indices],
            )
            loss = _weighted_loss(logits, train.targets[indices], weights)
            loss.backward()
            optimizer.step()
        train_loss = _loss_over_split(
            model, train, weights, int(config["batch_size"])
        )
        validation_loss = _loss_over_split(
            model, validation, weights, int(config["batch_size"])
        )
        history.append(
            {
                "model": model_type,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
            }
        )
        if validation_loss < best_loss - 1e-6:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= int(config["patience"]):
                break
    if best_state is None:
        raise RuntimeError(f"{model_type}: training produced no checkpoint")
    model.load_state_dict(best_state)
    validation_probabilities = torch.sigmoid(
        predict_logits(model, validation, int(config["batch_size"]))
    ).cpu().numpy()
    threshold, _ = select_threshold(
        validation.targets.cpu().numpy(), validation_probabilities
    )
    validation_metrics, validation_lines = evaluate_predictions(
        validation.targets.cpu().numpy(), validation_probabilities, threshold
    )
    checkpoint = {
        "model_type": model_type,
        "model_state_dict": best_state,
        "normalization": {key: value.cpu() for key, value in stats.items()},
        "config": dict(config),
        "threshold": threshold,
        "line_indices": bundle.train.line_indices,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "training_seconds": time.perf_counter() - started,
        "positive_weights": weights,
    }
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, path)
    return model, history, threshold, validation_metrics, validation_lines


def load_checkpoint(path: str | Path, split: GraphSplit) -> tuple[GridPredictor, dict[str, Any]]:
    """Reconstruct a predictor and restore its checkpoint state."""
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    model = make_model(
        checkpoint["model_type"],
        split,
        int(checkpoint["config"]["hidden_dim"]),
        float(checkpoint["config"]["dropout"]),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint


def run_training(
    output_dir: str | Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Train MLP, GCN, and GAT in order; evaluate test only after threshold freeze."""
    output = Path(output_dir)
    bundle = load_dataset(output)
    stats = fit_normalization(bundle.train)
    normalized = {name: normalize_split(bundle.by_name(name), stats) for name in SPLITS}
    metadata = pd.read_csv(output / "gnn_samples_metadata.csv")
    test_metadata = metadata.loc[metadata["split"] == "test"].set_index("sample_id")
    ordered_test_metadata = test_metadata.loc[bundle.test.sample_ids]
    models_dir = output / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    histories: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    metrics_by_model: dict[str, Any] = {}
    per_line_frames = []
    robustness_records = []
    thresholds: dict[str, float] = {}
    training_seconds: dict[str, float] = {}
    for model_type in MODEL_TYPES:
        model, history, threshold, validation_metrics, _ = train_model(
            model_type,
            bundle,
            stats,
            config,
            models_dir / f"best_{model_type}.pt",
        )
        histories.extend(history)
        thresholds[model_type] = threshold
        saved_checkpoint = torch.load(
            models_dir / f"best_{model_type}.pt", map_location="cpu", weights_only=False
        )
        training_seconds[model_type] = float(saved_checkpoint["training_seconds"])
        test = normalized["test"]
        probabilities = torch.sigmoid(
            predict_logits(model, test, int(config["batch_size"]))
        ).cpu().numpy()
        test_metrics, line_metrics = evaluate_predictions(
            test.targets.cpu().numpy(), probabilities, threshold
        )
        test_metrics["best_epoch"] = int(saved_checkpoint["best_epoch"])
        test_metrics["training_seconds"] = training_seconds[model_type]
        metrics_by_model[model_type] = test_metrics
        comparisons.append(
            {
                "model": model_type.upper(),
                "validation_f1_at_selected_threshold": validation_metrics["micro_f1"],
                **test_metrics,
            }
        )
        for position, record in enumerate(line_metrics):
            per_line_frames.append(
                {"model": model_type.upper(), "line_index": int(test.line_indices[position]), **record}
            )
        capacity = ordered_test_metadata["capacity_scale"].to_numpy(dtype=float)
        true = test.targets.cpu().numpy()
        robustness_bins = (
            ("extreme", capacity < 0.005),
            ("high", (capacity >= 0.005) & (capacity < 0.0125)),
            ("moderate", capacity >= 0.0125),
        )
        for label, mask in robustness_bins:
            if mask.any():
                stress_metrics, _ = evaluate_predictions(
                    true[mask], probabilities[mask], threshold
                )
                robustness_records.append(
                    {
                        "model": model_type.upper(),
                        "capacity_scale_range": label,
                        "minimum_capacity_scale": float(capacity[mask].min()),
                        "maximum_capacity_scale": float(capacity[mask].max()),
                        **stress_metrics,
                    }
                )

    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(histories).to_csv(output / "gnn_training_history.csv", index=False)
    pd.DataFrame(comparisons).to_csv(output / "gnn_model_comparison.csv", index=False)
    pd.DataFrame(per_line_frames).to_csv(output / "gnn_per_line_metrics.csv", index=False)
    pd.DataFrame(robustness_records).to_csv(output / "gnn_stress_robustness.csv", index=False)
    (output / "gnn_decision_thresholds.json").write_text(
        json.dumps(thresholds, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "gnn_test_metrics.json").write_text(
        json.dumps(metrics_by_model, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output / "gnn_training_summary.json").write_text(
        json.dumps(
            {
                "configuration": config,
                "training_seconds_by_model": training_seconds,
                "total_training_seconds": float(sum(training_seconds.values())),
                "positive_weight_policy": "train-only negative/positive ratio clipped to [1, 20]",
                "early_stopping": "minimum validation BCE loss",
                "threshold_selection": "validation pooled micro F1; frozen before test evaluation",
                "normalization": {
                    key: value.cpu().tolist() for key, value in stats.items()
                },
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return {
        "metrics": metrics_by_model,
        "thresholds": thresholds,
        "history": histories,
        "comparison": comparisons,
        "per_line": per_line_frames,
        "robustness": robustness_records,
    }
