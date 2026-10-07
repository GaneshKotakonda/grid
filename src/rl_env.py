"""Gymnasium environment for power-grid cascading-failure mitigation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from pandapower.auxiliary import pandapowerNet

from src.cascade import find_overloaded_lines
from src.graph import network_to_graph
from src.grid_loader import load_ieee14
from src.scenarios import DEFAULT_STRESS_PROFILES, stress_grid
from src.simulator import run_power_flow

STRESS_PROFILES = {profile["name"]: profile for profile in DEFAULT_STRESS_PROFILES}


class GridResilienceEnv(gym.Env):
    """Gymnasium environment modeling real-time remedial actions during cascading failure.

    Actions:
        Discrete(num_lines + 1):
            - 0 to num_lines - 1: Proactively trip (disconnect) transmission line i.
            - num_lines: No-Op (take no remedial action).

    Observations:
        - "flat": 1D array concatenating flattened node features (14x8) and edge features (30x11).
        - "dict": Dict containing node_features, edge_features, edge_index, and line_in_service.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        net: pandapowerNet | None = None,
        overload_threshold: float = 100.0,
        max_steps: int = 10,
        stress_profile: str | None = "moderate",
        observation_mode: str = "flat",
        line_trip_penalty: float = 0.05,
    ) -> None:
        super().__init__()
        self.base_net = load_ieee14() if net is None else deepcopy(net)
        self.overload_threshold = float(overload_threshold)
        self.max_steps = int(max_steps)
        self.stress_profile = stress_profile
        self.observation_mode = observation_mode
        self.line_trip_penalty = float(line_trip_penalty)

        self.num_buses = len(self.base_net.bus)
        self.line_indices = sorted(int(idx) for idx in self.base_net.line.index)
        self.num_lines = len(self.line_indices)
        self.num_directed_edges = self.num_lines * 2
        self.action_space = spaces.Discrete(self.num_lines + 1)
        self.no_op_action = self.num_lines

        self.node_dim = 8
        self.edge_dim = 11
        self.flat_obs_dim = (self.num_buses * self.node_dim) + (
            self.num_directed_edges * self.edge_dim
        )

        if self.observation_mode == "flat":
            self.observation_space = spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(self.flat_obs_dim,),
                dtype=np.float32,
            )
        elif self.observation_mode == "dict":
            self.observation_space = spaces.Dict(
                {
                    "node_features": spaces.Box(
                        low=-np.inf,
                        high=np.inf,
                        shape=(self.num_buses, self.node_dim),
                        dtype=np.float32,
                    ),
                    "edge_features": spaces.Box(
                        low=-np.inf,
                        high=np.inf,
                        shape=(self.num_directed_edges, self.edge_dim),
                        dtype=np.float32,
                    ),
                    "line_in_service": spaces.Box(
                        low=0,
                        high=1,
                        shape=(self.num_lines,),
                        dtype=np.int8,
                    ),
                }
            )
        else:
            raise ValueError(f"Unknown observation_mode: {observation_mode}")

        self.current_net: pandapowerNet | None = None
        self.current_metrics: dict[str, Any] | None = None
        self.initial_load_mw: float = 0.0
        self.current_step: int = 0
        self.initial_outages: list[int] = []
        self.failed_lines: set[int] = set()
        self.last_served_load_mw: float = 0.0

    def _get_obs(self) -> np.ndarray | dict[str, np.ndarray]:
        if self.current_net is None or not self.current_metrics.get("converged", False):
            if self.observation_mode == "flat":
                return np.zeros(self.flat_obs_dim, dtype=np.float32)
            return {
                "node_features": np.zeros(
                    (self.num_buses, self.node_dim), dtype=np.float32
                ),
                "edge_features": np.zeros(
                    (self.num_directed_edges, self.edge_dim), dtype=np.float32
                ),
                "line_in_service": np.zeros(self.num_lines, dtype=np.int8),
            }

        graph_sample = network_to_graph(
            net=self.current_net,
            sample_id=f"step_{self.current_step}",
            next_failed_lines=[],
        )

        node_feat = graph_sample.node_features.astype(np.float32)
        edge_feat = graph_sample.edge_features.astype(np.float32)
        in_service = np.array(
            [
                int(bool(self.current_net.line.at[idx, "in_service"]))
                for idx in self.line_indices
            ],
            dtype=np.int8,
        )

        if self.observation_mode == "flat":
            return np.concatenate(
                [node_feat.flatten(), edge_feat.flatten()], dtype=np.float32
            )

        return {
            "node_features": node_feat,
            "edge_features": edge_feat,
            "line_in_service": in_service,
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray | dict[str, np.ndarray], dict[str, Any]]:
        super().reset(seed=seed)
        options = options or {}

        # 1. Prepare base network with optional stress profile
        profile_name = options.get("stress_profile", self.stress_profile)
        if profile_name and profile_name in STRESS_PROFILES:
            cfg = STRESS_PROFILES[profile_name]
            working_net = stress_grid(
                self.base_net,
                load_scale=cfg["load_scale"],
                generation_scale=cfg["generation_scale"],
                capacity_scale=cfg["capacity_scale"],
            )
        else:
            working_net = deepcopy(self.base_net)

        in_service_loads = working_net.load["in_service"].fillna(False).astype(bool)
        self.initial_load_mw = float(working_net.load.loc[in_service_loads, "p_mw"].sum())
        self.last_served_load_mw = self.initial_load_mw
        self.current_step = 0
        self.failed_lines.clear()

        # 2. Pick initial contingency outages
        available_lines = [
            idx
            for idx in self.line_indices
            if bool(working_net.line.at[idx, "in_service"])
        ]
        if "initial_outages" in options:
            self.initial_outages = list(options["initial_outages"])
        else:
            outage_line = int(self.np_random.choice(available_lines))
            self.initial_outages = [outage_line]

        for line_idx in self.initial_outages:
            working_net.line.at[line_idx, "in_service"] = False
            self.failed_lines.add(line_idx)

        # 3. Solve initial post-contingency state
        self.current_net = working_net
        self.current_metrics = run_power_flow(self.current_net)
        if self.current_metrics["converged"]:
            self.last_served_load_mw = float(self.current_metrics["total_load_mw"])

        info = {
            "initial_outages": list(self.initial_outages),
            "initial_load_mw": self.initial_load_mw,
            "converged": bool(self.current_metrics["converged"]),
            "overloaded_lines": self.current_metrics.get("overloaded_lines", []),
        }

        return self._get_obs(), info

    def step(
        self,
        action: int,
    ) -> tuple[np.ndarray | dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        self.current_step += 1
        terminated = False
        truncated = self.current_step >= self.max_steps
        remedial_applied = False
        action_penalty = 0.0

        if not (0 <= action <= self.num_lines):
            raise ValueError(f"Invalid action {action}. Must be in [0, {self.num_lines}]")

        # 1. Apply remedial action if not No-Op
        if action != self.no_op_action:
            target_line = self.line_indices[action]
            if bool(self.current_net.line.at[target_line, "in_service"]):
                self.current_net.line.at[target_line, "in_service"] = False
                self.failed_lines.add(target_line)
                remedial_applied = True
                action_penalty = self.line_trip_penalty

        # 2. If remedial action was taken, re-solve power flow
        if remedial_applied:
            self.current_metrics = run_power_flow(self.current_net)

        # 3. Automatic cascade propagation wave: check for overloads
        newly_tripped_by_cascade: list[int] = []
        if self.current_metrics["converged"]:
            overloaded = find_overloaded_lines(
                self.current_metrics, self.overload_threshold
            )
            for line_idx in overloaded:
                if bool(self.current_net.line.at[line_idx, "in_service"]):
                    self.current_net.line.at[line_idx, "in_service"] = False
                    self.failed_lines.add(line_idx)
                    newly_tripped_by_cascade.append(line_idx)

            if newly_tripped_by_cascade:
                self.current_metrics = run_power_flow(self.current_net)

        # 4. Determine state termination and load metrics
        if not self.current_metrics["converged"]:
            terminated = True
            served_load = 0.0
            terminal_status = "NON_CONVERGED"
        else:
            served_load = float(self.current_metrics["total_load_mw"])
            overloaded_remaining = find_overloaded_lines(
                self.current_metrics, self.overload_threshold
            )
            if served_load <= 1e-4:
                terminated = True
                terminal_status = "TOTAL_BLACKOUT"
            elif not overloaded_remaining and not newly_tripped_by_cascade:
                terminated = True
                terminal_status = (
                    "STABLE"
                    if served_load >= 0.99 * self.initial_load_mw
                    else "PARTIAL_BLACKOUT"
                )
            else:
                terminal_status = "PROPAGATING"

        if truncated and not terminated:
            terminal_status = "MAX_STEPS_REACHED"

        # 5. Compute Reward
        load_fraction = (
            served_load / self.initial_load_mw if self.initial_load_mw > 0 else 0.0
        )
        load_change = (
            (served_load - self.last_served_load_mw) / self.initial_load_mw
            if self.initial_load_mw > 0
            else 0.0
        )

        reward = float(load_fraction + load_change - action_penalty)
        if terminal_status == "STABLE":
            reward += 1.0
        elif terminal_status in ("TOTAL_BLACKOUT", "NON_CONVERGED"):
            reward -= 2.0

        self.last_served_load_mw = served_load

        info = {
            "step": self.current_step,
            "action": action,
            "remedial_applied": remedial_applied,
            "newly_tripped_by_cascade": newly_tripped_by_cascade,
            "failed_lines_count": len(self.failed_lines),
            "served_load_mw": served_load,
            "load_served_percent": load_fraction * 100.0,
            "status": terminal_status,
            "converged": bool(self.current_metrics["converged"]),
        }

        return self._get_obs(), reward, terminated, truncated, info
