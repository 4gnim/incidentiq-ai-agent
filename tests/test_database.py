
import sqlite3

from incidentiq.database import get_connection, initialize_database
from incidentiq.seed_data import seed_demo_data


def test_initialize_database_creates_required_tables(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"

    initialize_database(db_path)
    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {row["name"] for row in rows}

        assert {
            "services",
            "incidents",
            "deployments",
            "incident_logs",
        }.issubset(table_names)
    finally:
        connection.close()



def test_seed_demo_data_creates_expected_records(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"

    counts = seed_demo_data(db_path)

    assert counts["services"] == 15
    assert counts["incidents"] == 120
    assert counts["deployments"] >= 60
    assert counts["incident_logs"] >= 2000


def test_seed_demo_data_is_idempotent(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"

    first_counts = seed_demo_data(db_path)
    second_counts = seed_demo_data(db_path)

    assert second_counts == first_counts


def test_seeded_data_has_valid_foreign_keys(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"

    seed_demo_data(db_path)
    connection = get_connection(db_path)

    try:
        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert violations == []
    finally:
        connection.close()


def test_database_rejects_incident_with_unknown_service(tmp_path):
    db_path = tmp_path / "test_incidentiq.db"

    initialize_database(db_path)
    connection = get_connection(db_path)

    try:
        try:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, title, severity, status,
                    service_id, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "INC-9999",
                    "Invalid test incident",
                    "SEV2",
                    "investigating",
                    "svc-does-not-exist",
                    "Test foreign key enforcement",
                    "2026-10-28T12:00:00Z",
                ),
            )
            connection.commit()
            assert False, "Expected foreign key violation."
        except sqlite3.IntegrityError:
            connection.rollback()
    finally:
        connection.close()
