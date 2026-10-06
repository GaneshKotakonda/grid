# GridResilience Phase 1 Design

## Purpose

Phase 1 establishes a small, reproducible power-grid simulation foundation for GridResilience. It loads pandapower's built-in IEEE 14-bus network, solves its normal operating state, applies one transmission-line outage to an isolated copy, compares the solved states, and writes a line-level CSV report.

This phase intentionally excludes graph neural networks, reinforcement learning, agentic AI, APIs, user interfaces, cascading-failure simulation, automated recovery, and performance optimization.

## Runtime and Dependencies

- Python 3.11 or newer
- pandapower
- pandas
- numpy
- pytest
- matplotlib is not required by this phase and will not be installed unless a later need appears

`requirements.txt` will use compatible minimum-version constraints rather than exact environment-specific pins.

## Project Layout

```text
gridresilience/
├── src/
│   ├── __init__.py
│   ├── grid_loader.py
│   ├── simulator.py
│   └── metrics.py
├── scripts/
│   └── run_baseline.py
├── tests/
│   ├── test_grid_loader.py
│   └── test_simulator.py
├── outputs/
├── requirements.txt
└── README.md
```

The repository-level `docs/superpowers/` directory contains this design and its implementation plan but is not part of the runtime package.

## Architecture and Interfaces

### Grid loading

`src/grid_loader.py` exposes `load_ieee14()`. It calls `pandapower.networks.case14()` and validates that the returned network contains at least one bus, line, load, and generator. A missing or empty required element raises `ValueError` with the element name.

### Simulation

`src/simulator.py` exposes:

- `run_power_flow(net)`: calls `pandapower.runpp(net)` and returns extracted metrics. It operates on the supplied network because pandapower stores solved result tables on that object.
- `simulate_line_outage(net, line_index)`: validates that `line_index` exists, deep-copies `net`, sets the selected copied line's `in_service` value to `False`, solves the copied network, and returns the copied network plus metrics. It never mutates the caller's network.

Both functions catch pandapower's `LoadflowNotConverged` exception and return a metrics object with `converged=False`, an explanatory error string, empty line and bus result tables, and unavailable aggregate result values. Invalid line indices raise `ValueError` before copying or solving.

### Metrics

`src/metrics.py` provides focused extraction and comparison functions. A converged metrics dictionary contains:

- `converged`
- `error`
- `lines`: a pandas DataFrame with `line_index`, `from_bus`, `to_bus`, `in_service`, `active_power_mw`, and `loading_percent`
- `buses`: a pandas DataFrame with `bus_index`, `voltage_pu`, and `supplied`
- `total_load_mw`
- `total_generation_mw`
- `max_line_loading_percent`
- `min_bus_voltage_pu`
- `overloaded_lines`

`active_power_mw` is pandapower's signed `p_from_mw`. The direction is therefore from the line's configured `from_bus` to `to_bus`.

Total generation is the sum of solved active-power output in `net.res_gen.p_mw` and `net.res_ext_grid.p_mw`. Empty result tables contribute zero.

Served load is not the sum of configured `net.load.p_mw`. A load is counted only when it is in service, its bus is in service, and that bus has a finite solved voltage in `net.res_bus.vm_pu`. For those supplied loads, solved `net.res_load.p_mw` values are summed. This excludes loads on disconnected or otherwise unsupplied buses.

An overloaded line is an in-service line whose solved `loading_percent` is strictly greater than 100.

`compare_grid_states(baseline_metrics, outage_metrics)` produces a dictionary containing summary values, a line-level DataFrame under `lines`, and a bus-level DataFrame under `buses`. The line table contains identifiers and status, before/after active power and loading, and signed after-minus-before loading change. The bus table contains bus identifiers, supplied status, before/after voltage, and signed after-minus-before voltage change. If the outage does not converge, after-state numeric fields remain unavailable rather than being presented as zeros.

## Data Flow

1. Load and validate the built-in IEEE 14-bus network.
2. Solve the original network and extract baseline metrics.
3. Deterministically select the first in-service transmission line by sorted line index.
4. Deep-copy the solved original, disconnect that line on the copy, and solve the copy.
5. Compare baseline and contingency metrics.
6. Print grid counts and the requested before/after summary.
7. Create `outputs/` when necessary and save the line-level comparison to `outputs/baseline_results.csv`.

The original network remains solved in its baseline state and retains its original line status.

## Error Handling

- A malformed built-in network fails fast during loader validation.
- A missing or non-line index raises a clear `ValueError`.
- Normal and outage power-flow non-convergence is represented in returned metrics so the demo can report the failure without a traceback.
- The comparison accepts a failed after-state and preserves baseline values while marking after-state results unavailable.
- Unexpected exceptions are not swallowed.

## Demo Behavior

Running `python scripts/run_baseline.py` from the project root prints:

- the IEEE 14-bus heading and counts of buses, lines, loads, and generators;
- baseline maximum line loading;
- the disconnected line index and endpoint buses;
- after-outage maximum loading, overloaded line indices, minimum voltage, and served load; or a clear non-convergence message;
- the CSV output path.

The script uses no random selection and is therefore repeatable for a fixed pandapower version.

## Testing Strategy

Tests use the real pandapower IEEE 14-bus network except for the explicit non-convergence test. Coverage includes:

- loader returns the expected 14 buses and non-empty line, load, and generator tables;
- normal power flow converges and exposes the required line, bus, and aggregate fields;
- total generation includes solved external-grid contribution;
- served-load calculation excludes an in-service load attached to an unsupplied bus;
- outage simulation does not mutate the original network;
- the selected line is out of service only in the returned copy;
- returned outage metrics expose the expected fields;
- an invalid line index raises `ValueError`;
- mocked `pandapower.runpp()` raising `LoadflowNotConverged` produces `converged=False` metrics;
- comparison output contains the required line, per-bus voltage, and summary fields.

Tests will be written and observed failing before their corresponding production behavior is implemented. Final verification runs the demo script and the full `pytest` suite.

## Acceptance Criteria

Phase 1 is complete when the requested files exist, the demo completes and writes `outputs/baseline_results.csv`, all tests pass, the original network is unchanged by outage simulation, and the final report includes the exact demo and pytest outputs. No Phase 2 functionality is introduced.
