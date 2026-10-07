"""Baseline and RL mitigation controllers for GridResilience Phase 5."""

from __future__ import annotations

from typing import Any
import numpy as np


class DoNothingController:
    """Baseline A: Always chooses action 0 (do nothing)."""

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> tuple[int, Any]:
        return 0, None


class RuleMitigationController:
    """Baseline B: Heuristic rule-based mitigation controller.

    Inspects line loadings and GCN failure probabilities to apply targeted
    load shedding or generator redispatch before overloads trigger cascading trips.
    """

    def __init__(self, overload_threshold: float = 1.0, gcn_risk_threshold: float = 0.5) -> None:
        self.overload_threshold = overload_threshold
        self.gcn_risk_threshold = gcn_risk_threshold

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> tuple[int, Any]:
        # Observation format:
        # [0:14]    bus_vm_pu
        # [14:28]   bus_net_p
        # [28:42]   bus_net_q
        # [42:57]   line_loading (normalized by 100%, so 1.0 = 100%)
        # [57:72]   line_status
        # [72:87]   gcn_risk
        line_loading = observation[42:57]
        line_status = observation[57:72]
        gcn_risk = observation[72:87]

        # In-service lines
        in_service_mask = line_status > 0.5
        overloads = np.where(in_service_mask & (line_loading >= self.overload_threshold))[0]
        high_risk = np.where(in_service_mask & (gcn_risk >= self.gcn_risk_threshold))[0]

        if len(overloads) == 0 and len(high_risk) == 0:
            return 0, None  # Grid is operating within limits; do nothing

        # Identify most severe line: either highest overload or highest GCN risk
        combined_severity = np.zeros(15, dtype=np.float32)
        combined_severity[in_service_mask] = line_loading[in_service_mask] + 0.5 * gcn_risk[in_service_mask]
        worst_line = int(np.argmax(combined_severity))

        # Heuristic mitigation mapping for IEEE-14:
        # Lines connected to major load buses:
        # Lines 0, 1, 2, 3, 4 connect buses (0,1), (0,2), (1,2), (1,3), (1,4)
        # Bus 2 is the largest load (94.2 MW); Bus 3 is second (47.8 MW)
        if worst_line in (1, 2, 5):  # Lines connected to bus 2
            return 9, None  # Shed 15% load at Bus 2
        elif worst_line in (3, 6, 7):  # Lines connected to bus 3
            return 10, None  # Shed 15% load at Bus 3
        elif worst_line in (0, 4):  # Lines connected to bus 1
            return 11, None  # Shed 15% load at Bus 1
        elif worst_line in (9, 10, 11, 12, 13, 14):  # Higher bus lines (near bus 8)
            return 12, None  # Shed 15% load at Bus 8
        elif len(overloads) >= 2:
            return 13, None  # Uniform 5% emergency load shed
        else:
            # Fallback to generator 0 or 1 redispatch
            return 1, None  # Boost gen 0


class PPOController:
    """Wrapper around trained SB3 PPO policy."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> tuple[int, Any]:
        action, states = self.model.predict(observation, deterministic=deterministic)
        return int(action), states
