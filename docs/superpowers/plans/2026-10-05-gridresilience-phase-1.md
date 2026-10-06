# GridResilience Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python foundation that loads the IEEE 14-bus network, solves its baseline state, simulates one copied line outage, compares both states, and writes a reproducible CSV report.

**Architecture:** `grid_loader` owns built-in-network creation and validation, `metrics` owns solved-result extraction and comparison, and `simulator` owns pandapower execution plus copy-isolated contingencies. A thin deterministic script composes those modules and writes output; tests exercise real IEEE 14-bus behavior except for an explicitly mocked solver non-convergence.

**Tech Stack:** Python 3.11+, pandapower 3.x, pandas 2.x, NumPy 1.26–2.x, pytest 9.x

**Spec:** `docs/superpowers/specs/2026-10-05-gridresilience-phase-1-design.md`

## Global Constraints

- Implement Phase 1 only: no GNN, reinforcement learning, FastAPI, frontend, agentic AI, cascading failures, or recovery.
- Use `pandapower.networks.case14()`; do not manually encode the IEEE network.
- `simulate_line_outage` must deep-copy and never mutate its input network.
- Total generation is solved `res_gen.p_mw` plus solved `res_ext_grid.p_mw`.
- Served load includes only in-service loads on in-service buses with finite solved voltage.
- A line is overloaded only when it is in service and `loading_percent > 100`.
- Unexpected exceptions propagate; only `LoadflowNotConverged` becomes failed metrics.
- The demo is deterministic and writes `outputs/baseline_results.csv`.
- Production code follows observed red-green test cycles.

## Review Focus

- A configured but out-of-service load must not count as served; Task 2 adds `test_served_load_excludes_out_of_service_load`.
- A load on an out-of-service bus must not count even if a stale voltage exists; Task 2 adds `test_served_load_excludes_out_of_service_bus`.
- Networks with empty generator or external-grid result tables must still produce a numeric generation total; Task 2 adds `test_total_generation_handles_empty_result_tables`.
- An unknown line label must not be silently treated as a valid outage target; Task 3 adds `test_line_outage_rejects_unknown_index`.
- A failed post-outage solve must not turn unavailable after-values into misleading zeros; Task 4 adds `test_comparison_preserves_unavailable_after_values`.

---

### Task 1: Dependencies and IEEE 14-Bus Loader

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/grid_loader.py`
- Create: `tests/test_grid_loader.py`

**Interfaces:**
- Consumes: `pandapower.networks.case14()`
- Produces: `load_ieee14() -> pandapowerNet`

- [ ] **Step 1: Declare runtime and test dependencies**

Add compatible constraints for `pandapower>=3.5,<4`, `pandas>=2.3,<3`, `numpy>=1.26,<2.5`, and `pytest>=9,<10`, then install them with `python3 -m pip install -r requirements.txt`.

- [ ] **Step 2: Write the failing loader test**

Add `test_load_ieee14_returns_valid_network`, asserting 14 buses and non-empty `line`, `load`, and `gen` tables. Add parametrized `test_load_ieee14_rejects_missing_required_elements`, monkeypatching `case14()` to return a real IEEE 14-bus network with one required table emptied and asserting the table name appears in `ValueError`.

- [ ] **Step 3: Run the loader test to verify RED**

Run: `python3 -m pytest tests/test_grid_loader.py -v`

Expected: collection/import failure because `src.grid_loader` does not exist.

- [ ] **Step 4: Implement `load_ieee14() -> pandapowerNet`**

Call `pandapower.networks.case14()`, require non-empty `bus`, `line`, `load`, and `gen` tables, name the missing element in `ValueError`, and return the network.

- [ ] **Step 5: Run the loader test to verify GREEN**

Run: `python3 -m pytest tests/test_grid_loader.py -v`

Expected: all loader tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add requirements.txt src/__init__.py src/grid_loader.py tests/test_grid_loader.py
git commit -m "feat: load and validate IEEE 14-bus grid"
```

### Task 2: Solved-Network Metric Extraction

**Files:**
- Create: `src/metrics.py`
- Create: `tests/test_simulator.py`

**Interfaces:**
- Consumes: a converged `pandapowerNet` with pandapower result tables
- Produces: `extract_grid_metrics(net) -> dict[str, Any]`
- Produces: `failed_grid_metrics(error: str) -> dict[str, Any]`

- [ ] **Step 1: Write failing metric-extraction tests**

Add these tests using a real solved IEEE 14-bus network:

- `test_metrics_contain_expected_line_bus_and_summary_fields`: assert the exact line columns (`line_index`, `from_bus`, `to_bus`, `in_service`, `active_power_mw`, `loading_percent`), bus columns (`bus_index`, `voltage_pu`, `supplied`), and all aggregate keys from the spec.
- `test_total_generation_includes_external_grid`: assert `total_generation_mw == res_gen.p_mw.sum() + res_ext_grid.p_mw.sum()` with numeric approximation.
- `test_served_load_excludes_unsupplied_bus`: replace one loaded bus's solved voltage with `NaN` and assert its `res_load.p_mw` is excluded.
- `test_served_load_excludes_out_of_service_load`: mark one load out of service after solving and assert its solved active power is excluded.
- `test_served_load_excludes_out_of_service_bus`: mark one loaded bus out of service after solving and assert loads at that bus are excluded despite the existing solved voltage.
- `test_total_generation_handles_empty_result_tables`: empty both generation result tables and assert a `0.0` total.
- `test_failed_metrics_are_explicit_and_empty`: assert `converged=False`, the supplied error text, empty line/bus frames, unavailable aggregates, and an empty overloaded-line list.

- [ ] **Step 2: Run metric tests to verify RED**

Run: `python3 -m pytest tests/test_simulator.py -v`

Expected: collection/import failure because `src.metrics` does not exist.

- [ ] **Step 3: Implement `extract_grid_metrics(net) -> dict[str, Any]`**

Join line metadata to `res_line` by index and use signed `p_from_mw`. Determine supplied buses from bus status and finite `res_bus.vm_pu`; calculate served load by aligning `load`, `res_load`, and supplied buses; add `res_gen` and `res_ext_grid` active power for total generation; derive maximum loading, minimum voltage, and sorted overloaded indices.

- [ ] **Step 4: Implement `failed_grid_metrics(error: str) -> dict[str, Any]`**

Return the same stable schema as successful metrics with empty typed DataFrames, `None` aggregate values, `converged=False`, and the error string.

- [ ] **Step 5: Run metric tests to verify GREEN**

Run: `python3 -m pytest tests/test_simulator.py -v`

Expected: all Task 2 tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/metrics.py tests/test_simulator.py
git commit -m "feat: extract solved grid metrics"
```

### Task 3: Baseline and Copy-Isolated Outage Simulation

**Files:**
- Create: `src/simulator.py`
- Modify: `tests/test_simulator.py`

**Interfaces:**
- Consumes: `extract_grid_metrics(net)` and `failed_grid_metrics(error)` from Task 2
- Produces: `run_power_flow(net) -> dict[str, Any]`
- Produces: `simulate_line_outage(net, line_index) -> tuple[pandapowerNet, dict[str, Any]]`

- [ ] **Step 1: Write failing simulation tests**

Add:

- `test_normal_power_flow_converges`: assert `run_power_flow(load_ieee14())["converged"] is True` and required fields exist.
- `test_line_outage_does_not_modify_original`: snapshot the original line status column and assert exact equality after simulation.
- `test_selected_line_is_disconnected_only_in_copy`: assert the chosen copied status is false and the original status remains true.
- `test_line_outage_returns_expected_metric_fields`: assert the copied network and stable metric schema are returned.
- `test_line_outage_rejects_unknown_index`: assert `ValueError` for a label absent from `net.line.index`.
- `test_non_convergence_returns_failed_metrics`: mock `pandapower.runpp` to raise `LoadflowNotConverged` and assert failed metrics contain the exception text.

- [ ] **Step 2: Run new simulation tests to verify RED**

Run: `python3 -m pytest tests/test_simulator.py -v`

Expected: import failure because `src.simulator` does not exist.

- [ ] **Step 3: Implement `run_power_flow(net) -> dict[str, Any]`**

Call `pandapower.runpp(net)`, return `extract_grid_metrics(net)` on success, and catch only `pandapower.powerflow.LoadflowNotConverged` to return `failed_grid_metrics(str(error))`.

- [ ] **Step 4: Implement `simulate_line_outage(net, line_index) -> tuple[pandapowerNet, dict[str, Any]]`**

Validate membership in `net.line.index`, deep-copy, disconnect the copied line, call `run_power_flow` on the copy, and return both values.

- [ ] **Step 5: Run the full suite to verify GREEN**

Run: `python3 -m pytest -v`

Expected: all loader, metric, and simulation tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/simulator.py tests/test_simulator.py
git commit -m "feat: simulate isolated line outage"
```

### Task 4: Before/After Comparison

**Files:**
- Modify: `src/metrics.py`
- Modify: `tests/test_simulator.py`

**Interfaces:**
- Consumes: two stable metrics dictionaries from Tasks 2–3
- Produces: `compare_grid_states(baseline, outage) -> dict[str, Any]`

- [ ] **Step 1: Write failing comparison tests**

Add:

- `test_comparison_contains_line_bus_and_summary_changes`: assert `lines` includes identifiers/status, before/after power and loading, and `loading_change_percent`; assert `buses` includes supplied status, before/after voltage, and `voltage_change_pu`; assert summary values include convergence, maximum loadings, minimum voltages, served loads, and before/after overloaded lines.
- `test_comparison_preserves_unavailable_after_values`: compare successful baseline metrics to `failed_grid_metrics(...)` and assert after-state numeric columns in both comparison frames and summary values are `NaN`/`None`, not zero.

- [ ] **Step 2: Run comparison tests to verify RED**

Run: `python3 -m pytest tests/test_simulator.py -v`

Expected: import failure because `compare_grid_states` does not exist.

- [ ] **Step 3: Implement `compare_grid_states(baseline, outage) -> dict[str, Any]`**

Rename before/after metric columns and outer-merge line and bus frames by their indexes. Preserve baseline endpoint metadata; calculate signed after-minus-before loading and voltage changes; return `lines`, `buses`, and the requested scalar/list summary fields in one dictionary. Do not coerce unavailable post-failure data to zero.

- [ ] **Step 4: Run the full suite to verify GREEN**

Run: `python3 -m pytest -v`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/metrics.py tests/test_simulator.py
git commit -m "feat: compare baseline and outage states"
```

### Task 5: Deterministic Demo, CSV, and Documentation

**Files:**
- Create: `scripts/run_baseline.py`
- Create: `README.md`
- Modify: `tests/test_simulator.py`
- Create at runtime: `outputs/baseline_results.csv`

**Interfaces:**
- Consumes: `load_ieee14`, `run_power_flow`, `simulate_line_outage`, and `compare_grid_states`
- Produces: console report and `outputs/baseline_results.csv`

- [ ] **Step 1: Write the failing demo integration test**

Add `test_demo_writes_csv_and_prints_summary`, launching `scripts/run_baseline.py` with the current Python interpreter from the repository root. Assert exit 0, the required report headings, existence of `outputs/baseline_results.csv`, a non-empty CSV, and required before/after line columns.

- [ ] **Step 2: Run the demo test to verify RED**

Run: `python3 -m pytest tests/test_simulator.py::test_demo_writes_csv_and_prints_summary -v`

Expected: FAIL because `scripts/run_baseline.py` does not exist.

- [ ] **Step 3: Write the demo script**

Make direct execution from the repository root import `src`, select the lowest sorted in-service line index, print the exact categories required by the spec, report graceful non-convergence, create `outputs/`, and save the line comparison with `index=False`.

- [ ] **Step 4: Run the demo test and script to verify GREEN**

Run: `python3 -m pytest tests/test_simulator.py::test_demo_writes_csv_and_prints_summary -v`

Expected: PASS.

Run: `python3 scripts/run_baseline.py`

Expected: exit 0, baseline and contingency summaries, and a reported CSV path.

Run: `python3 -c "import pandas as pd; frame = pd.read_csv('outputs/baseline_results.csv'); assert len(frame) > 0; print(frame.columns.tolist())"`

Expected: before/after line comparison columns are present.

- [ ] **Step 5: Write the README**

Describe Phase 1 scope, project layout, metric semantics, installation, `python scripts/run_baseline.py`, `pytest`, CSV location, and explicit Phase 2 exclusions.

- [ ] **Step 6: Run final acceptance verification**

Run: `python3 scripts/run_baseline.py`

Run: `python3 -m pytest -v`

Expected: demo exit 0 and all tests pass with no failures.

- [ ] **Step 7: Review scope and repository diff**

Run: `git status --short && git diff --check && git diff --stat HEAD`

Expected: only Phase 1 source, tests, docs, requirements, and generated CSV are present; `git diff --check` reports no whitespace errors.

- [ ] **Step 8: Commit Task 5**

```bash
git add README.md scripts/run_baseline.py tests/test_simulator.py outputs/baseline_results.csv
git commit -m "docs: add Phase 1 baseline demo"
```
