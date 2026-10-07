"""Tests for the Gymnasium GridResilience environment."""

import numpy as np
import pytest

from src.rl_env import GridResilienceEnv


def test_env_initialization():
    env = GridResilienceEnv(observation_mode="flat")
    assert env.action_space.n == 16  # 15 lines + 1 no-op
    assert env.observation_space.shape == (442,)
    assert env.num_lines == 15
    assert env.num_buses == 14


def test_env_reset():
    env = GridResilienceEnv(observation_mode="flat")
    obs, info = env.reset(seed=42)
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (442,)
    assert np.isfinite(obs).all()
    assert "initial_outages" in info
    assert len(info["initial_outages"]) >= 1
    assert info["converged"] is True


def test_env_dict_observation():
    env = GridResilienceEnv(observation_mode="dict")
    obs, info = env.reset(seed=42)
    assert isinstance(obs, dict)
    assert "node_features" in obs
    assert "edge_features" in obs
    assert "line_in_service" in obs
    assert obs["node_features"].shape == (14, 8)
    assert obs["edge_features"].shape == (30, 11)
    assert obs["line_in_service"].shape == (15,)


def test_env_step_no_op():
    env = GridResilienceEnv(stress_profile=None)
    obs, info = env.reset(seed=42, options={"initial_outages": [0]})
    # Take No-Op action (15)
    obs, reward, terminated, truncated, step_info = env.step(15)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert step_info["action"] == 15
    assert step_info["remedial_applied"] is False


def test_env_step_remedial_branch_cut():
    env = GridResilienceEnv(stress_profile=None)
    obs, info = env.reset(seed=42, options={"initial_outages": [0]})
    # Proactively cut line 1
    obs, reward, terminated, truncated, step_info = env.step(1)
    assert step_info["action"] == 1
    assert step_info["remedial_applied"] is True
    assert step_info["failed_lines_count"] >= 2


def test_env_invalid_action():
    env = GridResilienceEnv()
    env.reset(seed=42)
    with pytest.raises(ValueError):
        env.step(99)
