"""Demonstration runner for Phase 5 Gymnasium GridResilience environment."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rl_env import GridResilienceEnv


def run_demo_episode(policy_name: str, stress_profile: str = "severe") -> None:
    print(f"\n================ Running Policy: {policy_name} ({stress_profile} stress) ================")
    env = GridResilienceEnv(stress_profile=stress_profile, max_steps=10)
    obs, info = env.reset(seed=42, options={"initial_outages": [5]})

    print(f"Initial Outage: Line {info['initial_outages']}")
    print(f"Initial Load: {info['initial_load_mw']:.2f} MW")

    total_reward = 0.0
    done = False
    step_num = 0

    while not done:
        step_num += 1
        if policy_name == "no_op":
            action = env.no_op_action
        elif policy_name == "random":
            action = env.action_space.sample()
        elif policy_name == "heuristic_cut_overload":
            # Heuristic: Cut the first line that is detected as overloaded
            overloaded = env.current_metrics.get("overloaded_lines", [])
            action = overloaded[0] if overloaded else env.no_op_action
        else:
            action = env.no_op_action

        obs, reward, terminated, truncated, step_info = env.step(action)
        total_reward += reward
        done = terminated or truncated

        action_desc = "No-Op" if action == env.no_op_action else f"Cut Line {action}"
        print(
            f"Step {step_num}: Action={action_desc} | "
            f"Cascade Tripped={step_info['newly_tripped_by_cascade']} | "
            f"Served={step_info['served_load_mw']:.1f} MW ({step_info['load_served_percent']:.1f}%) | "
            f"Reward={reward:+.2f} | Status={step_info['status']}"
        )

    print(f"Outcome: {step_info['status']} | Total Reward: {total_reward:+.2f}")


def main() -> int:
    print("GridResilience Phase 5 - Reinforcement Learning Environment Demo")
    # Compare No-Op (uncontrolled cascade) vs Heuristic Action
    run_demo_episode("no_op", stress_profile="severe")
    run_demo_episode("heuristic_cut_overload", stress_profile="severe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
