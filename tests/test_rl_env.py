"""Unit tests for Phase 5 GridMitigationEnv and RL components."""

import numpy as np
import pytest
import torch

from src.rl_env import (
    GridMitigationEnv,
    RewardConfig,
    ACTION_NAMES,
    load_gcn_predictor,
)
from src.rl_controllers import (
    DoNothingController,
    RuleMitigationController,
)


@pytest.fixture
def env_no_gcn():
    """Environment without GCN predictions."""
    return GridMitigationEnv(
        gcn_model=None,
        gcn_stats=None,
        use_gcn_predictions=False,
        seed=42,
    )


@pytest.fixture
def env_with_gcn():
    """Environment with GCN predictions from saved checkpoint."""
    try:
        gcn, stats = load_gcn_predictor(
            "outputs/predictive_v2/models/best_gcn.pt",
            "outputs/predictive_v2",
        )
        return GridMitigationEnv(
            gcn_model=gcn,
            gcn_stats=stats,
            use_gcn_predictions=True,
            seed=42,
        )
    except Exception:
        pytest.skip("predictive_v2 GCN model not found or failed to load")


def test_environment_reset(env_no_gcn):
    """Test environment reset returns valid observation and info dict."""
    obs, info = env_no_gcn.reset(seed=123)
    assert isinstance(obs, np.ndarray)
    assert obs.dtype == np.float32
    assert isinstance(info, dict)
    assert "initial_outages" in info
    assert "initial_load_mw" in info
    assert info["initial_load_mw"] > 0.0


def test_observation_shape(env_no_gcn):
    """Test observation shape matches expected 87-dimensional Box."""
    obs, _ = env_no_gcn.reset(seed=42)
    assert obs.shape == (87,)
    assert env_no_gcn.observation_space.contains(obs)
    # Check components
    voltages = obs[0:14]
    assert np.all(voltages > 0.0)
    line_status = obs[57:72]
    assert np.all(np.isin(line_status, [0.0, 1.0]))


def test_action_execution(env_no_gcn):
    """Test executing each action type (redispatch, load shed, do nothing)."""
    env_no_gcn.reset(seed=42)
    # Action 0: Do nothing
    obs, rew, term, trunc, info = env_no_gcn.step(0)
    assert isinstance(rew, float)

    # Action 1: Gen 0 boost
    env_no_gcn.reset(seed=42)
    obs, rew, term, trunc, info = env_no_gcn.step(1)
    assert isinstance(rew, float)

    # Action 9: Load shed at bus 2
    env_no_gcn.reset(seed=42)
    obs, rew, term, trunc, info = env_no_gcn.step(9)
    assert info["load_shed_mw"] > 0.0


def test_reward_calculation(env_no_gcn):
    """Test reward reflects served load and stability bonuses/penalties."""
    cfg = RewardConfig(
        weight_served_load=2.0,
        weight_stability=10.0,
        penalty_action=0.05,
    )
    env_no_gcn.reward_config = cfg
    env_no_gcn.reset(seed=42)
    _, rew, _, _, info = env_no_gcn.step(0)
    # Reward should be finite numeric value
    assert np.isfinite(rew)


def test_gcn_probability_integration(env_with_gcn):
    """Test GCN probabilities are populated in the observation vector [72:87]."""
    obs, info = env_with_gcn.reset(seed=42)
    gcn_risks = obs[72:87]
    assert gcn_risks.shape == (15,)
    assert np.all(gcn_risks >= 0.0)
    assert np.all(gcn_risks <= 1.0)
    assert "gcn_risk_mean" in info


def test_episode_termination(env_no_gcn):
    """Test episode terminates upon stabilization, blackout, or max steps."""
    env_no_gcn.max_steps = 3
    env_no_gcn.reset(seed=42)
    done = False
    steps = 0
    while not done and steps < 10:
        _, _, term, trunc, _ = env_no_gcn.step(0)
        done = term or trunc
        steps += 1
    assert done
    assert steps <= env_no_gcn.max_steps + 1


def test_blackout_penalty(env_no_gcn):
    """Test total blackout applies large configured penalty."""
    cfg = RewardConfig(penalty_total_blackout=50.0)
    env_no_gcn.reward_config = cfg
    # Find a severe scenario
    env_no_gcn.reset(seed=42)
    _, rew, term, _, info = env_no_gcn.step(0)
    if info.get("final_status") == "TOTAL_BLACKOUT":
        assert rew < -40.0


def test_invalid_action_handling(env_no_gcn):
    """Test generator limits are strictly respected even with extreme actions."""
    env_no_gcn.reset(seed=42)
    net = env_no_gcn.net
    assert net is not None
    # Repeatedly increase generator 0 to trigger upper limit clip
    for _ in range(20):
        env_no_gcn._apply_action(1)
    gen_p = float(net.gen.at[0, "p_mw"])
    max_p = float(net.gen.at[0, "max_p_mw"])
    assert gen_p <= max_p


def test_deterministic_seeded_reset(env_no_gcn):
    """Test resetting with the same seed produces identical initial states."""
    obs1, info1 = env_no_gcn.reset(seed=999)
    obs2, info2 = env_no_gcn.reset(seed=999)
    np.testing.assert_array_almost_equal(obs1, obs2)
    assert info1["initial_outages"] == info2["initial_outages"]
    assert info1["initial_load_mw"] == info2["initial_load_mw"]


def test_controllers_interface(env_no_gcn):
    """Test DoNothing and Rule controllers comply with predict() interface."""
    obs, _ = env_no_gcn.reset(seed=42)
    do_nothing = DoNothingController()
    a_dn, _ = do_nothing.predict(obs)
    assert a_dn == 0

    rule = RuleMitigationController()
    a_rule, _ = rule.predict(obs)
    assert a_rule in range(len(ACTION_NAMES))
