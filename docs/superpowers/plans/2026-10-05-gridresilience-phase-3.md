# GridResilience Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, validated pipeline that converts randomized IEEE 14-bus cascade states into leakage-free supervised graph datasets for later PyTorch Geometric training.

**Architecture:** The cascade engine optionally captures solved network states without changing its default API output. `graph.py` converts one solved network into raw bidirectional graph tensors and targets, while `gnn_dataset.py` orchestrates seeded synthetic scenarios, next-wave sample extraction, scenario-level splits, quality validation, summaries, and compressed NumPy serialization.

**Tech Stack:** Python 3.11+, pandapower 3.x, pandas 2.x, NumPy 1.26+, pytest 9.x

**Spec:** `docs/superpowers/specs/2026-10-05-gridresilience-phase-3-design.md`

## Global Constraints

- Implement only Phase 3 dataset generation; do not train a GNN or add RL, recovery, API, frontend, or agentic behavior.
- Preserve the Phase 2 overload-only electrical failure rules and deep-copy guarantees.
- Store raw finite values without feature normalization.
- Represent 15 physical IEEE-14 lines as 30 directed message-passing edges and a 15-slot physical-line target.
- Never use an initial outage as a prediction target.
- Assign splits by scenario, never by sample.
- Keep pytest scenario counts small; run 100 then 2,000 scenarios only as development artifacts.
- Add no PyTorch dependency in this phase; write compressed NumPy tensors that convert directly to tensors later.
- Existing uncommitted Phase 2 hardening changes remain user-owned; commits stage only files named by each Phase 3 task.

## Review Focus

- A `MAX_STEPS_REACHED` terminal state with pending overloads must not become an all-zero negative; Task 3 adds `test_capped_pending_state_is_not_emitted_as_negative`.
- A trip wave that causes non-convergence must remain the target of its preceding solved state; Task 3 adds `test_pre_failure_state_keeps_nonconvergent_trip_target`.
- Failed lines with NaN pandapower result rows must serialize as finite zero flows with both directed status flags off; Task 2 adds `test_failed_line_remains_finite_and_out_of_service`.
- Line labels must map through sorted physical labels rather than assuming labels are contiguous; Task 2 adds `test_target_uses_explicit_sorted_line_mapping`.
- Small scenario counts must still keep every scenario in exactly one split and avoid sample leakage; Task 3 adds `test_scenario_split_is_deterministic_and_isolated`.

---

### Task 1: Opt-In Cascade State Capture

**Files:**
- Modify: `src/cascade.py`
- Modify: `tests/test_cascade.py`

**Interfaces:**
- Extends: `simulate_cascade(..., capture_network_states: bool = False) -> tuple[pandapowerNet, dict[str, Any]]`
- Produces when enabled: `history[*]["network_state"]: pandapowerNet` on converged records only

- [ ] **Step 1: Write failing capture tests**

Add `test_state_capture_is_opt_in_and_preserves_each_solved_topology`. Assert the default history retains the exact existing keys, capture mode adds a solved deep-copied `network_state`, the captured step reflects the failed line status, and mutating the returned final network does not alter the captured state.

- [ ] **Step 2: Run the focused test to verify RED**

Run: `python3 -m pytest tests/test_cascade.py::test_state_capture_is_opt_in_and_preserves_each_solved_topology -v`

Expected: FAIL because `capture_network_states` is not accepted.

- [ ] **Step 3: Implement optional solved-state capture**

Add the boolean argument. After each successful solve, attach `deepcopy(cascade_net)` only when capture is enabled. Do not add a key for failed solves or default calls.

- [ ] **Step 4: Run cascade and existing tests to verify GREEN**

Run: `python3 -m pytest tests/test_cascade.py tests/test_simulator.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1 only**

```bash
git add src/cascade.py tests/test_cascade.py
git commit -m "feat: capture solved cascade states"
```

### Task 2: Graph Conversion, Targets, and Sample Validation

**Files:**
- Create: `src/graph.py`
- Create: `tests/test_graph.py`

**Interfaces:**
- Produces: `GraphSample` dataclass containing sample ID, node features, edge index, edge features, edge-line mapping, physical line labels, and target
- Produces: `network_to_graph(net: pandapowerNet, sample_id: str, next_failed_lines: Iterable[int]) -> GraphSample`
- Produces: `make_target(line_indices: np.ndarray, next_failed_lines: Iterable[int]) -> np.ndarray`
- Produces: `validate_graph_sample(sample: GraphSample, metadata: Mapping[str, Any] | None = None) -> None`
- Produces constants: `NODE_FEATURE_NAMES`, `EDGE_FEATURE_NAMES`

- [ ] **Step 1: Write failing graph schema tests**

Add tests that solve IEEE 14-bus and assert 14 nodes with the eight specified node columns, 30 directed edges with eleven edge columns, bidirectional endpoint/flow mapping, 15 physical line labels, and finite raw values.

- [ ] **Step 2: Write failing target and failed-line tests**

Add `test_target_uses_explicit_sorted_line_mapping`, `test_stable_target_is_all_zero`, and `test_failed_line_remains_finite_and_out_of_service`. Use a relabeled line index fixture for the mapping test and a real solved outage for line-state representation.

- [ ] **Step 3: Write failing validation test**

Add `test_graph_validation_rejects_nan_features` by copying a valid sample, injecting NaN into a node feature, and asserting a contextual `ValueError`.

- [ ] **Step 4: Run graph tests to verify RED**

Run: `python3 -m pytest tests/test_graph.py -v`

Expected: collection failure because `src.graph` does not exist.

- [ ] **Step 5: Implement graph conversion and validation**

Aggregate solved load/generation by sorted bus label, include external-grid p/q, create forward and reverse line rows using `p_from`/`q_from` and `p_to`/`q_to`, replace only unavailable solved measurements with zero, preserve line status and capacity fields, construct targets through the explicit line-label lookup, and validate shapes/finiteness/binary labels/status consistency.

- [ ] **Step 6: Run graph and Phase 1-2 tests to verify GREEN**

Run: `python3 -m pytest tests/test_graph.py tests/test_grid_loader.py tests/test_simulator.py tests/test_cascade.py -q`

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2 only**

```bash
git add src/graph.py tests/test_graph.py
git commit -m "feat: convert cascade states to graph samples"
```

### Task 3: Seeded Scenario Generation and Leakage-Free Sample Extraction

**Files:**
- Create: `src/gnn_dataset.py`
- Create: `tests/test_gnn_dataset.py`

**Interfaces:**
- Produces: `DatasetBuild` dataclass with `samples`, `metadata`, `scenarios`, `line_indices`, `config`, and `generation_seconds`
- Produces: `assign_scenario_splits(scenario_ids: Sequence[str], seed: int) -> dict[str, str]`
- Produces: `extract_cascade_samples(cascade: Mapping[str, Any], scenario_metadata: Mapping[str, Any], split: str) -> tuple[list[GraphSample], list[dict[str, Any]]]`
- Produces: `generate_gnn_dataset(net: pandapowerNet, scenario_count: int, seed: int, ..., max_initial_outages: int = 2, multiple_outage_probability: float = 0.2) -> DatasetBuild`
- Produces: `validate_dataset(build: DatasetBuild) -> None`

- [ ] **Step 1: Write failing deterministic generation tests**

Add `test_random_generation_is_deterministic` using six real scenarios and a fixed seed. Assert identical non-timing scenario parameters, metadata, targets, and tensors across two runs, plus at least one emitted sample.

- [ ] **Step 2: Write failing next-step label tests**

Add a tiny controlled history fixture to assert the step-0 target is the next automatic trip rather than the initial outage, a stable terminal creates an all-zero target, `test_capped_pending_state_is_not_emitted_as_negative`, and `test_pre_failure_state_keeps_nonconvergent_trip_target`.

- [ ] **Step 3: Write failing split/isolation test**

Add `test_scenario_split_is_deterministic_and_isolated` for 20 scenario IDs. Assert repeatability, approximate 70/15/15 scenario counts, and at most one unique split per scenario in emitted metadata.

- [ ] **Step 4: Run dataset-generation tests to verify RED**

Run: `python3 -m pytest tests/test_gnn_dataset.py -v`

Expected: collection failure because `src.gnn_dataset` does not exist.

- [ ] **Step 5: Implement random configuration and split assignment**

Validate positive ordered ranges, positive scenario count, probability in `[0, 1]`, and outage bounds. Derive and record one local seed per scenario, sample scales and unique initial outages from that local generator, and deterministically split scenario IDs.

- [ ] **Step 6: Implement cascade-to-sample extraction**

Call state-capturing cascade simulation. Emit a positive graph for each actual next history wave, emit one zero target for converged terminals with no overload, omit failed states and capped pending terminals, and attach all required metadata with JSON list fields.

- [ ] **Step 7: Implement dataset validation**

Validate every graph, target-to-metadata mapping, sample ID/order alignment, failed-line status mapping, and scenario split isolation. Preserve non-converged scenario records even when they emit no final graph.

- [ ] **Step 8: Run dataset and complete existing tests to verify GREEN**

Run: `python3 -m pytest tests/test_gnn_dataset.py tests/test_graph.py tests/test_cascade.py tests/test_scenarios.py -q`

Expected: all selected tests pass quickly.

- [ ] **Step 9: Commit Task 3 only**

```bash
git add src/gnn_dataset.py tests/test_gnn_dataset.py
git commit -m "feat: generate supervised cascade graph samples"
```

### Task 4: Summary and Dataset Serialization

**Files:**
- Modify: `src/gnn_dataset.py`
- Modify: `tests/test_gnn_dataset.py`

**Interfaces:**
- Produces: `build_dataset_summary(build: DatasetBuild) -> pd.DataFrame`
- Produces: `save_gnn_dataset(build: DatasetBuild, output_dir: str | Path) -> dict[str, Path]`

- [ ] **Step 1: Write failing summary test**

Assert one summary row includes total scenarios/samples, positive/negative counts and percentages, train/validation/test sample counts, `line_<label>_next_failure_count` and frequency fields for all lines, final-status counts, and generation seconds.

- [ ] **Step 2: Write failing serialization test**

Save a tiny real build under `tmp_path`. Assert all three `.npz` files, metadata CSV, summary CSV, and manifest exist; load each archive with `allow_pickle=False`; assert tensor/sample dimensions and sample IDs match the corresponding metadata split; assert manifest feature names match module constants.

- [ ] **Step 3: Run serialization tests to verify RED**

Run: `python3 -m pytest tests/test_gnn_dataset.py -k 'summary or serialization' -v`

Expected: FAIL because summary/save functions do not exist.

- [ ] **Step 4: Implement summary construction**

Count a positive sample when any target bit is one, compute raw imbalance without resampling, count target occurrences/frequencies per physical line, and count scenario final statuses from the scenario table.

- [ ] **Step 5: Implement split archives, metadata, and manifest**

Stack fixed-shape sample arrays per split, preserve zero-length leading dimensions, write compressed archives, write metadata and summary CSVs, and write JSON schema/configuration metadata without NumPy-only scalar types.

- [ ] **Step 6: Run Task 4 and full tests to verify GREEN**

Run: `python3 -m pytest -q`

Expected: all Phase 1-3 tests pass.

- [ ] **Step 7: Commit Task 4 only**

```bash
git add src/gnn_dataset.py tests/test_gnn_dataset.py
git commit -m "feat: serialize validated graph datasets"
```

### Task 5: CLI, Documentation, and Development Datasets

**Files:**
- Create: `scripts/generate_gnn_dataset.py`
- Modify: `README.md`
- Create at runtime: `outputs/gnn_train.npz`
- Create at runtime: `outputs/gnn_validation.npz`
- Create at runtime: `outputs/gnn_test.npz`
- Create at runtime: `outputs/gnn_samples_metadata.csv`
- Create at runtime: `outputs/gnn_dataset_summary.csv`
- Create at runtime: `outputs/gnn_dataset_manifest.json`
- Modify: `tests/test_gnn_dataset.py`

**Interfaces:**
- CLI: `python scripts/generate_gnn_dataset.py --scenarios N --seed S [range and cascade options]`

- [ ] **Step 1: Write failing CLI integration test**

Run the script with four scenarios, seed 42, a temporary output directory, and bounded max steps. Assert exit zero, output paths/count/timing markers, and the six expected files. Do not generate a large dataset in pytest.

- [ ] **Step 2: Run the CLI test to verify RED**

Run: `python3 -m pytest tests/test_gnn_dataset.py::test_cli_generates_small_dataset -v`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement the CLI**

Use argparse for scenario count, seed, output directory, min/max scale values, overload threshold, max steps, max initial outages, and multiple-outage probability. Print scenario/sample/class/split counts, imbalance, elapsed seconds, and saved paths.

- [ ] **Step 4: Document Phase 3**

Add graph schema, raw-value and missing-value semantics, scenario split rule, command examples, output files, validation behavior, and explicit no-training scope to `README.md`.

- [ ] **Step 5: Run and validate the 100-scenario development dataset**

Run: `python3 scripts/generate_gnn_dataset.py --scenarios 100 --seed 42 --output-dir outputs/gnn_small`

Expected: exit zero, finite validated tensors, 100 scenario records, nonzero samples, both positive and negative examples, and no split leakage.

- [ ] **Step 6: Run and validate the 2,000-scenario dataset**

Run: `python3 scripts/generate_gnn_dataset.py --scenarios 2000 --seed 42 --output-dir outputs`

Expected: exit zero with reported elapsed time, 2,000 scenario records, six final artifacts, finite tensors, and no split leakage.

- [ ] **Step 7: Run final acceptance verification**

Run: `python3 -m pytest -q`

Run: `python3 -c "import pandas as pd; s=pd.read_csv('outputs/gnn_dataset_summary.csv').iloc[0]; assert s.total_scenarios == 2000; assert s.total_graph_samples > 0; print(s.to_dict())"`

Run: `git diff --check && git status --short`

Expected: full test success, valid 2,000-scenario summary, and only intended Phase 2 hardening plus Phase 3 changes/artifacts in the working tree.

- [ ] **Step 8: Commit code/docs tests only**

```bash
git add scripts/generate_gnn_dataset.py README.md tests/test_gnn_dataset.py
git commit -m "docs: add Phase 3 dataset workflow"
```

Generated binary datasets remain workspace artifacts unless the repository's existing output policy explicitly tracks them.
