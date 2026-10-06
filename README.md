# GridResilience

GridResilience is an incremental research project for predictive cascading-failure mitigation and power-grid recovery. The repository currently implements four phases:

- **Phase 1:** IEEE 14-bus loading, AC power flow, single-line outage simulation, metrics, and before/after comparison.
- **Phase 2:** automatic overload-driven cascade simulation, controlled operating-point stress, and deterministic batch scenario generation.
- **Phase 3:** seeded randomized cascades and validated supervised graph-sample generation.
- **Phase 4:** MLP, GCN, and GAT next-line failure prediction and evaluation.

It does not yet include reinforcement learning, FastAPI, a frontend, recovery actions, load shedding controls, or agentic control.

## Requirements

- Python 3.11 or newer
- pandapower 3.x
- pandas 2.x
- NumPy
- pytest
- PyTorch 2.x

## Installation

From the project root:

```bash
pip install -r requirements.txt
```

## Phase 1: baseline and single outage

```bash
python scripts/run_baseline.py
```

The script loads pandapower's IEEE 14-bus network, solves the baseline, deterministically disconnects the lowest-index in-service line, solves the contingency, prints the comparison, and writes:

```text
outputs/baseline_results.csv
```

## Phase 2: cascading failures

Run the readable multi-step cascade demonstration:

```bash
python scripts/run_cascade_demo.py
```

The cascade engine:

1. deep-copies the supplied network;
2. applies the initial outage as step 0;
3. runs AC power flow;
4. detects in-service lines loaded strictly above the threshold;
5. applies those overload trips as the next wave;
6. repeats until no overload remains, power flow fails, or the propagation limit is reached.

Every step records cumulative and new failures, loading, overloaded lines, minimum voltage, served load, generation, convergence, and solver error information. Post-initial failures are never random.

`max_steps` counts automatic overload-trip waves after the initiating event, so a result can contain at most `max_steps + 1` history records including step 0.

## Controlled stress profiles

`stress_grid()` returns a deep copy and can independently scale:

- active and reactive load;
- generator active-power setpoints;
- line current ratings used by overload detection.

All default profiles and generated records are explicitly marked as synthetic stress scenarios. The built-in IEEE 14-bus case has deliberately high thermal ratings, so the default stressed profiles use calibrated capacity factors of `0.02` and `0.012` to create controlled cascades without changing line impedances or randomly forcing failures. Every scenario stores its exact `capacity_scale`.

## Generate the scenario dataset

```bash
python scripts/generate_cascade_scenarios.py
```

The generator runs three stress profiles against each of the 15 initially in-service lines, producing 45 scenarios and two files:

```text
outputs/cascade_scenario_summary.csv
outputs/cascade_steps.csv
```

The summary contains one row per scenario with its synthetic-stress marker, stress parameters (including capacity scale), initial outage, cascade length, ordered trip-wave sequence, total failed lines, initial and final served load, load lost, load-served percentage, convergence, terminal status, and final maximum loading. The detailed file contains one row per cascade step. List-valued columns are serialized as JSON.

Unavailable values after a non-converged solve remain empty rather than being reported as zero.

## Phase 3: graph-learning dataset

Generate a deterministic graph dataset with configurable randomized operating conditions:

```bash
python scripts/generate_gnn_dataset.py --scenarios 5000 --seed 42
```

The generator samples synthetic load, generation, capacity, and initial-outage conditions. A dedicated seed is recorded for every scenario. All post-initial failures still come exclusively from the Phase 2 overload rule.

Each solved state becomes a graph with 14 bus nodes and 30 directed message-passing edges representing the 15 physical lines. Node features contain voltage magnitude/angle, served active/reactive load, active/reactive generation, bus status, and supplied status. Edge features contain endpoints, directional active/reactive flow, loading, resistance, reactance, line status, current rating, length, and maximum loading. Raw electrical values are not normalized.

Unavailable solved measurements on unsupplied buses and failed lines are stored as zero alongside explicit supplied/in-service flags. This produces finite tensors without making a failed component appear energized.

Targets are 15-element multi-label vectors. State `t` predicts the physical line wave actually tripped at `t+1`; the initiating outage is never a target. Stable terminal states produce all-zero negative labels. States capped with unapplied overloads are not mislabeled as stable.

The deterministic 70/15/15 split is performed by scenario, so every step from one cascade remains in exactly one of train, validation, or test. Before writing, validation checks tensor shapes, finite values, binary targets, failed-line status, history/label agreement, sample alignment, and split leakage.

Outputs are NumPy arrays ready to convert to PyTorch/PyTorch Geometric tensors without adding those training dependencies in Phase 3:

```text
outputs/gnn_train.npz
outputs/gnn_validation.npz
outputs/gnn_test.npz
outputs/gnn_samples_metadata.csv
outputs/gnn_dataset_summary.csv
outputs/gnn_dataset_manifest.json
```

The summary reports positive/negative imbalance, split sizes, per-line next-failure frequency, final-status distribution, and generation time. Phase 3 measures imbalance but does not resample or train a model.

## Phase 4: next-line prediction

Train the flattened-feature MLP baseline, topology-aware GCN, and topology-aware GAT using the existing saved split arrays. The dataset is not regenerated:

```bash
python scripts/train_gnn.py --smoke
python scripts/train_gnn.py --epochs 80 --patience 12 --seed 42
```

Normalization statistics and per-line positive weights are fit on the training split only. Checkpoints include the model, normalization, configuration, and validation-selected threshold. Early stopping uses validation BCE loss; the decision threshold maximizes pooled validation micro-F1 and is frozen before test evaluation. Reports include per-line scores and held-out capacity-stress bands.

Outputs include `outputs/models/best_{mlp,gcn,gat}.pt`, `gnn_training_history.csv`, `gnn_test_metrics.json`, `gnn_per_line_metrics.csv`, `gnn_model_comparison.csv`, `gnn_stress_robustness.csv`, `gnn_decision_thresholds.json`, and `gnn_training_summary.json`.

## Metric semantics

- Active line power is signed pandapower `p_from_mw`, flowing from the configured `from_bus` toward `to_bus` when positive.
- Total generation includes solved generator output (`res_gen.p_mw`) and external-grid contribution (`res_ext_grid.p_mw`).
- Served load counts solved loads only when the load and its bus are in service and the bus has a finite solved voltage.
- An overloaded line is an in-service line with loading strictly greater than the configured threshold, which defaults to 100 percent.
- A failed power flow returns explicit `converged=False` metrics instead of fabricated numeric results.
- Terminal statuses are `STABLE`, `PARTIAL_BLACKOUT`, `TOTAL_BLACKOUT`, `NON_CONVERGED`, and `MAX_STEPS_REACHED`. A converged result is stable only when no overload remains and at least 99 percent of initial load is served. Near-zero served load is always a total blackout. Non-convergence and step-limit termination take precedence over load-based classification.

## Tests

```bash
pytest
```

The suite covers all Phase 1 behavior plus cascade sequencing, topology isolation, stress/scenario persistence, graph conversion, next-wave targets, deterministic generation, scenario-level split isolation, validation, and serialization.

## Project structure

```text
gridresilience/
├── src/
│   ├── __init__.py
│   ├── grid_loader.py
│   ├── simulator.py
│   ├── metrics.py
│   ├── cascade.py
│   ├── scenarios.py
│   ├── graph.py
│   └── gnn_dataset.py
├── scripts/
│   ├── run_baseline.py
│   ├── run_cascade_demo.py
│   ├── generate_cascade_scenarios.py
│   └── generate_gnn_dataset.py
├── tests/
│   ├── test_grid_loader.py
│   ├── test_simulator.py
│   ├── test_cascade.py
│   ├── test_scenarios.py
│   ├── test_graph.py
│   └── test_gnn_dataset.py
├── outputs/
│   ├── baseline_results.csv
│   ├── cascade_scenario_summary.csv
│   ├── cascade_steps.csv
│   ├── gnn_train.npz
│   ├── gnn_validation.npz
│   ├── gnn_test.npz
│   ├── gnn_samples_metadata.csv
│   ├── gnn_dataset_summary.csv
│   └── gnn_dataset_manifest.json
├── requirements.txt
└── README.md
```
