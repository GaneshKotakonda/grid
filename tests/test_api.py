"""Focused test suite for GridResilience FastAPI backend endpoints.

Validates:
- Health check endpoint (/health)
- Grid topology elements and layout (/grid)
- Simulation endpoint execution and contract (/simulate)
- Run result retrieval and 404 handling (/results/{run_id})
- Benchmark data serialization from real CSVs (/benchmarks)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import app, RUN_CACHE


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_api_health(client):
    """Test health check returns operational status and model readiness."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "GridResilience API"
    assert data["phase"] == "7"
    assert "models" in data
    assert "gcn" in data["models"]
    assert "ppo" in data["models"]


def test_grid_topology(client):
    """Test grid endpoint returns all 14 buses and 15 lines with visual layout."""
    response = client.get("/grid")
    assert response.status_code == 200
    data = response.json()
    assert data["total_buses"] == 14
    assert data["total_lines"] == 15
    assert len(data["buses"]) == 14
    assert len(data["lines"]) == 15
    assert len(data["transformers"]) == 5

    # Verify first bus schema
    bus0 = data["buses"][0]
    assert bus0["id"] == 0
    assert "x" in bus0 and "y" in bus0
    assert "vn_kv" in bus0
    assert bus0["type"] in ("slack", "generator", "load")

    # Verify first line schema
    line0 = data["lines"][0]
    assert line0["id"] == 0
    assert "from_bus" in line0
    assert "to_bus" in line0
    assert "max_i_ka" in line0


def test_simulation_endpoint_and_result_retrieval(client):
    """Test POST /simulate runs full pipeline and stores result retrievable via GET /results/{run_id}."""
    payload = {
        "initial_outage": 1,
        "load_scale": 1.10,
        "capacity_scale": 0.02,
        "seed": 42,
    }
    response = client.post("/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    run_id = data["run_id"]
    assert data["status"] == "COMPLETED"

    # Verify required data contract fields
    assert "initial_grid_state" in data
    assert "gcn_failure_probabilities" in data
    assert len(data["gcn_failure_probabilities"]) == 15
    assert "line_predictions" in data
    assert len(data["line_predictions"]) == 15
    assert "mitigation_actions" in data
    assert "failed_lines" in data
    assert "cascade_history" in data
    assert "load_served_before_mitigation" in data
    assert "load_served_after_mitigation" in data
    assert "recovery_actions" in data
    assert "final_load_served" in data
    assert "final_system_status" in data

    # Verify line prediction item schema
    pred0 = data["line_predictions"][0]
    assert "line_index" in pred0
    assert "probability" in pred0
    assert "risk_rank" in pred0
    assert "risk_level" in pred0

    # Retrieve by run_id
    res_resp = client.get(f"/results/{run_id}")
    assert res_resp.status_code == 200
    retrieved = res_resp.json()
    assert retrieved["run_id"] == run_id
    assert retrieved["final_system_status"] == data["final_system_status"]


def test_results_not_found(client):
    """Test invalid run_id returns HTTP 404."""
    response = client.get("/results/nonexistent_run_99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_benchmarks_endpoint(client):
    """Test benchmark endpoint parses saved real results from Phase 5.5 and Phase 6."""
    response = client.get("/benchmarks")
    assert response.status_code == 200
    data = response.json()

    assert "phase_5_5_mitigation" in data
    assert "phase_6_recovery" in data
    assert "key_findings" in data

    findings = data["key_findings"]
    assert findings["load_served_gain_pp"] == 4.17
    assert findings["load_shedding_reduction_percent"] == 69.5
    assert findings["blackout_rate_reduction_pp"] == 3.0

    # Verify real controllers are present
    controllers = [r["controller"] for r in data["phase_5_5_mitigation"]]
    assert "Do-Nothing" in controllers
    assert "PPO (Predictive GCN)" in controllers
