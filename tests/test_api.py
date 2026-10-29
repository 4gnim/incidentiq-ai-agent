
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import incidentiq.api as api


class FakeGraph:
    """Graph tiruan untuk menguji respons API."""

    def invoke(self, *args, **kwargs):
        return {"error": "Incident not found: INC-9999"}

    def get_state(self, config):
        return SimpleNamespace(values={}, next=())


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Pisahkan database checkpoint pengujian dari database aplikasi.
    monkeypatch.setattr(
        api,
        "CHECKPOINT_DB_PATH",
        tmp_path / "test_checkpoints.sqlite",
    )

    with TestClient(api.app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_investigation_requires_incident_id(client):
    response = client.post(
        "/incidents/investigate",
        json={},
    )

    assert response.status_code == 422


def test_unknown_incident_returns_404(client, monkeypatch):
    monkeypatch.setattr(api, "get_graph", lambda: FakeGraph())

    response = client.post(
        "/incidents/investigate",
        json={"incident_id": "INC-9999"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Incident not found: INC-9999"
    )


def test_unknown_approval_thread_returns_404(client, monkeypatch):
    monkeypatch.setattr(api, "get_graph", lambda: FakeGraph())

    response = client.post(
        "/incidents/unknown-thread/approval",
        json={
            "approved": True,
            "reason": "Test",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Investigation thread not found."
    )


def test_list_incidents_returns_incidents(client, monkeypatch):
    sample_incident = {
        "incident_id": "INC-1001",
        "title": "Checkout HTTP 500 spike",
        "severity": "SEV2",
        "incident_status": "investigating",
        "service_id": "svc-checkout",
        "description": "Synthetic checkout failure",
        "created_at": "2026-01-01 09:05:30",
        "service_name": "Checkout API",
        "service_status": "degraded",
        "latency_ms": 920,
        "error_rate_pct": 18.5,
    }

    class FakeResult:
        def fetchall(self):
            return [sample_incident]

    class FakeConnection:
        def execute(self, query):
            return FakeResult()

        def close(self):
            pass

    monkeypatch.setattr(
        api,
        "get_connection",
        lambda: FakeConnection(),
    )

    response = client.get("/incidents")

    assert response.status_code == 200
    assert len(response.json()["incidents"]) == 1
    assert response.json()["incidents"][0]["incident_id"] == "INC-1001"
    assert response.json()["incidents"][0]["service_status"] == "degraded"



def test_list_services_returns_accurate_summary(client, monkeypatch):
    sample_services = [
        {
            "service_id": "svc-checkout",
            "service_name": "Checkout API",
            "status": "degraded",
            "latency_ms": 920,
            "error_rate_pct": 18.5,
            "updated_at": "2026-10-29 09:00:00",
        },
        {
            "service_id": "svc-payment",
            "service_name": "Payment Gateway",
            "status": "down",
            "latency_ms": 5000,
            "error_rate_pct": 68.0,
            "updated_at": "2026-10-29 09:00:00",
        },
        {
            "service_id": "svc-catalog",
            "service_name": "Product Catalog",
            "status": "healthy",
            "latency_ms": 120,
            "error_rate_pct": 0.9,
            "updated_at": "2026-10-29 09:00:00",
        },
    ]

    class FakeResult:
        def fetchall(self):
            return sample_services

    class FakeConnection:
        def execute(self, query):
            return FakeResult()

        def close(self):
            pass

    monkeypatch.setattr(
        api,
        "get_connection",
        lambda: FakeConnection(),
    )

    response = client.get("/services")

    assert response.status_code == 200

    payload = response.json()

    assert payload["summary"] == {
        "total": 3,
        "healthy": 1,
        "degraded": 1,
        "down": 1,
    }

    assert len(payload["services"]) == 3

    statuses = {
        service["service_id"]: service["status"]
        for service in payload["services"]
    }

    assert statuses["svc-payment"] == "down"
    assert statuses["svc-checkout"] == "degraded"
    assert statuses["svc-catalog"] == "healthy"



def test_investigation_returns_collected_evidence(client, monkeypatch):
    evidence = {
        "service": {
            "service_id": "svc-checkout",
            "status": "degraded",
        },
        "timeline": [
            {
                "level": "ERROR",
                "message": "tax_code is missing",
            }
        ],
        "deployments": [],
        "runbooks": [
            {
                "source": "01-checkout-http-500.md",
                "content": "Investigate checkout HTTP 500 errors.",
                "distance": 0.25,
            }
        ],
    }

    state = {
        "incident": {"incident_id": "INC-1001"},
        "analysis": "Test investigation analysis",
        "proposed_action": {
            "action": "simulate_rollback",
            "description": "Simulate a rollback",
        },
        "evidence": evidence,
    }

    class FakeGraph:
        def invoke(self, *args, **kwargs):
            return {"__interrupt__": [object()]}

        def get_state(self, config):
            return SimpleNamespace(
                values=state,
                next=("request_approval",),
            )

    monkeypatch.setattr(
        api,
        "get_graph",
        lambda: FakeGraph(),
    )

    response = client.post(
        "/incidents/investigate",
        json={"incident_id": "INC-1001"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "awaiting_approval"
    assert payload["evidence"]["service"]["status"] == "degraded"
    assert payload["evidence"]["timeline"][0]["level"] == "ERROR"
    assert payload["evidence"]["runbooks"][0]["source"] == (
        "01-checkout-http-500.md"
    )



def test_approval_endpoint_returns_simulated_result(client, monkeypatch):
    class FakeGraph:
        def get_state(self, config):
            return SimpleNamespace(
                values={"incident": {"incident_id": "INC-1001"}},
                next=("request_approval",),
            )

        def invoke(self, command, config):
            assert command.resume["approved"] is True
            assert command.resume["reason"] == "Approved in test"

            return {
                "execution_result": {
                    "status": "simulated",
                    "action": "simulate_rollback",
                    "message": "Simulation completed.",
                },
                "verification": {
                    "status": "simulation_only",
                    "real_service_health_checked": False,
                },
            }

    monkeypatch.setattr(
        api,
        "get_graph",
        lambda: FakeGraph(),
    )

    response = client.post(
        "/incidents/test-approval-thread/approval",
        json={
            "approved": True,
            "reason": "Approved in test",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "simulated"
    assert payload["execution_result"]["action"] == "simulate_rollback"
    assert payload["verification"]["status"] == "simulation_only"
    assert payload["real_service_modified"] is False


def test_rejection_endpoint_returns_rejected_result(client, monkeypatch):
    class FakeGraph:
        def get_state(self, config):
            return SimpleNamespace(
                values={"incident": {"incident_id": "INC-1001"}},
                next=("request_approval",),
            )

        def invoke(self, command, config):
            assert command.resume["approved"] is False
            assert command.resume["reason"] == "Rejected in test"

            return {
                "execution_result": {
                    "status": "rejected",
                    "message": (
                        "Human approval was not granted; "
                        "no action was executed."
                    ),
                },
                "verification": {
                    "status": "not_executed",
                    "real_service_health_checked": False,
                },
            }

    monkeypatch.setattr(
        api,
        "get_graph",
        lambda: FakeGraph(),
    )

    response = client.post(
        "/incidents/test-rejection-thread/approval",
        json={
            "approved": False,
            "reason": "Rejected in test",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "rejected"
    assert payload["execution_result"]["status"] == "rejected"
    assert payload["verification"]["status"] == "not_executed"
    assert payload["real_service_modified"] is False
