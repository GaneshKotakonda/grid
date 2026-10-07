"""End-to-End GridResilience Demo Script.

Demonstrates full incident lifecycle:
Contingency -> Predictive GCN -> PPO Mitigation -> Cascade Outcome -> Recovery -> Restored Grid.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import EndToEndPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run End-to-End GridResilience Demo.")
    parser.add_argument("--line-outage", type=int, default=2, help="Initial tripped line index (default: 2)")
    parser.add_argument("--load-scale", type=float, default=1.10, help="Grid load scale factor (default: 1.10)")
    parser.add_argument("--capacity-scale", type=float, default=0.025, help="Line capacity scale (default: 0.025)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print("=" * 80)
    print("GRIDRESILIENCE END-TO-END DEMO: CONTINGENCY -> MITIGATION -> RECOVERY")
    print("=" * 80)

    scenario = {
        "scenario_id": "demo_contingency_1",
        "load_scale": args.load_scale,
        "generation_scale": 1.0,
        "capacity_scale": args.capacity_scale,
        "initial_outages": [args.line_outage],
    }

    print(f"\n[PHASE 1: CONTINGENCY INITIALIZATION]")
    print(f"  Target Grid: IEEE-14 Bus Network")
    print(f"  Operating Point: Load Scale = {args.load_scale:.2f}, Capacity Scale = {args.capacity_scale:.4f}")
    print(f"  Triggering Initial Outage: Transmission Line {args.line_outage}")

    pipeline = EndToEndPipeline()
    result = pipeline.run_incident(scenario, enable_mitigation=True, enable_recovery=True, seed=args.seed)

    print(f"\n[PHASE 2 & 3: MITIGATION & CASCADE DYNAMICS]")
    print(f"  Initial Grid Load: {result['initial_load_mw']:.2f} MW")
    print(f"  PPO Mitigation Actions Taken: {result['mitigation_actions']}")
    print(f"  Post-Cascade Tripped Lines: {result['post_cascade_status']}")
    print(f"  Post-Cascade Load Served: {result['post_cascade_served_mw']:.2f} MW ({(result['post_cascade_served_mw']/result['initial_load_mw']*100):.1f}%)")

    print(f"\n[PHASE 4: POST-CASCADE RECOVERY & RESTORATION]")
    print(f"  Recovery Steps Executed: {result['recovery_steps']}")
    print(f"  Lines Reconnected: {result['reconnected_lines']}")
    print(f"  Customer Load Restored: +{result['mw_restored']:.2f} MW")
    print(f"  Final Load Served: {result['final_restored_mw']:.2f} MW ({result['final_load_served_percent']:.1f}%)")
    print(f"  Final Operating State: {result['final_status']}")

    print("\n[STEP-BY-STEP INCIDENT AUDIT TRAIL]")
    for item in result["audit_log"]:
        stage = item.get("stage")
        if "MITIGATION_STEP" in stage:
            print(f"  [{stage}] Action: {item['action']} | Load Served: {item['load_served_percent']}% | Status: {item['final_status']}")
        elif "RECOVERY_STEP" in stage:
            print(f"  [{stage}] Action: {item['action']} | Committed: {item['committed']} | Served: {item['served_load_mw']} MW | {item['reason']}")

    print("\n" + "=" * 80)
    print("DEMO COMPLETE: System successfully transitioned from damage to restored operation.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
