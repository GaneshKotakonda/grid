"""Gymnasium environment for RL-based cascade mitigation on IEEE-14."""

from __future__ import annotations

import copy
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from pandapower.auxiliary import pandapowerNet
import torch

import pandapower as pp
from pandapower.powerflow import LoadflowNotConverged
from src.cascade import find_overloaded_lines, _load_outcome, _load_based_status
from src.gnn_training import GridPredictor, load_checkpoint, load_dataset
from src.graph import network_to_graph
from src.grid_loader import load_ieee14
from src.metrics import extract_grid_metrics, failed_grid_metrics
from src.scenarios import stress_grid
from src.simulator import run_power_flow


def fast_power_flow(net: pandapowerNet) -> dict[str, Any]:
    """Fast AC power flow solver using solution warm-start when available."""
    try:
        init_mode = "results" if ("vm_pu" in net.res_bus and len(net.res_bus) == len(net.bus)) else "auto"
        pp.runpp(net, numba=False, init=init_mode)
    except LoadflowNotConverged:
        return failed_grid_metrics("LoadflowNotConverged")
    except Exception:
        try:
            pp.runpp(net, numba=False, init="auto")
        except Exception as e:
            return failed_grid_metrics(str(e))
    return extract_grid_metrics(net)


ACTION_NAMES = [
    "do_nothing",
    "gen_0_up_10mw",
    "gen_0_down_10mw",
    "gen_1_up_10mw",
    "gen_1_down_10mw",
    "gen_2_up_10mw",
    "gen_2_down_10mw",
    "gen_3_up_10mw",
    "gen_3_down_10mw",
    "shed_bus_2_15pct",
    "shed_bus_3_15pct",
    "shed_bus_1_15pct",
    "shed_bus_8_15pct",
    "shed_uniform_5pct",
]


@dataclass
class RewardConfig:
    """Configurable weights for the multi-objective mitigation reward."""

    weight_served_load: float = 2.0
    weight_stability: float = 10.0
    reward_wave_prevented: float = 3.0
    reward_overload_reduction: float = 1.0
    penalty_line_failure: float = 3.0
    penalty_load_loss: float = 5.0
    penalty_load_shed: float = 1.5
    penalty_action: float = 0.05
    penalty_overload: float = 0.5
    penalty_non_converged: float = 30.0
    penalty_total_blackout: float = 50.0
    penalty_partial_blackout: float = 10.0


def load_gcn_predictor(
    model_path: str | Path,
    dataset_dir: str | Path,
) -> tuple[GridPredictor, dict[str, torch.Tensor]]:
    """Load the trained predictive_v2 GCN model and its normalization statistics."""
    bundle = load_dataset(dataset_dir)
    model, checkpoint = load_checkpoint(model_path, bundle.test)
    model.eval()
    stats = {k: v.to("cpu") for k, v in checkpoint["normalization"].items()}
    return model, stats


# Global template for fast IEEE-14 cloning
_TEMPLATE_IEEE14: pandapowerNet | None = None
_BASE_LOAD_P: np.ndarray | None = None
_BASE_LOAD_Q: np.ndarray | None = None
_BASE_GEN_P: np.ndarray | None = None
_BASE_MAX_I: np.ndarray | None = None

# Precomputed static topology for fast IEEE-14 array operations
_STATIC_INITIALIZED = False
_FROM_BUSES: np.ndarray | None = None
_TO_BUSES: np.ndarray | None = None
_LINE_R: np.ndarray | None = None
_LINE_X: np.ndarray | None = None
_LINE_LEN: np.ndarray | None = None
_LINE_MAX_LOAD: np.ndarray | None = None
_LOAD_BUS: np.ndarray | None = None
_GEN_BUS: np.ndarray | None = None
_EXT_BUS: np.ndarray | None = None


def _init_static_structures(template: pandapowerNet) -> None:
    global _STATIC_INITIALIZED, _FROM_BUSES, _TO_BUSES, _LINE_R, _LINE_X, _LINE_LEN, _LINE_MAX_LOAD, _LOAD_BUS, _GEN_BUS, _EXT_BUS
    if not _STATIC_INITIALIZED:
        _FROM_BUSES = template.line["from_bus"].to_numpy(dtype=int)
        _TO_BUSES = template.line["to_bus"].to_numpy(dtype=int)
        _LINE_R = template.line["r_ohm_per_km"].to_numpy(dtype=float)
        _LINE_X = template.line["x_ohm_per_km"].to_numpy(dtype=float)
        _LINE_LEN = template.line["length_km"].to_numpy(dtype=float)
        _LINE_MAX_LOAD = template.line["max_loading_percent"].to_numpy(dtype=float)
        _LOAD_BUS = template.load["bus"].to_numpy(dtype=int)
        _GEN_BUS = template.gen["bus"].to_numpy(dtype=int)
        _EXT_BUS = template.ext_grid["bus"].to_numpy(dtype=int)
        _STATIC_INITIALIZED = True


def _clone_ieee14(template: pandapowerNet) -> pandapowerNet:
    """Fast shallow clone of IEEE-14 network copying only mutable simulation tables."""
    net = copy.copy(template)
    net.load = template.load.copy()
    net.gen = template.gen.copy()
    net.line = template.line.copy()
    net.bus = template.bus.copy()
    net.ext_grid = template.ext_grid.copy()
    net.res_bus = template.res_bus.copy()
    net.res_line = template.res_line.copy()
    net.res_gen = template.res_gen.copy()
    net.res_load = template.res_load.copy()
    net.res_ext_grid = template.res_ext_grid.copy()
    return net


def _fast_extract_graph_tensors(net: pandapowerNet) -> tuple[np.ndarray, np.ndarray]:
    """Fast vectorized extraction of node and edge feature arrays for GCN model."""
    vm = net.res_bus["vm_pu"].to_numpy()
    va = net.res_bus["va_degree"].to_numpy()
    p_load = np.bincount(_LOAD_BUS, weights=net.res_load["p_mw"].to_numpy(), minlength=14)
    q_load = np.bincount(_LOAD_BUS, weights=net.res_load["q_mvar"].to_numpy(), minlength=14)
    p_gen = np.bincount(_GEN_BUS, weights=net.res_gen["p_mw"].to_numpy(), minlength=14)
    p_gen += np.bincount(_EXT_BUS, weights=net.res_ext_grid["p_mw"].to_numpy(), minlength=14)
    q_gen = np.bincount(_GEN_BUS, weights=net.res_gen["q_mvar"].to_numpy(), minlength=14)
    q_gen += np.bincount(_EXT_BUS, weights=net.res_ext_grid["q_mvar"].to_numpy(), minlength=14)
    in_serv_bus = net.bus["in_service"].to_numpy(dtype=float)
    supplied = in_serv_bus * np.isfinite(vm).astype(float)
    node_features = np.column_stack([vm, va, p_load, q_load, p_gen, q_gen, in_serv_bus, supplied]).astype(np.float32)

    in_serv_line = net.line["in_service"].to_numpy(dtype=float)
    max_i = net.line["max_i_ka"].to_numpy(dtype=float)
    loading = (net.res_line["loading_percent"].to_numpy() * in_serv_line)
    p_from = (net.res_line["p_from_mw"].to_numpy() * in_serv_line)
    q_from = (net.res_line["q_from_mvar"].to_numpy() * in_serv_line)
    p_to = (net.res_line["p_to_mw"].to_numpy() * in_serv_line)
    q_to = (net.res_line["q_to_mvar"].to_numpy() * in_serv_line)

    fwd = np.column_stack([_FROM_BUSES, _TO_BUSES, p_from, q_from, loading, _LINE_R, _LINE_X, in_serv_line, max_i, _LINE_LEN, _LINE_MAX_LOAD])
    bwd = np.column_stack([_TO_BUSES, _FROM_BUSES, p_to, q_to, loading, _LINE_R, _LINE_X, in_serv_line, max_i, _LINE_LEN, _LINE_MAX_LOAD])
    edge_features = np.empty((30, 11), dtype=np.float32)
    edge_features[0::2] = fwd
    edge_features[1::2] = bwd
    return node_features, edge_features


def _get_template() -> tuple[pandapowerNet, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    global _TEMPLATE_IEEE14, _BASE_LOAD_P, _BASE_LOAD_Q, _BASE_GEN_P, _BASE_MAX_I
    if _TEMPLATE_IEEE14 is None:
        _TEMPLATE_IEEE14 = load_ieee14()
        _BASE_LOAD_P = _TEMPLATE_IEEE14.load["p_mw"].to_numpy(dtype=float).copy()
        _BASE_LOAD_Q = _TEMPLATE_IEEE14.load["q_mvar"].to_numpy(dtype=float).copy()
        _BASE_GEN_P = _TEMPLATE_IEEE14.gen["p_mw"].to_numpy(dtype=float).copy()
        _BASE_MAX_I = _TEMPLATE_IEEE14.line["max_i_ka"].to_numpy(dtype=float).copy()
        _init_static_structures(_TEMPLATE_IEEE14)
    return _TEMPLATE_IEEE14, _BASE_LOAD_P, _BASE_LOAD_Q, _BASE_GEN_P, _BASE_MAX_I


class GridMitigationEnv(gym.Env):
    """Gymnasium environment for cascading failure prevention via redispatch and load shed."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        gcn_model: GridPredictor | None = None,
        gcn_stats: dict[str, torch.Tensor] | None = None,
        use_gcn_predictions: bool = True,
        scenarios: list[dict[str, Any]] | None = None,
        reward_config: RewardConfig | None = None,
        overload_threshold: float = 100.0,
        max_steps: int = 10,
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.gcn_model = gcn_model
        self.gcn_stats = gcn_stats
        self.use_gcn_predictions = bool(use_gcn_predictions and gcn_model is not None)
        self.scenarios = scenarios or []
        self.reward_config = reward_config or RewardConfig()
        self.overload_threshold = float(overload_threshold)
        self.max_steps = int(max_steps)
        self.seed(seed)

        self.action_space = spaces.Discrete(len(ACTION_NAMES))
        # 14 bus voltage vm_pu + 14 bus net P + 14 bus net Q + 15 line loading + 15 line status + 15 GCN risk = 87
        self.observation_space = spaces.Box(
            low=-10.0,
            high=10.0,
            shape=(87,),
            dtype=np.float32,
        )

        self.net: pandapowerNet | None = None
        self.last_metrics: dict[str, Any] = {}
        self.last_gcn_probs: np.ndarray = np.zeros(15, dtype=np.float32)
        self.initial_load_mw: float = 0.0
        self.initial_outages: list[int] = []
        self.failed_lines: list[int] = []
        self.step_count: int = 0
        self.total_load_shed_mw: float = 0.0
        self.current_scenario: dict[str, Any] = {}

    def seed(self, seed: int | None = None) -> list[int]:
        self.rng = np.random.default_rng(seed)
        return [seed if seed is not None else 42]

    def _predict_gcn_probabilities(self, net: pandapowerNet) -> np.ndarray:
        """Run GCN forward pass on current solved network state."""
        if not self.use_gcn_predictions or self.gcn_model is None or self.gcn_stats is None:
            return np.zeros(15, dtype=np.float32)

        try:
            nodes, edges = _fast_extract_graph_tensors(net)
            node = torch.from_numpy(nodes).unsqueeze(0)
            edge = torch.from_numpy(edges).unsqueeze(0)
            in_service = torch.from_numpy(
                (edges[:, 7] > 0.5).astype(float)
            ).unsqueeze(0)

            node_norm = (node - self.gcn_stats["node_mean"]) / self.gcn_stats["node_std"]
            edge_norm = (edge - self.gcn_stats["edge_mean"]) / self.gcn_stats["edge_std"]

            with torch.no_grad():
                logits = self.gcn_model(node_norm, edge_norm, in_service)
                probs = torch.sigmoid(logits).cpu().numpy()[0]
            return probs.astype(np.float32)
        except Exception:
            return np.zeros(15, dtype=np.float32)

    def _build_observation(
        self,
        metrics: dict[str, Any],
        gcn_probs: np.ndarray,
    ) -> np.ndarray:
        """Assemble the 87-dimensional normalized observation vector."""
        net = self.net
        assert net is not None

        # 1. Bus voltages (14)
        if metrics["converged"] and "vm_pu" in net.res_bus:
            voltages = net.res_bus["vm_pu"].to_numpy(dtype=np.float32)
        else:
            voltages = np.ones(14, dtype=np.float32)

        # 2. Bus net P and Q (14 each) - fast vectorized bincount
        if metrics["converged"]:
            p_load = np.bincount(_LOAD_BUS, weights=net.res_load["p_mw"].to_numpy(), minlength=14)
            q_load = np.bincount(_LOAD_BUS, weights=net.res_load["q_mvar"].to_numpy(), minlength=14)
            p_gen = np.bincount(_GEN_BUS, weights=net.res_gen["p_mw"].to_numpy(), minlength=14)
            p_gen += np.bincount(_EXT_BUS, weights=net.res_ext_grid["p_mw"].to_numpy(), minlength=14)
            q_gen = np.bincount(_GEN_BUS, weights=net.res_gen["q_mvar"].to_numpy(), minlength=14)
            q_gen += np.bincount(_EXT_BUS, weights=net.res_ext_grid["q_mvar"].to_numpy(), minlength=14)
            bus_p = ((p_gen - p_load) / 100.0).astype(np.float32)
            bus_q = ((q_gen - q_load) / 100.0).astype(np.float32)
        else:
            bus_p = np.zeros(14, dtype=np.float32)
            bus_q = np.zeros(14, dtype=np.float32)

        # 3. Line loadings (15) & Line in_service (15)
        in_serv_line = net.line["in_service"].to_numpy(dtype=np.float32)
        if metrics["converged"] and "loading_percent" in net.res_line:
            loadings = net.res_line["loading_percent"].to_numpy(dtype=np.float32)
            line_loading = np.clip(loadings / 100.0, 0.0, 5.0) * in_serv_line
        else:
            line_loading = np.zeros(15, dtype=np.float32)
        line_status = in_serv_line

        # 4. GCN probabilities (15)
        risk = gcn_probs if self.use_gcn_predictions else np.zeros(15, dtype=np.float32)

        obs = np.concatenate([
            voltages,        # 14
            bus_p,           # 14
            bus_q,           # 14
            line_loading,    # 15
            line_status,     # 15
            risk,            # 15
        ]).astype(np.float32)

        assert obs.shape == (87,), f"Obs shape {obs.shape} != (87,)"
        return np.nan_to_num(obs, nan=0.0, posinf=5.0, neginf=-5.0)

    def _sample_scenario(self) -> dict[str, Any]:
        """Return a scenario dictionary from the scenario pool or generate synthetic stress."""
        if self.scenarios:
            idx = int(self.rng.integers(0, len(self.scenarios)))
            return dict(self.scenarios[idx])

        lines = list(range(15))
        outage_count = 1 if self.rng.random() > 0.2 else 2
        initial_outages = sorted(int(x) for x in self.rng.choice(lines, size=outage_count, replace=False))
        return {
            "load_scale": float(self.rng.uniform(0.8, 1.4)),
            "generation_scale": float(self.rng.uniform(0.9, 1.1)),
            "capacity_scale": float(self.rng.uniform(0.005, 0.02)),
            "initial_outages": initial_outages,
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset environment to the post-contingency state of a scenario."""
        super().reset(seed=seed)
        if seed is not None:
            self.seed(seed)

        if options and "scenario" in options:
            scenario = options["scenario"]
        else:
            scenario = self._sample_scenario()
        self.current_scenario = scenario

        template, base_p, base_q, base_gen, base_max_i = _get_template()
        self.net = _clone_ieee14(template)

        load_scale = float(scenario.get("load_scale", 1.0))
        generation_scale = float(scenario.get("generation_scale", 1.0))
        capacity_scale = float(scenario.get("capacity_scale", 0.01))
        
        load_mult = scenario.get("load_multipliers")
        if isinstance(load_mult, str):
            load_mult = np.asarray(json.loads(load_mult), dtype=float)
        elif load_mult is not None:
            load_mult = np.asarray(load_mult, dtype=float)
        else:
            load_mult = np.ones(len(base_p), dtype=float)

        reactive_mult = scenario.get("reactive_load_multipliers")
        if isinstance(reactive_mult, str):
            reactive_mult = np.asarray(json.loads(reactive_mult), dtype=float)
        elif reactive_mult is not None:
            reactive_mult = np.asarray(reactive_mult, dtype=float)
        else:
            reactive_mult = np.ones(len(base_q), dtype=float)

        dispatch_mw = scenario.get("generator_dispatch_mw")
        if isinstance(dispatch_mw, str):
            dispatch_mw = np.asarray(json.loads(dispatch_mw), dtype=float)
        elif dispatch_mw is not None:
            dispatch_mw = np.asarray(dispatch_mw, dtype=float)
        else:
            dispatch_mw = base_gen * generation_scale

        # Fast vector updates
        self.net.load.loc[:, "p_mw"] = base_p * load_scale * load_mult
        self.net.load.loc[:, "q_mvar"] = base_q * load_scale * reactive_mult
        if "min_p_mw" in self.net.gen and "max_p_mw" in self.net.gen:
            dispatch_mw = np.clip(dispatch_mw, self.net.gen["min_p_mw"].values, self.net.gen["max_p_mw"].values)
        self.net.gen.loc[:, "p_mw"] = dispatch_mw
        self.net.line.loc[:, "max_i_ka"] = base_max_i * capacity_scale

        in_service_load = self.net.load["in_service"].fillna(False).astype(bool)
        self.initial_load_mw = float(self.net.load.loc[in_service_load, "p_mw"].sum())

        # Apply initial outages
        inits = scenario.get("initial_outages", [0])
        if isinstance(inits, str):
            inits = json.loads(inits)
        self.initial_outages = [int(x) for x in inits]
        self.failed_lines = list(self.initial_outages)

        for l in self.initial_outages:
            self.net.line.at[l, "in_service"] = False

        self.step_count = 0
        self.total_load_shed_mw = 0.0

        # Run post-contingency power flow
        metrics = fast_power_flow(self.net)
        self.last_metrics = metrics
        overloaded = find_overloaded_lines(metrics, self.overload_threshold) if metrics["converged"] else []
        gcn_probs = self._predict_gcn_probabilities(self.net)
        self.last_gcn_probs = gcn_probs
        obs = self._build_observation(metrics, gcn_probs)

        info = {
            "initial_outages": list(self.initial_outages),
            "initial_load_mw": self.initial_load_mw,
            "overloaded_lines": list(overloaded),
            "converged": bool(metrics["converged"]),
            "gcn_risk_mean": float(gcn_probs.mean()),
        }
        return obs, info

    def _apply_action(self, action: int) -> float:
        """Apply mitigation action and return MW of load shed (if any)."""
        net = self.net
        assert net is not None
        shed_mw = 0.0

        if action == 0:
            return 0.0

        gen_actions = {
            1: (0, 10.0),   # gen 0 +10 MW
            2: (0, -10.0),  # gen 0 -10 MW
            3: (1, 10.0),   # gen 1 +10 MW
            4: (1, -10.0),  # gen 1 -10 MW
            5: (2, 10.0),   # gen 2 +10 MW
            6: (2, -10.0),  # gen 2 -10 MW
            7: (3, 10.0),   # gen 3 +10 MW
            8: (3, -10.0),  # gen 3 -10 MW
        }
        if action in gen_actions:
            gen_idx, delta = gen_actions[action]
            curr = float(net.gen.at[gen_idx, "p_mw"])
            min_p = float(net.gen.at[gen_idx, "min_p_mw"]) if "min_p_mw" in net.gen else 0.0
            max_p = float(net.gen.at[gen_idx, "max_p_mw"]) if "max_p_mw" in net.gen else 100.0
            new_p = np.clip(curr + delta, min_p, max_p)
            net.gen.at[gen_idx, "p_mw"] = float(new_p)
            return 0.0

        load_bus_targets = {
            9: 2,   # bus 2 (15%)
            10: 3,  # bus 3 (15%)
            11: 1,  # bus 1 (15%)
            12: 8,  # bus 8 (15%)
        }
        if action in load_bus_targets:
            target_bus = load_bus_targets[action]
            matches = net.load.index[net.load["bus"] == target_bus]
            for idx in matches:
                if bool(net.load.at[idx, "in_service"]):
                    p_curr = float(net.load.at[idx, "p_mw"])
                    p_cut = p_curr * 0.15
                    net.load.at[idx, "p_mw"] = max(0.0, p_curr - p_cut)
                    shed_mw += p_cut
            return shed_mw

        if action == 13:
            for idx in net.load.index:
                if bool(net.load.at[idx, "in_service"]):
                    p_curr = float(net.load.at[idx, "p_mw"])
                    p_cut = p_curr * 0.05
                    net.load.at[idx, "p_mw"] = max(0.0, p_curr - p_cut)
                    shed_mw += p_cut
            return shed_mw

        return 0.0

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Apply agent mitigation, propagate power flows, and return reward/next state."""
        self.step_count += 1
        net = self.net
        assert net is not None
        cfg = self.reward_config

        # Measure pre-action overload state
        pre_overloaded = (
            find_overloaded_lines(self.last_metrics, self.overload_threshold)
            if self.last_metrics.get("converged", False)
            else []
        )
        pre_overload_sum = 0.0
        if pre_overloaded and "loading_percent" in net.res_line:
            pre_overload_sum = sum(
                max(0.0, (float(net.res_line.at[l, "loading_percent"]) - self.overload_threshold) / self.overload_threshold)
                for l in pre_overloaded
            )

        # 1. Apply mitigation action
        if action == 0:
            shed_mw = 0.0
            metrics_post_action = self.last_metrics
        else:
            shed_mw = self._apply_action(int(action))
            self.total_load_shed_mw += shed_mw
            metrics_post_action = fast_power_flow(net)

        if not metrics_post_action["converged"]:
            self.last_metrics = metrics_post_action
            obs = self._build_observation(metrics_post_action, np.zeros(15, dtype=np.float32))
            reward = -cfg.penalty_non_converged - cfg.penalty_action * (1.0 if action > 0 else 0.0)
            info = {
                "final_status": "NON_CONVERGED",
                "failed_lines_count": len(self.failed_lines),
                "cascade_length": self.step_count,
                "load_served_percent": 0.0,
                "load_shed_mw": self.total_load_shed_mw,
                "stable": False,
                "action_taken": ACTION_NAMES[action],
                "action_index": int(action),
                "overload_reduced": False,
                "load_preserved": False,
                "cascade_prevented": False,
                "action_converged": False,
            }
            return obs, float(reward), True, False, info

        overloaded = find_overloaded_lines(metrics_post_action, self.overload_threshold)
        post_overload_sum = (
            sum(
                max(0.0, (float(net.res_line.at[l, "loading_percent"]) - self.overload_threshold) / self.overload_threshold)
                for l in overloaded
            )
            if overloaded and "loading_percent" in net.res_line
            else 0.0
        )

        served_mw = float(metrics_post_action["total_load_mw"])
        served_frac = (served_mw / self.initial_load_mw) if self.initial_load_mw > 0 else 1.0
        shed_frac = (shed_mw / self.initial_load_mw) if self.initial_load_mw > 0 else 0.0

        reward = cfg.weight_served_load * served_frac
        reward -= cfg.penalty_load_shed * shed_frac
        if action > 0:
            reward -= cfg.penalty_action

        # Overload reduction reward / penalty
        if pre_overload_sum > 0.0 and post_overload_sum < pre_overload_sum:
            reward += cfg.reward_overload_reduction * (pre_overload_sum - post_overload_sum)
        if len(pre_overloaded) > 0 and len(overloaded) == 0:
            reward += cfg.reward_wave_prevented

        if overloaded:
            reward -= cfg.penalty_overload * post_overload_sum

        terminated = False
        newly_failed = []

        if not overloaded:
            terminated = True
            reward += cfg.weight_stability
            status = "STABLE"
        else:
            newly_failed = list(overloaded)
            for l in newly_failed:
                net.line.at[l, "in_service"] = False
                if l not in self.failed_lines:
                    self.failed_lines.append(l)

            reward -= cfg.penalty_line_failure * len(newly_failed)

            metrics_post_trip = fast_power_flow(net)

            if not metrics_post_trip["converged"]:
                terminated = True
                status = "NON_CONVERGED"
                reward -= cfg.penalty_non_converged
            else:
                final_served = float(metrics_post_trip["total_load_mw"])
                lost_mw, served_pct = _load_outcome(self.initial_load_mw, final_served)
                status = _load_based_status(self.initial_load_mw, final_served, served_pct)

                if lost_mw is not None and self.initial_load_mw > 0:
                    lost_frac = lost_mw / self.initial_load_mw
                    reward -= cfg.penalty_load_loss * lost_frac

                if status == "TOTAL_BLACKOUT":
                    terminated = True
                    reward -= cfg.penalty_total_blackout
                elif status == "PARTIAL_BLACKOUT":
                    reward -= cfg.penalty_partial_blackout * (1.0 - (served_pct or 0.0) / 100.0)

                sec_overloaded = find_overloaded_lines(metrics_post_trip, self.overload_threshold)
                if not sec_overloaded:
                    terminated = True
                    if status != "TOTAL_BLACKOUT":
                        reward += cfg.weight_stability

                metrics_post_action = metrics_post_trip

        truncated = bool(self.step_count >= self.max_steps and not terminated)
        if truncated and not terminated:
            terminated = True
            status = "MAX_STEPS_REACHED"

        self.last_metrics = metrics_post_action

        if not terminated:
            gcn_probs = self._predict_gcn_probabilities(net)
            self.last_gcn_probs = gcn_probs
        else:
            gcn_probs = self.last_gcn_probs

        obs = self._build_observation(metrics_post_action, gcn_probs)

        final_served_pct = (
            float(metrics_post_action["total_load_mw"]) / self.initial_load_mw * 100.0
            if self.initial_load_mw > 0 and metrics_post_action["converged"]
            else 0.0
        )

        overload_reduced = bool(
            (pre_overload_sum > 0.0 and post_overload_sum < pre_overload_sum)
            or (len(pre_overloaded) > 0 and len(overloaded) == 0)
        )
        cascade_prevented = bool(len(newly_failed) == 0)
        load_preserved = bool(final_served_pct >= 90.0)

        info = {
            "final_status": status,
            "failed_lines_count": len(self.failed_lines),
            "newly_failed_lines": newly_failed,
            "cascade_length": self.step_count,
            "load_served_percent": final_served_pct,
            "load_shed_mw": self.total_load_shed_mw,
            "stable": bool(status == "STABLE"),
            "action_taken": ACTION_NAMES[action],
            "action_index": int(action),
            "overload_reduced": overload_reduced,
            "load_preserved": load_preserved,
            "cascade_prevented": cascade_prevented,
            "action_converged": bool(metrics_post_action["converged"]),
        }

        return obs, float(reward), terminated, truncated, info
