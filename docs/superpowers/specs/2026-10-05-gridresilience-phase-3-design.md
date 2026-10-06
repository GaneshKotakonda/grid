# GridResilience Phase 3 Design

## Purpose and Scope

Phase 3 converts randomized IEEE 14-bus cascade simulations into reproducible supervised graph samples. Each sample describes a solved post-contingency network state and predicts which physical transmission lines trip in the next recorded cascade wave. Stable terminal states contribute all-zero negative targets.

This phase does not train a graph neural network and does not add reinforcement learning, recovery actions, FastAPI, a frontend, or agentic control. Phase 1 and Phase 2 behavior remains intact, including the overload-only cascade rule.

## Architecture

Phase 3 adds two focused modules:

- `src/graph.py` owns graph feature extraction, next-wave target creation, graph data structures, and per-sample validation.
- `src/gnn_dataset.py` owns seeded randomized scenario generation, sample extraction from cascade histories, scenario-level splitting, dataset validation, summary construction, and serialization.

`scripts/generate_gnn_dataset.py` is a thin command-line entry point. It loads IEEE 14-bus, invokes the dataset generator, validates all samples, writes the output artifacts, and reports counts, imbalance, and elapsed generation time.

The existing cascade engine gains an opt-in `capture_network_states=False` argument. When enabled, each converged history record includes a deep-copied solved network under `network_state`. The default remains false, so existing histories and Phase 2 memory use are unchanged. The capture option does not alter trip decisions, convergence handling, or termination classification.

## Graph Schema

Bus and line indices are sorted once and retained as explicit mappings. Raw electrical values are stored without normalization.

### Nodes

One node represents one bus. `node_features` has shape `[14, 8]` for IEEE 14-bus, with columns:

1. voltage magnitude (`vm_pu`)
2. voltage angle (`va_degree`)
3. served active load (`p_mw`)
4. served reactive load (`q_mvar`)
5. active generation including external-grid injection (`p_mw`)
6. reactive generation including external-grid injection (`q_mvar`)
7. bus in-service flag
8. supplied/solved flag

Unenergized buses have unavailable solved values represented as zero and are disambiguated by the supplied flag. This prevents NaN/Inf tensors without presenting imputed values as energized measurements.

### Edges

One physical transmission line creates two directed message-passing edges, so `edge_index` has shape `[2, 30]` and `edge_features` has shape `[30, 11]`. `edge_line_indices` maps each directed edge back to one of the 15 physical line labels and therefore to the corresponding target slot.

Edge columns are:

1. source bus
2. destination bus
3. directional active power flow (`p_mw`)
4. directional reactive power flow (`q_mvar`)
5. line loading percentage
6. resistance (`r_ohm_per_km`)
7. reactance (`x_ohm_per_km`)
8. in-service flag
9. thermal current rating (`max_i_ka`)
10. line length (`length_km`)
11. allowed loading percentage (`max_loading_percent`)

For reverse edges, endpoints are swapped and pandapower's solved `p_to_mw`/`q_to_mvar` values are used. Out-of-service lines remain in the graph with zero unavailable flows/loading and an in-service value of zero, preserving topology and failure state.

### Targets

`target` is a 15-element binary vector ordered by sorted physical line index. A one means that line is applied as the next actual cascade trip wave.

- Step 0 is the solved state after the initial outage, so the initial outage is never a label.
- If history step `t+1` exists, its `newly_failed_lines` is the target for state `t`.
- A converged terminal state with no pending overload is included as an all-zero negative example.
- A non-converged state has no valid graph and is not emitted, but its preceding converged state remains a positive sample when the trip wave that caused failure is recorded.
- A terminal `MAX_STEPS_REACHED` state with unapplied overloads is omitted because it has neither an observed next wave nor a valid negative label.

## Random Scenario Generation

`generate_random_scenarios` accepts a scenario count, deterministic seed, scale ranges, overload threshold, cascade step cap, maximum initial-outage count, and multiple-outage probability.

Default synthetic ranges are:

- load scale: 0.8 to 1.5
- generation scale: 0.9 to 1.1
- capacity scale: 0.01 to 0.05
- initial outages: one line, with a 20 percent probability of selecting two unique lines when the maximum is at least two

The top-level seed deterministically produces a separate recorded seed per scenario. Each scenario-local generator samples its scales and initial in-service line set. No post-initial random failure is allowed; all later failures continue to come only from the Phase 2 overload rule.

Each graph sample records:

- `sample_id`
- `scenario_id`
- `cascade_step`
- `random_seed`
- `load_scale`
- `generation_scale`
- `capacity_scale`
- JSON `initial_outages`
- JSON `current_failed_lines`
- JSON `next_failed_lines`
- `final_status`
- `is_synthetic_stress`
- `split`

## Scenario-Level Split

Scenario IDs are deterministically shuffled using the requested seed and assigned approximately 70 percent train, 15 percent validation, and 15 percent test. All samples from a scenario inherit its single split. Scenarios with no valid graph sample still participate in the scenario assignment and final-status accounting. Dataset validation rejects any scenario found in more than one split.

## Output Format

The output directory contains:

- `gnn_train.npz`
- `gnn_validation.npz`
- `gnn_test.npz`
- `gnn_samples_metadata.csv`
- `gnn_dataset_summary.csv`
- `gnn_dataset_manifest.json`

Each split archive contains stacked `node_features`, `edge_index`, `edge_features`, `edge_line_indices`, `targets`, `line_indices`, and `sample_ids`. These arrays can be converted directly to PyTorch tensors and then to PyTorch Geometric `Data` objects without changing the raw feature values. The manifest records feature names, dimensions, seed, scenario ranges, and split policy.

The one-row summary contains total scenarios, total graph samples, positive and negative sample counts and percentages, per-split sample counts, per-line next-failure counts/frequencies, final-status counts, and elapsed generation time.

## Quality Validation

Before serialization, validation checks:

- finite node and edge values with no NaN or Inf;
- exact bus, physical-line, and directed-edge dimensions;
- binary target length and values;
- two directed edges per physical line;
- every currently failed line has zero in-service status on both directed edges;
- target positions exactly match metadata `next_failed_lines`;
- sample IDs align with metadata;
- every scenario belongs to only one split.

Validation raises `ValueError` with the sample/scenario context rather than writing a partially valid dataset. Class imbalance is measured and reported but not modified.

## Command-Line Interface

The primary command is:

```bash
python scripts/generate_gnn_dataset.py --scenarios 5000 --seed 42
```

Additional options configure output directory, scale bounds, overload threshold, maximum cascade steps, maximum initial outages, and multiple-outage probability. Pytest uses only tiny deterministic scenario counts.

## Testing and Verification

Focused tests cover graph conversion, every required node/edge feature group, next-step and stable labels, seeded determinism, scenario-level split isolation, invalid feature rejection, failed-line status representation, and NPZ/CSV/manifest round-tripping.

End-to-end verification first generates 100 scenarios and validates every artifact. After that succeeds, a larger 2,000-scenario dataset is generated and timed. The complete Phase 1-3 pytest suite must remain fast and pass before completion.

## Acceptance Criteria

Phase 3 is complete when deterministic randomized cascades produce validated finite graph tensors, next-wave multi-label targets and stable negatives, leakage-free scenario splits, metadata and quality summaries, and reproducible serialized artifacts suitable for later PyTorch Geometric training. No model training or Phase 4 behavior is included.
