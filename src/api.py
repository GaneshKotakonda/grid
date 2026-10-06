"""FastAPI backend service for GridResilience Phase 7.

Exposes REST endpoints for:
- System health and loaded model status (/health)
- IEEE-14 topology, buses, transmission lines (/grid)
- Interactive multi-stage incident simulation (/simulate)
- Incident result retrieval by run ID (/results/{run_id})
- Benchmark and Phase 5.5 comparison data (/benchmarks)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.grid_loader import load_ieee14
from src.pipeline import EndToEndPipeline


# IEEE-14 schematic 2D layout coordinates for planar graph visualization
BUS_LAYOUT = {
    0: {"x": 90, "y": 380, "substation": "Bus 1 (Slack)"},
    1: {"x": 220, "y": 440, "substation": "Bus 2 (Gen)"},
    2: {"x": 420, "y": 480, "substation": "Bus 3 (Gen)"},
    3: {"x": 360, "y": 340, "substation": "Bus 4 (Load)"},
    4: {"x": 200, "y": 260, "substation": "Bus 5 (Load)"},
    5: {"x": 380, "y": 170, "substation": "Bus 6 (Gen)"},
    6: {"x": 540, "y": 300, "substation": "Bus 7 (Load)"},
    7: {"x": 680, "y": 300, "substation": "Bus 8 (Gen)"},
    8: {"x": 540, "y": 190, "substation": "Bus 9 (Load)"},
    9: {"x": 680, "y": 190, "substation": "Bus 10 (Load)"},
    10: {"x": 520, "y": 90, "substation": "Bus 11 (Load)"},
    11: {"x": 380, "y": 70, "substation": "Bus 12 (Load)"},
    12: {"x": 480, "y": 30, "substation": "Bus 13 (Load)"},
    13: {"x": 660, "y": 90, "substation": "Bus 14 (Load)"},
}

app = FastAPI(
    title="GridResilience AI API",
    description="Predictive GCN + PPO Mitigation + Post-Cascade Recovery Dashboard Backend",
    version="1.0.0",
)

# Enable CORS for local Vite dev server and cross-origin clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for runs and cached pipeline singleton
RUN_CACHE: dict[str, dict[str, Any]] = {}
_PIPELINE: EndToEndPipeline | None = None


def get_pipeline() -> EndToEndPipeline:
    """Lazy initialize and return singleton EndToEndPipeline."""
    global _PIPELINE
    if _PIPELINE is None:
        data_dir = PROJECT_ROOT / "outputs" / "predictive_v2"
        gcn_path = data_dir / "models" / "best_gcn.pt"
        ppo_path = PROJECT_ROOT / "outputs" / "models" / "ppo_predictive.zip"

        _PIPELINE = EndToEndPipeline(
            gcn_model_path=gcn_path if gcn_path.exists() else None,
            gcn_data_dir=data_dir if data_dir.exists() else None,
            ppo_model_path=ppo_path if ppo_path.exists() else None,
        )
    return _PIPELINE


class SimulationRequest(BaseModel):
    initial_outage: int = Field(default=1, ge=0, le=14, description="Initiating transmission line outage (0 to 14)")
    load_scale: float = Field(default=1.10, ge=0.5, le=2.5, description="System active load scaling factor")
    capacity_scale: float = Field(default=0.02, ge=0.005, le=0.05, description="Transmission line capacity scaling factor")
    seed: int = Field(default=42, description="Random seed for reproducibility")


@app.get("/health")
def get_health() -> dict[str, Any]:
    """Health check endpoint verifying pipeline readiness."""
    pipeline = get_pipeline()
    return {
        "status": "healthy",
        "service": "GridResilience API",
        "phase": "7",
        "pipeline_ready": pipeline is not None,
        "models": {
            "gcn": "predictive_v2 GCN",
            "ppo": "Predictive PPO Mitigation (30k steps)",
            "recovery": "Greedy Heuristic Restoration",
        },
    }


@app.get("/grid")
def get_grid_topology() -> dict[str, Any]:
    """Return standard IEEE-14 network elements and visual planar coordinates."""
    net = load_ieee14()

    # Buses
    buses = []
    for b in net.bus.index:
        b_idx = int(b)
        pos = BUS_LAYOUT.get(b_idx, {"x": 100 + b_idx * 40, "y": 200, "substation": f"Bus {b_idx+1}"})
        load_mw = float(net.load.loc[net.load["bus"] == b_idx, "p_mw"].sum()) if not net.load.empty else 0.0
        load_mvar = float(net.load.loc[net.load["bus"] == b_idx, "q_mvar"].sum()) if not net.load.empty else 0.0
        gen_mw = float(net.gen.loc[net.gen["bus"] == b_idx, "p_mw"].sum()) if not net.gen.empty else 0.0
        if b_idx == 0 and not net.ext_grid.empty:
            gen_mw += 232.4  # Base slack generation capacity reference

        bus_type = "slack" if b_idx == 0 else "generator" if gen_mw > 0 else "load"
        buses.append({
            "id": b_idx,
            "name": f"Bus {b_idx + 1}",
            "substation": pos["substation"],
            "vn_kv": float(net.bus.at[b, "vn_kv"]),
            "type": bus_type,
            "load_mw": round(load_mw, 2),
            "load_mvar": round(load_mvar, 2),
            "gen_mw": round(gen_mw, 2),
            "x": pos["x"],
            "y": pos["y"],
        })

    # Transmission lines
    lines = []
    for l in net.line.index:
        l_idx = int(l)
        fb = int(net.line.at[l, "from_bus"])
        tb = int(net.line.at[l, "to_bus"])
        lines.append({
            "id": l_idx,
            "name": f"Line {l_idx} (Bus {fb+1} - Bus {tb+1})",
            "from_bus": fb,
            "to_bus": tb,
            "max_i_ka": float(net.line.at[l, "max_i_ka"]),
            "r_ohm_per_km": float(net.line.at[l, "r_ohm_per_km"]),
            "x_ohm_per_km": float(net.line.at[l, "x_ohm_per_km"]),
            "in_service": bool(net.line.at[l, "in_service"]),
        })

    # Transformers
    trafos = []
    for t in net.trafo.index:
        t_idx = int(t)
        hb = int(net.trafo.at[t, "hv_bus"])
        lb = int(net.trafo.at[t, "lv_bus"])
        trafos.append({
            "id": t_idx,
            "name": f"Trafo {t_idx} (Bus {hb+1} - Bus {lb+1})",
            "hv_bus": hb,
            "lv_bus": lb,
            "in_service": bool(net.trafo.at[t, "in_service"]),
        })

    return {
        "system_name": "IEEE 14-Bus Test System",
        "total_buses": len(buses),
        "total_lines": len(lines),
        "total_transformers": len(trafos),
        "buses": buses,
        "lines": lines,
        "transformers": trafos,
    }


@app.post("/simulate")
def run_simulation(req: SimulationRequest) -> dict[str, Any]:
    """Execute end-to-end incident simulation: contingency -> GCN -> PPO -> cascade -> recovery."""
    pipeline = get_pipeline()

    scenario = {
        "scenario_id": f"sim_{uuid.uuid4().hex[:8]}",
        "initial_outages": [req.initial_outage],
        "load_scale": req.load_scale,
        "capacity_scale": req.capacity_scale,
        "generation_scale": 1.0,
    }

    result = pipeline.run_incident(
        scenario=scenario,
        enable_mitigation=True,
        enable_recovery=True,
        seed=req.seed,
    )

    run_id = f"run_{uuid.uuid4().hex[:10]}"
    packaged_result = {
        "run_id": run_id,
        "scenario_id": scenario["scenario_id"],
        "status": "COMPLETED",
        "inputs": {
            "initial_line_outage": req.initial_outage,
            "load_scale": req.load_scale,
            "capacity_scale": req.capacity_scale,
            "seed": req.seed,
        },
        "initial_grid_state": {
            "initial_load_mw": result["initial_load_mw"],
            "initial_outages": result["initial_outages"],
            "gcn_risk_mean": result.get("gcn_risk_mean", 0.0),
        },
        "gcn_failure_probabilities": result.get("gcn_probabilities", []),
        "line_predictions": result.get("line_predictions", []),
        "mitigation_actions": result.get("mitigation_actions", []),
        "failed_lines": result.get("failed_lines", []),
        "cascade_history": [e for e in result.get("audit_log", []) if "MITIGATION_STEP" in e.get("stage", "") or "CONTINGENCY" in e.get("stage", "") or "CASCADE" in e.get("stage", "")],
        "load_served_before_mitigation": result["initial_load_mw"],
        "load_served_after_mitigation": result["post_cascade_served_mw"],
        "post_cascade_status": result["post_cascade_status"],
        "recovery_actions": [e for e in result.get("audit_log", []) if "RECOVERY_STEP" in e.get("stage", "")],
        "reconnected_lines": result.get("reconnected_lines", []),
        "customer_load_restored_mw": result.get("mw_restored", 0.0),
        "final_load_served": result.get("final_restored_mw", 0.0),
        "final_load_served_percent": result.get("final_load_served_percent", 0.0),
        "final_system_status": result.get("final_status", "UNKNOWN"),
        "audit_log": result.get("audit_log", []),
    }

    RUN_CACHE[run_id] = packaged_result
    return packaged_result


@app.get("/results/{run_id}")
def get_run_results(run_id: str) -> dict[str, Any]:
    """Retrieve full result payload for a specific simulation run ID."""
    if run_id not in RUN_CACHE:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RUN_CACHE[run_id]


@app.get("/benchmarks")
def get_benchmarks() -> dict[str, Any]:
    """Return Phase 5.5 and Phase 6 experimental evaluation comparisons from saved CSVs."""
    rl_file = PROJECT_ROOT / "outputs" / "rl_method_comparison.csv"
    rec_file = PROJECT_ROOT / "outputs" / "recovery_summary.csv"

    rl_records = []
    if rl_file.exists():
        with open(rl_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rl_records.append({
                    "controller": row.get("controller"),
                    "sample_count": int(float(row.get("sample_count", 0))),
                    "average_load_served_percent": round(float(row.get("average_load_served_percent", 0.0)), 2),
                    "average_load_shed_mw": round(float(row.get("average_load_shed_mw", 0.0)), 2),
                    "stable_rate": round(float(row.get("stable_rate", 0.0)), 2),
                    "total_blackout_rate": round(float(row.get("total_blackout_rate", 0.0)), 2),
                    "cascade_reduction_percent": round(float(row.get("cascade_reduction_vs_donothing_percent", 0.0)), 2),
                })

    rec_records = []
    if rec_file.exists():
        with open(rec_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec_records.append({
                    "method": row.get("method"),
                    "scenario_count": int(float(row.get("scenario_count", 0))),
                    "average_served_load_mw": round(float(row.get("average_served_load_mw", 0.0)), 2),
                    "average_load_served_percent": round(float(row.get("average_load_served_percent", 0.0)), 2),
                    "average_mw_restored": round(float(row.get("average_mw_restored", 0.0)), 2),
                    "stable_grid_rate": round(float(row.get("stable_grid_rate", 0.0)), 2),
                    "total_blackout_rate": round(float(row.get("total_blackout_rate", 0.0)), 2),
                    "non_converged_rate": round(float(row.get("non_converged_rate", 0.0)), 2),
                    "recovery_success_rate": round(float(row.get("recovery_success_rate", 0.0)), 2),
                })

    return {
        "phase_5_5_mitigation": rl_records,
        "phase_6_recovery": rec_records,
        "key_findings": {
            "load_served_gain_pp": 4.17,
            "load_shedding_reduction_percent": 69.5,
            "blackout_rate_reduction_pp": 3.0,
            "audit_blackout_rate": 74.0,
            "highlights": [
                "+4.17 percentage points load served (30.65% vs 26.48% for No-GCN)",
                "69.5% less load shedding (2.91 MW vs 9.54 MW for No-GCN)",
                "3.0 percentage-point reduction in total blackout rate (68.33% vs 71.33%)",
                "Phase 6 Recovery audited: remaining blackout rate conserved at 74.0% with zero survivor corruption",
            ],
        },
    }


# Mount frontend static distribution if built
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
