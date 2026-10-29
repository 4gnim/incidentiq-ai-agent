
import sqlite3
from pathlib import Path

from incidentiq.config import DB_PATH


def get_connection(
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(
    db_path: str | Path | None = None,
) -> None:
    """Create the IncidentIQ database schema."""
    connection = get_connection(db_path)

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS services (
                service_id TEXT PRIMARY KEY,
                service_name TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('healthy', 'degraded', 'down')),
                latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
                error_rate_pct REAL NOT NULL
                    CHECK (error_rate_pct >= 0 AND error_rate_pct <= 100),
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                severity TEXT NOT NULL
                    CHECK (severity IN ('SEV1', 'SEV2', 'SEV3', 'SEV4')),
                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'open',
                            'investigating',
                            'mitigated',
                            'resolved'
                        )
                    ),
                service_id TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (service_id)
                    REFERENCES services(service_id)
            );

            CREATE TABLE IF NOT EXISTS deployments (
                deployment_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                version TEXT NOT NULL,
                deployed_at TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (
                        status IN ('successful', 'failed', 'rolled_back')
                    ),
                change_summary TEXT NOT NULL,
                FOREIGN KEY (service_id)
                    REFERENCES services(service_id)
            );

            CREATE TABLE IF NOT EXISTS incident_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                service_id TEXT NOT NULL,
                logged_at TEXT NOT NULL,
                level TEXT NOT NULL
                    CHECK (
                        level IN (
                            'DEBUG',
                            'INFO',
                            'WARNING',
                            'ERROR',
                            'CRITICAL'
                        )
                    ),
                message TEXT NOT NULL,
                UNIQUE (incident_id, logged_at, message),
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(incident_id),
                FOREIGN KEY (service_id)
                    REFERENCES services(service_id)
            );

            CREATE INDEX IF NOT EXISTS idx_incidents_service
                ON incidents(service_id);

            CREATE INDEX IF NOT EXISTS idx_logs_incident_time
                ON incident_logs(incident_id, logged_at);

            CREATE INDEX IF NOT EXISTS idx_deployments_service_time
                ON deployments(service_id, deployed_at);
            """
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")
