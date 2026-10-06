"""Unit tests for Phase 6 post-cascade recovery environment and pipeline."""

from __future__ import annotations

import copy
from pathlib import Path
import pytest
import numpy as np
import pandapower as pp

from src.grid_loader import load_ieee14
from src.recovery import (
    GridRecoveryEnv,
    GreedyRecoveryController,
    RecoveryConfig,
    check_recovery_safety,
)
from src.pipeline import EndToEndPipeline
from src.rl_env import fast_power_flow


@pytest.fixture
def base_ieee14():
    """Fresh solved IEEE-14 grid fixture."""
    net = load_ieee14()
    fast_power_flow(net)
    return net


@pytest.fixture
def damaged_grid(base_ieee14):
    """Simulated post-cascade grid with line outage and shed load."""
    net = copy.deepcopy(base_ieee14)
    # Disconnect lines 1 and 2
    net.line.at[1, "in_service"] = False
    net.line.at[2, "in_service"] = False
    # Shed 30% load at Bus 2
    b2_loads = net.load.index[net.load["bus"] == 2]
    for idx in b2_loads:
        net.load.at[idx, "p_mw"] *= 0.70
    fast_power_flow(net)
    return net


def test_recovery_environment_initialization(damaged_grid):
    """Test recovery environment sets up state, tracking, and target loads."""
    target_by_bus = {int(b): float(damaged_grid.load.loc[damaged_grid.load["bus"] == b, "p_mw"].sum()) for b in damaged_grid.bus.index}
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus=target_by_bus,
        disconnected_lines=[1, 2],
    )
    assert env.step_count == 0
    assert env.reconnected_lines == []
    assert 1 in env.disconnected_lines
    assert 2 in env.disconnected_lines
    eligible = env.get_eligible_actions()
    action_types = [a["action_type"] for a in eligible]
    assert "do_nothing" in action_types
    assert "reconnect_line" in action_types


def test_line_reconnection(damaged_grid):
    """Test safe line reconnection restores in-service status."""
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus={},
        disconnected_lines=[1, 2],
    )
    action = {"action_type": "reconnect_line", "line_id": 1, "label": "reconnect_line_1"}
    done, safety, info = env.step(action)
    if info["committed"]:
        assert bool(env.net.line.at[1, "in_service"]) is True
        assert 1 in env.reconnected_lines
        assert info["reconnected_lines_count"] == 1


def test_unsafe_action_rejection(base_ieee14):
    """Test action causing thermal/voltage overload is safely rejected without modifying state."""
    net = copy.deepcopy(base_ieee14)
    # Heavily overload a line by scaling load
    net.line.at[0, "max_i_ka"] = 0.001  # Tiny capacity
    cfg = RecoveryConfig(overload_threshold=100.0)
    safety = check_recovery_safety(net, cfg)
    assert safety.is_safe is False
    assert "overloads" in safety.reason or "thermal" in safety.reason.lower()


def test_load_restoration(damaged_grid):
    """Test load restoration increases bus active power towards target."""
    target_by_bus = {2: 100.0}
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus=target_by_bus,
        disconnected_lines=[],
    )
    b2_loads = env.net.load.index[env.net.load["bus"] == 2]
    initial_p = float(env.net.load.loc[b2_loads, "p_mw"].sum())

    action = {"action_type": "restore_load", "bus": 2, "label": "restore_load_bus_2"}
    done, safety, info = env.step(action)
    new_p = float(env.net.load.loc[b2_loads, "p_mw"].sum())

    if info["committed"]:
        assert new_p > initial_p


def test_generator_limit_enforcement(damaged_grid):
    """Test generator power cannot exceed max_p_mw."""
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus={},
        disconnected_lines=[],
    )
    # Set Gen 0 already at maximum
    max_p = float(env.net.gen.at[0, "max_p_mw"]) if "max_p_mw" in env.net.gen else 100.0
    env.net.gen.at[0, "p_mw"] = max_p

    trial_net, safety = env.preview_action({"action_type": "gen_up", "gen_id": 0, "delta_mw": 10.0})
    assert float(trial_net.gen.at[0, "p_mw"]) <= max_p + 1e-4


def test_recovery_termination_on_do_nothing(damaged_grid):
    """Test environment terminates cleanly when do_nothing is selected."""
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus={},
        disconnected_lines=[1],
    )
    done, safety, info = env.step({"action_type": "do_nothing", "label": "do_nothing"})
    assert done is True
    assert info["reason"] == "Recovery terminated by do_nothing"


def test_deterministic_greedy_recovery(damaged_grid):
    """Test greedy controller produces consistent deterministic recovery decisions."""
    target_by_bus = {2: 90.0}
    env1 = GridRecoveryEnv(damaged_net=damaged_grid, initial_target_load_mw=300.0, target_load_by_bus=target_by_bus, disconnected_lines=[1, 2])
    env2 = GridRecoveryEnv(damaged_net=damaged_grid, initial_target_load_mw=300.0, target_load_by_bus=target_by_bus, disconnected_lines=[1, 2])

    controller = GreedyRecoveryController()
    sum1 = controller.run_recovery(env1)
    sum2 = controller.run_recovery(env2)

    assert sum1["reconnected_lines"] == sum2["reconnected_lines"]
    assert sum1["final_served_mw"] == sum2["final_served_mw"]
    assert sum1["recovery_steps"] == sum2["recovery_steps"]


def test_end_to_end_pipeline_execution():
    """Test full pipeline runs from contingency to restored grid without exceptions."""
    pipeline = EndToEndPipeline()
    scenario = {
        "scenario_id": "test_pipeline_0",
        "load_scale": 1.10,
        "generation_scale": 1.0,
        "capacity_scale": 0.02,
        "initial_outages": [1],
    }
    result = pipeline.run_incident(scenario, enable_mitigation=True, enable_recovery=True, seed=42)
    assert "scenario_id" in result
    assert "final_restored_mw" in result
    assert "audit_log" in result
    assert len(result["audit_log"]) >= 3


def test_recovery_served_load_invariant(damaged_grid):
    """Invariant: Recovery actions must never reduce served load below initial recovery level."""
    target_by_bus = {2: 90.0}
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus=target_by_bus,
        disconnected_lines=[1, 2],
    )
    initial_served = env.initial_served_load_mw
    controller = GreedyRecoveryController()
    summary = controller.run_recovery(env)

    # Invariant: final served load must never be lower than initial recovery-state served load
    assert summary["final_served_mw"] >= initial_served - 1e-4
    assert summary["restored_mw"] >= 0.0


def test_non_converged_status_preservation(base_ieee14):
    """Regression test: Non-convergent grid states must remain NON_CONVERGED, never TOTAL_BLACKOUT."""
    # Create non-convergent net by imposing infeasible generator voltage and extreme active load
    net = copy.deepcopy(base_ieee14)
    net.load.loc[:, "p_mw"] *= 50.0  # Massive infeasible load causing non-convergence
    res = check_recovery_safety(net)
    assert res.converged is False

    env = GridRecoveryEnv(
        damaged_net=net,
        initial_target_load_mw=1000.0,
        target_load_by_bus={},
        disconnected_lines=[0, 1],
    )
    controller = GreedyRecoveryController()
    summary = controller.run_recovery(env)

    assert summary["converged"] is False
    assert summary["final_status"] == "NON_CONVERGED"
    assert summary["final_status"] != "TOTAL_BLACKOUT"


def test_stable_grid_status_preservation(damaged_grid):
    """Regression test: Grid with initial STABLE status is not demoted to PARTIAL_BLACKOUT."""
    target_by_bus = {2: 90.0}
    env = GridRecoveryEnv(
        damaged_net=damaged_grid,
        initial_target_load_mw=300.0,
        target_load_by_bus=target_by_bus,
        disconnected_lines=[1, 2],
        initial_status="STABLE",
    )
    controller = GreedyRecoveryController()
    summary = controller.run_recovery(env)

    assert summary["converged"] is True
    assert summary["is_safe"] is True
    assert summary["final_status"] == "STABLE"

