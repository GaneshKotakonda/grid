# GridResilience

**Physics-Informed Graph Neural Network Forecasting, Autonomous Reinforcement Learning Mitigation, and Safety-Constrained Service Recovery for IEEE-14 Power Networks.**

GridResilience is an end-to-end cyber-physical research and operational platform designed to prevent, mitigate, and recover from cascading failures in electric power grids.

---

## Architecture Overview (Phases 1–7)

The repository implements the full end-to-end pipeline through Phase 7:

- **Phase 1: AC Power Flow & Network Modeling**: Pandapower IEEE 14-bus modeling, AC load flow, single-line contingency analysis, and metric extraction.
- **Phase 2: Cascading Failure Physics**: Deterministic overload-driven propagation, multi-wave line trip mechanics, synthetic operating stress calibration.
- **Phase 3: Graph Representation & Dataset Generation**: Conversion of power-flow states to 14-bus / 30-edge graph tensors with strict scenario-level split isolation.
- **Phase 4 & 4.5: Downstream Failure Forecasting**: Topology-aware Graph Convolutional Network (`predictive_v2` GCN) trained on future wave targets ($t+1$) without threshold data leakage.
- **Phase 5 & 5.5: Predictive RL Mitigation**: PPO policy trained in parallel Gymnasium environments combining physical AC states with downstream GCN failure probabilities to execute targeted load shedding and generator redispatch.
- **Phase 6: Safety-Constrained Grid Recovery**: Post-cascade restoration environment enforcing AC feasibility, bus voltage bounds ($[0.90, 1.10]\text{ pu}$), and thermal limits ($<100\%$) to sequentially reclose tripped lines and restore customer load.
- **Phase 7: FastAPI Backend & React Dashboard**: Real-time REST API and interactive research control dashboard featuring dynamic IEEE-14 topology visualization, GCN prediction ranking, mitigation tracing, cascade timeline, and experimental benchmarks.

---

## Main Experimental Results

### Phase 5.5 Reinforcement Learning Findings (300 Held-Out Scenarios)
Evaluated across identical held-out test scenarios against Do-Nothing and Rule-Based baselines:

| Controller | Load Served (%) | Load Shed (MW) | Total Blackout Rate (%) | Cascade Reduction |
| :--- | :---: | :---: | :---: | :---: |
| **Do-Nothing** | 27.00% | 0.00 MW | 73.00% | Baseline |
| **Rule-Controller** | 26.34% | 8.35 MW | 73.00% | +0.86% |
| **PPO (No GCN)** | 26.48% | 9.54 MW | 71.33% | +2.74% |
| **PPO (Predictive GCN)** | **30.65%** | **2.91 MW** | **68.33%** | **+3.53%** |

- **+4.17 percentage points** higher customer load served ($30.65\%$ vs $26.48\%$).
- **69.5% reduction** in customer load shedding ($2.91\text{ MW}$ vs $9.54\text{ MW}$).
- **3.0 percentage-point reduction** in total blackout rate ($68.33\%$ vs $71.33\%$).

### Phase 6 Post-Cascade Recovery Audit (100 Scenarios)
- **100% Invariant Conservation**: Every attempted unsafe action is reverted; recovery actions never reduce served load below post-cascade levels.
- **Audited Blackout Rate**: No-Recovery remaining blackout rate is **74.0%**, and Greedy-Recovery remaining blackout rate is **74.0%** (+0.28 MW average load restored, 0 survivors corrupted).

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Python Environment
Install core dependencies:
```bash
pip install -r requirements.txt
```

### 2. Frontend Setup
From the repository root:
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## Running the Platform

### Option A: Unified Production Mode (FastAPI + Embedded Dashboard)
Serves the built React dashboard and REST API simultaneously on port 8000:
```bash
py -3.11 -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### Option B: Live Development Mode (Hot Reloading)
- **Terminal 1 (Backend)**:
  ```bash
  py -3.11 -m uvicorn src.api:app --reload --port 8000
  ```
- **Terminal 2 (Frontend)**:
  ```bash
  cd frontend
  npm run dev
  ```
  Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## API Endpoints

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/health` | `GET` | Service readiness and loaded model checkpoints (`best_gcn.pt`, `ppo_predictive.zip`). |
| `/grid` | `GET` | Complete IEEE-14 topology: 14 buses, 15 transmission lines, 5 transformers, and 2D layout coordinates. |
| `/simulate` | `POST` | Trigger incident simulation with parameters: `initial_outage`, `load_scale`, `capacity_scale`, `seed`. |
| `/results/{run_id}` | `GET` | Retrieve complete incident trace, GCN failure probabilities, mitigation steps, and recovery history. |
| `/benchmarks` | `GET` | Return real empirical comparison tables from saved CSV artifacts. |

---

## Testing

Run the full automated test suite (97 tests covering all 7 phases):
```bash
py -3.11 -m pytest
```

---

## Project Directory Structure

```text
grid/
├── src/
│   ├── __init__.py
│   ├── api.py                  # FastAPI REST service & static mount
│   ├── pipeline.py             # End-to-end incident execution pipeline
│   ├── grid_loader.py          # IEEE 14-bus test system loader
│   ├── simulator.py            # AC power flow solver
│   ├── metrics.py              # Electrical & operational metric extraction
│   ├── cascade.py              # Deterministic overload cascade engine
│   ├── scenarios.py            # Operating point stress & scenario generation
│   ├── graph.py                # Graph tensor construction
│   ├── gnn_dataset.py          # Supervised dataset pipeline & validation
│   ├── gnn_training.py         # MLP, GCN, and GAT PyTorch architectures
│   ├── rl_env.py               # Gymnasium mitigation environment
│   ├── rl_controllers.py       # Heuristic & PPO policy controllers
│   ├── rl_training.py          # Multi-process PPO training pipeline
│   └── recovery.py             # Safety-constrained AC recovery environment
├── frontend/
│   ├── package.json            # React + Vite configuration
│   ├── vite.config.js          # Dev proxy routing to backend:8000
│   ├── dist/                   # Production build distribution
│   └── src/
│       ├── App.jsx             # Master dashboard layout & state
│       ├── index.css           # Slate cyber-physical design tokens
│       └── components/
│           ├── Navbar.jsx              # Status & quick incident presets
│           ├── ControlBar.jsx          # Interactive outage & stress runner
│           ├── TopologyGraph.jsx       # Interactive IEEE-14 SVG network
│           ├── MetricsOverview.jsx     # 6 real-time KPI cards
│           ├── FailurePredictionPanel.jsx # 15-line GCN risk rankings
│           ├── MitigationPanel.jsx     # PPO load shed & dispatch trace
│           ├── CascadeTimeline.jsx     # Horizontal incident stepper
│           ├── RecoveryPanel.jsx       # Load restored & reclosure log
│           └── ComparisonPanel.jsx     # Phase 5.5 & 6 benchmark tables
├── scripts/
│   ├── run_baseline.py
│   ├── run_cascade_demo.py
│   ├── run_end_to_end_demo.py
│   ├── generate_cascade_scenarios.py
│   ├── generate_gnn_dataset.py
│   ├── generate_predictive_v2.py
│   ├── train_gnn.py
│   ├── train_rl.py
│   └── run_recovery_eval.py
├── tests/
│   ├── test_grid_loader.py
│   ├── test_simulator.py
│   ├── test_cascade.py
│   ├── test_scenarios.py
│   ├── test_graph.py
│   ├── test_gnn_dataset.py
│   ├── test_gnn_training.py
│   ├── test_rl_env.py
│   ├── test_recovery.py
│   └── test_api.py
├── outputs/                    # Validated experimental models & CSV reports
├── requirements.txt
├── .gitignore
└── README.md
```
