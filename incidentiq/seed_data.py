
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from incidentiq.config import DB_PATH
from incidentiq.database import get_connection, initialize_database


SERVICE_DEFINITIONS = [
    ("svc-checkout", "Checkout API"),
    ("svc-orders-db", "Orders Database"),
    ("svc-payment", "Payment API"),
    ("svc-auth", "Authentication Service"),
    ("svc-inventory", "Inventory Service"),
    ("svc-notification", "Notification Service"),
    ("svc-api-gateway", "API Gateway"),
    ("svc-user-profile", "User Profile Service"),
    ("svc-search", "Product Search Service"),
    ("svc-catalog", "Product Catalog Service"),
    ("svc-shipping", "Shipping Service"),
    ("svc-reporting", "Reporting Service"),
    ("svc-cache", "Redis Cache"),
    ("svc-worker", "Background Worker"),
    ("svc-storage", "Object Storage"),
]

INCIDENT_TYPES = [
    {
        "title": "HTTP 500 error spike",
        "description": "HTTP 500 rate increased above the configured threshold.",
        "symptoms": [
            "HTTP 500 rate increased after a request payload change.",
            "Unhandled exception observed in application logs.",
            "Error rate exceeded the configured alert threshold.",
        ],
    },
    {
        "title": "Database query latency",
        "description": "Query latency increased and database resources are under pressure.",
        "symptoms": [
            "P95 query latency increased above 1000 ms.",
            "Database CPU utilization is elevated.",
            "Connection pool utilization is approaching capacity.",
        ],
    },
    {
        "title": "Upstream dependency timeout",
        "description": "Requests to an upstream dependency are timing out.",
        "symptoms": [
            "Upstream requests exceeded the configured timeout.",
            "Request retries increased during the incident window.",
            "Dependency response time increased significantly.",
        ],
    },
    {
        "title": "Deployment regression",
        "description": "Service errors increased after a software deployment.",
        "symptoms": [
            "Error rate increased shortly after a deployment.",
            "New application version reports unexpected exceptions.",
            "Service health checks started failing after a release.",
        ],
    },
    {
        "title": "Memory pressure",
        "description": "Memory usage increased and service responsiveness degraded.",
        "symptoms": [
            "Memory utilization exceeded 90%.",
            "Garbage collection frequency increased.",
            "Request latency increased during memory pressure.",
        ],
    },
    {
        "title": "Health check failure",
        "description": "The service health check is failing intermittently.",
        "symptoms": [
            "Health check endpoint returned unsuccessful responses.",
            "Service readiness checks failed repeatedly.",
            "The service became unavailable to some requests.",
        ],
    },
    {
        "title": "Background job backlog",
        "description": "Background jobs are accumulating faster than they are processed.",
        "symptoms": [
            "Pending job count increased over the monitoring window.",
            "Worker processing latency increased.",
            "Queue consumption rate fell below incoming job rate.",
        ],
    },
    {
        "title": "Cache performance degradation",
        "description": "Cache latency increased and cache effectiveness decreased.",
        "symptoms": [
            "Cache response latency increased.",
            "Cache miss rate increased above its baseline.",
            "More requests reached the underlying database.",
        ],
    },
]

LOG_LEVELS = ["INFO", "INFO", "WARNING", "ERROR", "CRITICAL"]

BASE_TIME = datetime(2026, 10, 1, tzinfo=timezone.utc)


def iso_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_dataset():
    """Generate a reproducible synthetic incident dataset."""
    rng = random.Random(20261029)

    
    services = []

    for index, (service_id, name) in enumerate(SERVICE_DEFINITIONS):
        status = "healthy"
        latency_ms = 80 + (index * 37) % 420
        error_rate_pct = round(0.1 + (index % 5) * 0.2, 2)

        # Keep the service state consistent with the baseline incidents.
        if service_id == "svc-checkout":
            status = "degraded"
            latency_ms = 920
            error_rate_pct = 18.5
        elif service_id == "svc-orders-db":
            status = "degraded"
            latency_ms = 1500
            error_rate_pct = 2.1
        elif service_id == "svc-payment":
            status = "down"
            latency_ms = 5000
            error_rate_pct = 68.0

        services.append(
            (
                service_id,
                name,
                status,
                latency_ms,
                error_rate_pct,
                iso_time(BASE_TIME + timedelta(days=29)),
            )
        )


    incidents = [
        (
            "INC-1001",
            "Checkout HTTP 500 spike",
            "SEV2",
            "investigating",
            "svc-checkout",
            "HTTP 500 errors increased after a checkout deployment.",
            "2026-10-28T09:05:30Z",
        ),
        (
            "INC-1002",
            "Orders database latency",
            "SEV2",
            "investigating",
            "svc-orders-db",
            "Database query latency and connection pool utilization increased.",
            "2026-10-28T10:15:00Z",
        ),
        (
            "INC-1003",
            "Payment gateway timeouts",
            "SEV1",
            "investigating",
            "svc-payment",
            "Payment requests are timing out while calling the upstream gateway.",
            "2026-10-28T11:40:00Z",
        ),
    ]

    deployments = [
        (
            "DEP-2001",
            "svc-checkout",
            "v2.4.1",
            "2026-10-28T09:03:00Z",
            "successful",
            "Refactored tax calculation and checkout payload validation.",
        ),
        (
            "DEP-2002",
            "svc-orders-db",
            "v5.8.0",
            "2026-10-20T08:00:00Z",
            "successful",
            "Routine database maintenance release.",
        ),
        (
            "DEP-2003",
            "svc-payment",
            "v3.1.2",
            "2026-10-25T07:30:00Z",
            "successful",
            "Updated payment request tracing and timeout logging.",
        ),
    ]

    logs = [
        (
            "INC-1001", "svc-checkout", "2026-10-28T09:00:00Z",
            "INFO",
            "Baseline checkout HTTP 500 rate was 0.4% over the previous 15 minutes.",
        ),
        (
            "INC-1001", "svc-checkout", "2026-10-28T09:03:00Z",
            "INFO",
            "Deployment DEP-2001 version v2.4.1 completed successfully.",
        ),
        (
            "INC-1001", "svc-checkout", "2026-10-28T09:05:30Z",
            "WARNING",
            "HTTP 500 rate increased to 18.5%; configured alert threshold is 5%.",
        ),
        (
            "INC-1001", "svc-checkout", "2026-10-28T09:06:10Z",
            "ERROR",
            "Tax calculation failed: tax_code is missing from checkout payload.",
        ),
        (
            "INC-1002", "svc-orders-db", "2026-10-28T10:15:00Z",
            "INFO", "Database CPU utilization reached 88%.",
        ),
        (
            "INC-1002", "svc-orders-db", "2026-10-28T10:18:00Z",
            "WARNING",
            "P95 query latency reached 1500 ms; slow queries observed on orders by customer_id.",
        ),
        (
            "INC-1002", "svc-orders-db", "2026-10-28T10:22:00Z",
            "WARNING",
            "Connection pool utilization reached 98%; request retries are increasing.",
        ),
        (
            "INC-1003", "svc-payment", "2026-10-28T11:40:00Z",
            "WARNING",
            "Upstream payment gateway requests exceeded the 3000 ms warning threshold.",
        ),
        (
            "INC-1003", "svc-payment", "2026-10-28T11:42:00Z",
            "ERROR", "68% of payment requests timed out after 5000 ms.",
        ),
        (
            "INC-1003", "svc-payment", "2026-10-28T11:43:00Z",
            "CRITICAL",
            "Payment health check failed; the last recorded deployment was on 2026-10-25.",
        ),
    ]

    # Generate 117 additional incidents.
    for number in range(1004, 1121):
        service = rng.choice(SERVICE_DEFINITIONS)
        service_id, service_name = service
        incident_type = rng.choice(INCIDENT_TYPES)

        created = BASE_TIME + timedelta(
            days=rng.randint(0, 27),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )

        severity = rng.choices(
            ["SEV1", "SEV2", "SEV3", "SEV4"],
            weights=[5, 20, 45, 30],
            k=1,
        )[0]

        status = rng.choices(
            ["open", "investigating", "mitigated", "resolved"],
            weights=[10, 20, 20, 50],
            k=1,
        )[0]

        incident_id = f"INC-{number}"
        incident_title = f"{service_name}: {incident_type['title']}"

        incidents.append(
            (
                incident_id,
                incident_title,
                severity,
                status,
                service_id,
                incident_type["description"],
                iso_time(created),
            )
        )

        # Some incidents have a recent deployment; others do not.
        if rng.random() < 0.5:
            deployed = created - timedelta(
                hours=rng.randint(1, 72)
            )
            deployment_number = 2004 + number - 1004

            deployments.append(
                (
                    f"DEP-{deployment_number}",
                    service_id,
                    f"v{rng.randint(1, 5)}.{rng.randint(0, 12)}.{rng.randint(0, 9)}",
                    iso_time(deployed),
                    rng.choices(
                        ["successful", "failed", "rolled_back"],
                        weights=[85, 10, 5],
                        k=1,
                    )[0],
                    rng.choice(
                        [
                            "Dependency update",
                            "Performance optimization",
                            "Bug fix release",
                            "Configuration update",
                            "Routine application release",
                        ]
                    ),
                )
            )

        # Generate between 12 and 28 log records per incident.
        log_count = rng.randint(12, 28)
        for log_index in range(log_count):
            logged_at = created + timedelta(
                seconds=log_index * rng.randint(20, 120)
            )

            if log_index == 0:
                level = "WARNING"
            elif log_index == log_count - 1:
                level = rng.choice(["ERROR", "CRITICAL"])
            else:
                level = rng.choice(LOG_LEVELS)

            message = rng.choice(incident_type["symptoms"])

            logs.append(
                (
                    incident_id,
                    service_id,
                    iso_time(logged_at),
                    level,
                    f"{service_name}: {message}",
                )
            )

    # Additional deployment history for services with fewer releases.
    while len(deployments) < 60:
        service_id, service_name = rng.choice(SERVICE_DEFINITIONS)
        deployment_number = 2004 + len(deployments) - 3

        deployed = BASE_TIME + timedelta(
            days=rng.randint(0, 28),
            hours=rng.randint(0, 23),
        )

        deployments.append(
            (
                f"DEP-{deployment_number}",
                service_id,
                f"v{rng.randint(1, 5)}.{rng.randint(0, 12)}.{rng.randint(0, 9)}",
                iso_time(deployed),
                "successful",
                f"Routine release for {service_name}",
            )
        )

    # Deduplicate generated deployment IDs, keeping the first record.
    unique_deployments = {}
    for deployment in deployments:
        unique_deployments.setdefault(deployment[0], deployment)

    # A minimum target ensures a useful volume of logs.
    # Additional logs are deterministic and use existing incidents.
    logs_by_incident = {}
    for log in logs:
        logs_by_incident.setdefault(log[0], []).append(log)

    while len(logs) < 2000:
        incident = rng.choice(incidents)
        incident_id = incident[0]
        service_id = incident[4]
        created = datetime.fromisoformat(
            incident[6].replace("Z", "+00:00")
        )
        extra_number = len(logs)

        logs.append(
            (
                incident_id,
                service_id,
                iso_time(created + timedelta(seconds=extra_number)),
                "INFO",
                f"Diagnostic checkpoint {extra_number}: "
                "service metrics collected for incident investigation.",
            )
        )

    return (
        services,
        incidents,
        list(unique_deployments.values()),
        logs,
    )


def seed_demo_data(
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Seed deterministic company-scale demo data without duplicate records."""
    initialize_database(db_path)
    services, incidents, deployments, logs = build_dataset()
    connection = get_connection(db_path)

    try:
        connection.executemany(
            """
            INSERT OR IGNORE INTO services (
                service_id, service_name, status,
                latency_ms, error_rate_pct, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            services,
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO incidents (
                incident_id, title, severity, status,
                service_id, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            incidents,
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO deployments (
                deployment_id, service_id, version,
                deployed_at, status, change_summary
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            deployments,
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO incident_logs (
                incident_id, service_id, logged_at, level, message
            ) VALUES (?, ?, ?, ?, ?)
            """,
            logs,
        )

        connection.commit()

        counts = {}
        for table in (
            "services",
            "incidents",
            "deployments",
            "incident_logs",
        ):
            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM {table}"
            ).fetchone()
            counts[table] = row["total"]

        return counts
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    counts = seed_demo_data()
    print("IncidentIQ demo data is ready:")
    for table, count in counts.items():
        print(f"- {table}: {count} records")
    print(f"Database: {DB_PATH}")
