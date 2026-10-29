
from pathlib import Path

from incidentiq.database import get_connection


def get_incident_details(
    incident_id: str,
    db_path: str | Path | None = None,
) -> dict | None:
    """Retrieve incident details and its affected service."""
    connection = get_connection(db_path)

    try:
        row = connection.execute(
            """
            SELECT
                i.incident_id,
                i.title,
                i.severity,
                i.status AS incident_status,
                i.description,
                i.created_at,
                s.service_id,
                s.service_name,
                s.status AS service_status,
                s.latency_ms,
                s.error_rate_pct
            FROM incidents AS i
            JOIN services AS s
                ON s.service_id = i.service_id
            WHERE i.incident_id = ?
            """,
            (incident_id,),
        ).fetchone()

        return dict(row) if row else None
    finally:
        connection.close()


def get_incident_timeline(
    incident_id: str,
    limit: int = 100,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Retrieve incident logs in chronological order."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500.")

    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            """
            SELECT
                log_id,
                incident_id,
                service_id,
                logged_at,
                level,
                message
            FROM incident_logs
            WHERE incident_id = ?
            ORDER BY logged_at ASC, log_id ASC
            LIMIT ?
            """,
            (incident_id, limit),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_deployment_history(
    service_id: str,
    limit: int = 10,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Retrieve recent deployments for a service."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")

    connection = get_connection(db_path)

    try:
        rows = connection.execute(
            """
            SELECT
                deployment_id,
                service_id,
                version,
                deployed_at,
                status,
                change_summary
            FROM deployments
            WHERE service_id = ?
            ORDER BY deployed_at DESC, deployment_id DESC
            LIMIT ?
            """,
            (service_id, limit),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_service_status(
    service_id: str,
    db_path: str | Path | None = None,
) -> dict | None:
    """Retrieve the latest recorded service status and metrics."""
    connection = get_connection(db_path)

    try:
        row = connection.execute(
            """
            SELECT
                service_id,
                service_name,
                status,
                latency_ms,
                error_rate_pct,
                updated_at
            FROM services
            WHERE service_id = ?
            """,
            (service_id,),
        ).fetchone()

        return dict(row) if row else None
    finally:
        connection.close()
