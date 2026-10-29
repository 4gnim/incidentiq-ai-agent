
import pytest

from incidentiq.seed_data import seed_demo_data
from incidentiq.tools import (
    get_deployment_history,
    get_incident_details,
    get_incident_timeline,
    get_service_status,
)


@pytest.fixture
def seeded_db(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"
    seed_demo_data(db_path)
    return db_path


def test_get_incident_details_returns_known_incident(seeded_db):
    incident = get_incident_details("INC-1001", seeded_db)

    assert incident is not None
    assert incident["incident_id"] == "INC-1001"
    assert incident["service_id"] == "svc-checkout"
    assert incident["severity"] == "SEV2"


def test_get_incident_details_returns_none_for_unknown_id(seeded_db):
    incident = get_incident_details("INC-9999", seeded_db)

    assert incident is None


def test_get_incident_timeline_is_chronological(seeded_db):
    logs = get_incident_timeline("INC-1001", db_path=seeded_db)

    assert len(logs) == 4
    assert logs[0]["logged_at"] <= logs[-1]["logged_at"]
    assert any("tax_code" in log["message"] for log in logs)


def test_get_incident_timeline_respects_limit(seeded_db):
    logs = get_incident_timeline(
        "INC-1001",
        limit=2,
        db_path=seeded_db,
    )

    assert len(logs) == 2


def test_get_incident_timeline_rejects_invalid_limit(seeded_db):
    with pytest.raises(ValueError):
        get_incident_timeline(
            "INC-1001",
            limit=0,
            db_path=seeded_db,
        )


def test_get_deployment_history_returns_service_deployments(seeded_db):
    deployments = get_deployment_history(
        "svc-checkout",
        db_path=seeded_db,
    )

    assert len(deployments) >= 1
    assert all(
        deployment["service_id"] == "svc-checkout"
        for deployment in deployments
    )


def test_get_deployment_history_rejects_invalid_limit(seeded_db):
    with pytest.raises(ValueError):
        get_deployment_history(
            "svc-checkout",
            limit=101,
            db_path=seeded_db,
        )


def test_get_service_status_returns_known_service(seeded_db):
    service = get_service_status("svc-payment", seeded_db)

    assert service is not None
    assert service["service_name"] == "Payment API"
    assert service["status"] == "down"
    assert service["error_rate_pct"] == 68.0


def test_get_service_status_returns_none_for_unknown_service(seeded_db):
    service = get_service_status("svc-unknown", seeded_db)

    assert service is None
