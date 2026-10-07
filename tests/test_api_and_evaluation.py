from pathlib import Path

from fastapi.testclient import TestClient

from launchguard.api import create_app
from launchguard.evaluation import run_evaluation

ROOT = Path(__file__).parents[1]


def test_api_start_review_and_resume(workflow, sku) -> None:
    app = create_app(workflow=workflow)
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        started = client.post("/api/runs", json={"sku": sku.model_dump(mode="json")})
        assert started.status_code == 201
        run_id = started.json()["run"]["run_id"]
        assert started.json()["run"]["status"] == "pending_approval"
        decision = client.post(
            f"/api/runs/{run_id}/decision",
            json={"action": "approve", "reviewer": "API reviewer", "note": "Reviewed"},
        )
        assert decision.status_code == 200
        assert decision.json()["run"]["delivery"]["status"] == "prepared"
        assert client.get(f"/api/runs/{run_id}").status_code == 200
        assert client.get("/api/runs").json()


def test_api_returns_clear_not_found_and_conflict(workflow, sku) -> None:
    app = create_app(workflow=workflow)
    with TestClient(app) as client:
        assert client.get("/api/runs/missing").status_code == 404
        started = client.post("/api/runs", json={"sku": sku.model_dump(mode="json")}).json()
        run_id = started["run"]["run_id"]
        payload = {"action": "reject", "reviewer": "API reviewer"}
        assert client.post(f"/api/runs/{run_id}/decision", json=payload).status_code == 200
        assert client.post(f"/api/runs/{run_id}/decision", json=payload).status_code == 409


def test_bundled_evaluation_passes_all_gates() -> None:
    result = run_evaluation(
        ROOT / "examples" / "policies", ROOT / "evals" / "cases.json"
    )
    assert result["passed"] is True
    assert result["decision_accuracy"] == 1
    assert result["price_floor_pass_rate"] == 1
    assert result["citation_coverage"] == 1
