# GridResilience Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic overload-driven cascading-failure simulation, controlled IEEE 14-bus stress profiles, and reproducible scenario summary/detail datasets without changing Phase 1 behavior.

**Architecture:** `cascade.py` owns trip-wave state transitions and complete history, while `scenarios.py` owns copy-isolated operating-point stress, batch orchestration, tabular records, and CSV persistence. Two thin scripts demonstrate one cascade and generate the full 45-scenario default batch.

**Tech Stack:** Python 3.11+, pandapower 3.x, pandas 2.x, NumPy, pytest 9.x

**Spec:** `docs/superpowers/specs/2026-10-05-gridresilience-phase-2-design.md`

## Global Constraints

- Preserve all Phase 1 public behavior and keep its tests green.
- Post-initial failures arise only from in-service line loading strictly greater than the configured threshold.
- Deep-copy every caller-owned network before stressing or cascading.
- Step 0 applies the initial outage; `max_steps` caps subsequent automatic trip waves, so history length is at most `max_steps + 1`.
- Never replace unavailable non-converged metrics with zero.
- Batch scenarios and scripts are deterministic and use no random failure injection.
- Implement Phase 2 only: no GNN, RL, API, frontend, recovery, load shedding, or agentic control.
- Every production behavior follows an observed red-green test cycle.

## Review Focus

- A line exactly at the threshold must remain in service because overload is strict `>`; Task 1 adds `test_overload_detection_is_strict_and_in_service_only`.
- Duplicate initial outage labels must be recorded and applied once; Task 1 adds `test_duplicate_initial_outages_are_normalized`.
- `max_steps=0` must still solve and record the initial contingency without applying detected overloads; Task 1 adds `test_zero_max_steps_records_only_initial_state`.
- Non-converged scenario summaries must preserve unavailable numeric values; Task 3 adds `test_non_converged_summary_does_not_report_zero_metrics`.
- CSV list fields must round-trip as valid JSON rather than Python repr strings; Task 3 adds `test_saved_scenario_lists_are_valid_json`.

---

### Task 1: Cascade Engine and Complete History

**Files:**
- Create: `src/cascade.py`
- Create: `tests/test_cascade.py`

**Interfaces:**
- Consumes: `run_power_flow(net) -> dict[str, Any]` from Phase 1
- Produces: `find_overloaded_lines(metrics, overload_threshold=100.0) -> list[int]`
- Produces: `simulate_cascade(net, initial_outages, overload_threshold=100.0, max_steps=20) -> tuple[pandapowerNet, dict[str, Any]]`

- [ ] **Step 1: Write failing overload-detection and cascade tests**

Add tests for strict threshold/in-service filtering, original-network immutability, correct initial outage, duplicate normalization, automatic overload trips, stable termination, maximum-step termination including `max_steps=0`, non-convergence, invalid outage labels/parameters, and exact history/result fields. Use real IEEE networks for copying and stable behavior; use deterministic power-flow fakes only to force precise overload-wave and failure sequences.

- [ ] **Step 2: Run Task 1 tests to verify RED**

Run: `python3 -m pytest tests/test_cascade.py -v`

Expected: collection failure because `src.cascade` does not exist.

- [ ] **Step 3: Implement `find_overloaded_lines`**

Validate a positive threshold, filter the metrics line table by `in_service` and strict `loading_percent > threshold`, and return sorted native-Python line labels.

- [ ] **Step 4: Implement `simulate_cascade`**

Validate and normalize input; deep-copy; iteratively apply the initial wave followed by prior-step overload waves; solve through Phase 1; record every required metric; and stop with `stable`, `non_converged`, or `max_steps` while keeping final topology and metrics aligned.

- [ ] **Step 5: Run Task 1 and Phase 1 tests to verify GREEN**

Run: `python3 -m pytest tests/test_cascade.py tests/test_grid_loader.py tests/test_simulator.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/cascade.py tests/test_cascade.py
git commit -m "feat: simulate overload-driven cascades"
```

### Task 2: Controlled Grid Stressing

**Files:**
- Create: `src/scenarios.py`
- Create: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: a pandapower network
- Produces: `stress_grid(net, load_scale=1.0, generation_scale=1.0, capacity_scale=1.0) -> pandapowerNet`
- Produces: `DEFAULT_STRESS_PROFILES`

- [ ] **Step 1: Write failing stress tests**

Add `test_stress_grid_scales_copy_without_modifying_original`, asserting active/reactive loads, generator active power, and line current ratings scale exactly while original tables remain equal. Add parametrized `test_stress_grid_rejects_non_positive_scale` and a real-power-flow test proving the stressed IEEE 14-bus copy remains solvable.

- [ ] **Step 2: Run stress tests to verify RED**

Run: `python3 -m pytest tests/test_scenarios.py -v`

Expected: collection failure because `src.scenarios` does not exist.

- [ ] **Step 3: Implement `stress_grid` and default profiles**

Validate all scales, deep-copy, scale only the spec-defined columns/elements, and define deterministic nominal, stressed, and severe profile dictionaries.

- [ ] **Step 4: Run stress tests to verify GREEN**

Run: `python3 -m pytest tests/test_scenarios.py -v`

Expected: all Task 2 tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/scenarios.py tests/test_scenarios.py
git commit -m "feat: add controlled grid stress profiles"
```

### Task 3: Batch Scenario Generation and CSV Persistence

**Files:**
- Modify: `src/scenarios.py`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: `stress_grid`, `simulate_cascade`, and Phase 1 `run_power_flow`
- Produces: `generate_scenarios(net, profiles=None, line_indices=None, overload_threshold=100.0, max_steps=20) -> tuple[pandas.DataFrame, pandas.DataFrame]`
- Produces: `save_scenario_results(summary, steps, output_dir) -> tuple[pathlib.Path, pathlib.Path]`

- [ ] **Step 1: Write failing batch and persistence tests**

Add tests asserting deterministic scenario IDs/count/order, required summary/detail columns, cascade histories flattened one row per step, correct converged load loss, unavailable non-converged final metrics via a cascade fake, rejection of non-converged pre-contingency profiles, both CSV files under a temporary output directory, and valid JSON round-trip for all list fields.

- [ ] **Step 2: Run Task 3 tests to verify RED**

Run: `python3 -m pytest tests/test_scenarios.py -v`

Expected: import or assertion failures because generation/persistence functions do not exist.

- [ ] **Step 3: Implement `generate_scenarios`**

Validate selected line labels, run every profile/line pair on independent copies, solve the stressed baseline, invoke the cascade engine, and construct summary/detail DataFrames with JSON list fields and unavailable failed-state values preserved.

- [ ] **Step 4: Implement `save_scenario_results`**

Create the output directory and write `cascade_scenario_summary.csv` and `cascade_steps.csv` with `index=False`, returning both paths.

- [ ] **Step 5: Run all Phase 1–2 tests to verify GREEN**

Run: `python3 -m pytest -v`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/scenarios.py tests/test_scenarios.py
git commit -m "feat: generate cascade scenario datasets"
```

### Task 4: Demo, Full Batch Script, Outputs, and README

**Files:**
- Create: `scripts/run_cascade_demo.py`
- Create: `scripts/generate_cascade_scenarios.py`
- Create at runtime: `outputs/cascade_scenario_summary.csv`
- Create at runtime: `outputs/cascade_steps.csv`
- Modify: `README.md`
- Modify: `tests/test_cascade.py`

**Interfaces:**
- Consumes: Phase 1 loader/simulator plus Phase 2 cascade/scenario APIs
- Produces: console cascade trace, 45-scenario default batch, two CSV datasets, and Phase 2 usage documentation

- [ ] **Step 1: Write the failing cascade-demo integration test**

Add `test_cascade_demo_prints_complete_trace`, running the script with the current interpreter and asserting exit 0 plus initial-outage, step, ended, failed-lines, load-lost, and final-status output markers.

- [ ] **Step 2: Run the demo test to verify RED**

Run: `python3 -m pytest tests/test_cascade.py::test_cascade_demo_prints_complete_trace -v`

Expected: FAIL because `scripts/run_cascade_demo.py` does not exist.

- [ ] **Step 3: Implement both scripts**

Use project-root import setup. The demo prints each history record and final summary. The generator runs all default profile/line pairs, saves both CSVs under `outputs/`, and prints scenario/step counts and paths.

- [ ] **Step 4: Run scripts and validate outputs**

Run: `python3 scripts/run_cascade_demo.py`

Run: `python3 scripts/generate_cascade_scenarios.py`

Run: `python3 -c "import pandas as pd; s=pd.read_csv('outputs/cascade_scenario_summary.csv'); d=pd.read_csv('outputs/cascade_steps.csv'); assert len(s)==45 and len(d)>=45; print(len(s), len(d), sorted(s.final_status.unique()))"`

Expected: a readable trace, 45 scenarios, at least 45 detailed steps, and more than one outcome class including a cascading case.

- [ ] **Step 5: Update README for Phase 2**

Document cascade semantics, stress factors, both commands, both datasets, test command, and explicit exclusions of later phases.

- [ ] **Step 6: Run final acceptance verification**

Run: `python3 scripts/run_cascade_demo.py`

Run: `python3 scripts/generate_cascade_scenarios.py`

Run: `python3 -m pytest -v`

Expected: both scripts exit 0, both CSVs validate, and the entire Phase 1–2 suite passes.

- [ ] **Step 7: Review scope and repository diff**

Run: `git diff --check && git status --short && git diff --stat HEAD`

Expected: only Phase 2 source, scripts, tests, docs, and generated outputs are present.

- [ ] **Step 8: Commit Task 4**

```bash
git add README.md scripts/run_cascade_demo.py scripts/generate_cascade_scenarios.py tests/test_cascade.py outputs/cascade_scenario_summary.csv outputs/cascade_steps.csv
git commit -m "docs: add Phase 2 cascade demos and datasets"
```
