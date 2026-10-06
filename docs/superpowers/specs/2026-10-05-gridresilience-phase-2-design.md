# GridResilience Phase 2 Design

## Purpose and Scope

Phase 2 adds deterministic, automatic cascading-failure simulation and batch contingency scenario generation to the Phase 1 IEEE 14-bus foundation. An initial line outage is followed only by overload-driven line trips. Every solved or failed state is recorded for later research use.

This phase does not add graph neural networks, reinforcement learning, FastAPI, a frontend, recovery actions, load shedding controls, agentic control, or random post-contingency failures. All Phase 1 public behavior and tests remain intact.

## Architecture

### Cascade engine

`src/cascade.py` owns cascade state transitions and exposes:

- `find_overloaded_lines(metrics, overload_threshold=100.0) -> list[int]`
- `simulate_cascade(net, initial_outages, overload_threshold=100.0, max_steps=20) -> tuple[pandapowerNet, dict]`

`simulate_cascade` validates all outage labels, the positive overload threshold, and a non-negative `max_steps`, then deep-copies the input. Duplicate initial outage labels are removed while preserving order.

Step 0 applies all initial outages and solves the grid. Each later step applies exactly the in-service overloaded lines observed in the preceding converged step, then solves again. This representation matches the physical event sequence: each record describes the newly applied trip wave and the network state after that wave.

`max_steps` is the maximum number of automatic overload-trip waves after the initial outage. Therefore the history contains at most `max_steps + 1` records, including step 0. When the limit is reached, candidate overloaded lines remain recorded but are not applied, so the returned final metrics always describe the returned network's most recent solved topology.

The cascade stops with one of five statuses:

- `STABLE`: the last converged solve has no overloaded in-service line and at least 99 percent of initial load remains served;
- `PARTIAL_BLACKOUT`: no overloaded line remains, meaningful load is still served, and more than 1 percent of initial load was lost;
- `TOTAL_BLACKOUT`: no overloaded line remains and served load is approximately zero;
- `NON_CONVERGED`: AC power flow fails after a trip wave;
- `MAX_STEPS_REACHED`: overloaded lines remain but the propagation limit has been reached.

Non-convergence and step-limit termination take precedence over load-based classification. Approximate zero uses a small absolute/relative numerical tolerance and does not change any electrical failure rule.

Each history record contains:

- `step`
- cumulative `failed_lines`
- `newly_failed_lines` applied at that step
- `max_line_loading_percent`
- currently detected `overloaded_lines`
- `min_bus_voltage_pu`
- `served_load_mw`
- `total_generation_mw`
- `converged`
- `error`

The result also contains `status`, `final_status`, `initial_outages`, `failed_lines`, `failure_sequence` grouped by trip wave, `initial_load_mw`, `final_served_load_mw`, `load_lost_mw`, `load_served_percent`, `total_failed_lines`, `cascade_length` (automatic waves only), the configured threshold and limit, and `history`.

### Controlled scenario stressing

`src/scenarios.py` exposes `stress_grid(net, load_scale=1.0, generation_scale=1.0, capacity_scale=1.0)`. It returns a deep copy and scales:

- active and reactive load setpoints by `load_scale`;
- controllable generator active-power setpoints by `generation_scale` while leaving the external grid to balance the solve;
- line current ratings (`max_i_ka`) by `capacity_scale`.

All scale factors must be positive. Transformer limits and unrelated grid elements are unchanged.

The default batch uses three deterministic synthetic stress profiles across every initially in-service IEEE 14-bus line. Every profile and output row carries `is_synthetic_stress=true`:

- `nominal`: load 1.0, generation 1.0, capacity 1.0;
- `stressed`: load 1.2, generation 1.05, capacity 0.02;
- `severe`: load 1.4, generation 1.10, capacity 0.012.

The small capacity factors compensate for the deliberately high thermal ratings in pandapower's built-in case14 data. They change only the overload trigger, not the AC network impedances. Profile values may be recalibrated during implementation if verification shows they fail to produce the required mix of stable and cascading cases; any change must remain deterministic and be documented.

### Scenario generation and persistence

`generate_scenarios(net, profiles=None, line_indices=None, overload_threshold=100.0, max_steps=20)` runs each selected line as a single initial contingency for every profile. Before each contingency it solves the stressed pre-contingency grid to establish served-load baseline, then invokes the cascade engine on an independent copy.

It returns two pandas DataFrames:

- a scenario summary with scenario ID, synthetic-stress marker, profile and scale parameters, JSON initial outages, cascade length, JSON trip-wave sequence, total failed lines, initial and final served load, load lost, load-served percentage, final convergence, final status, and final maximum loading;
- detailed step data with scenario metadata plus every cascade history field. List fields use JSON strings for portable CSV round-tripping.

For non-converged final states, final served load, load lost, total generation, minimum voltage, and maximum loading remain unavailable rather than being reported as zero.

`save_scenario_results(summary, steps, output_dir)` creates the target directory and writes:

- `cascade_scenario_summary.csv`
- `cascade_steps.csv`

## Scripts

`scripts/run_cascade_demo.py` loads IEEE 14-bus, applies a deterministic stressed profile and selected initial outage, prints each cascade record, then prints failed lines, load lost when available, and terminal status.

`scripts/generate_cascade_scenarios.py` runs the three default profiles against all 15 IEEE 14-bus lines and writes both CSV datasets under `outputs/`.

Neither script uses random selection.

## Error Handling

- Unknown line indices raise `ValueError` before any simulation.
- Empty initial outages raise `ValueError` because Phase 2 scenarios require an initiating event.
- Invalid scale factors, thresholds, and step limits raise `ValueError`.
- `LoadflowNotConverged` remains represented through Phase 1 failed metrics and terminates the cascade without raising.
- Unexpected exceptions propagate.
- Scenario generation rejects a stressed pre-contingency operating point that does not converge, naming the profile and scenario rather than manufacturing load-loss values.

## Testing

Tests cover:

- original-network immutability for stress and cascade functions;
- initial outage application and cumulative failed-line history;
- overloaded in-service line detection at a configurable strict threshold;
- overload-driven trip waves with no random failures;
- stable, partial-blackout, total-blackout, maximum-step, and non-converged termination;
- correct step numbering, metrics, failure sequence, and cascade length;
- load, generation, and line-capacity scaling;
- scenario summary and detail schemas;
- CSV creation and JSON list serialization;
- real stressed IEEE 14-bus integration;
- continued success of all Phase 1 tests.

Implementation follows observed red-green test cycles. Final verification runs the cascade demo, the full batch generator, validates both output files, and runs the complete pytest suite.

## Acceptance Criteria

Phase 2 is complete when overloads alone drive every post-initial trip, histories are complete and deterministic, scenario output includes stable and cascading outcomes, both CSVs exist under `outputs/`, the original input networks remain unchanged, all Phase 1 and Phase 2 tests pass, and no Phase 3 functionality is present.
