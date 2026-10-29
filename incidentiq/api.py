
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from incidentiq.config import DATA_DIR
from incidentiq.database import get_connection
from incidentiq.workflow import build_workflow


CHECKPOINT_DB_PATH = DATA_DIR / "incidentiq_checkpoints.sqlite"


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=50)


class ApprovalRequest(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(CHECKPOINT_DB_PATH),
        check_same_thread=False,
        timeout=30,
    )

    checkpointer = SqliteSaver(connection)
    checkpointer.setup()

    app.state.graph = build_workflow(checkpointer=checkpointer)

    try:
        yield
    finally:
        connection.close()


app = FastAPI(
    title="IncidentIQ API",
    description="AI-assisted incident investigation with human approval and simulated remediation.",
    version="1.0.0",
    lifespan=lifespan,
)


def get_graph():
    return app.state.graph


def get_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "IncidentIQ API"}

@app.get("/incidents")
def list_incidents():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                i.incident_id,
                i.title,
                i.severity,
                i.status AS incident_status,
                i.service_id,
                i.description,
                i.created_at,
                s.service_name,
                s.status AS service_status,
                s.latency_ms,
                s.error_rate_pct
            FROM incidents AS i
            JOIN services AS s
                ON i.service_id = s.service_id
            ORDER BY
                CASE i.severity
                    WHEN 'SEV1' THEN 1
                    WHEN 'SEV2' THEN 2
                    WHEN 'SEV3' THEN 3
                    WHEN 'SEV4' THEN 4
                    ELSE 5
                END,
                i.created_at DESC
            LIMIT 200
            """
        ).fetchall()

        return {"incidents": [dict(row) for row in rows]}

    finally:
        connection.close()



@app.get("/services")
def list_services():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                service_id,
                service_name,
                status,
                latency_ms,
                error_rate_pct,
                updated_at
            FROM services
            ORDER BY
                CASE status
                    WHEN 'down' THEN 1
                    WHEN 'degraded' THEN 2
                    WHEN 'healthy' THEN 3
                    ELSE 4
                END,
                service_name ASC
            """
        ).fetchall()

        services = [dict(row) for row in rows]

        summary = {
            "total": len(services),
            "healthy": sum(
                service["status"] == "healthy"
                for service in services
            ),
            "degraded": sum(
                service["status"] == "degraded"
                for service in services
            ),
            "down": sum(
                service["status"] == "down"
                for service in services
            ),
        }

        return {
            "summary": summary,
            "services": services,
        }

    finally:
        connection.close()



@app.post("/incidents/investigate")
def investigate_incident(request: InvestigationRequest):
    import uuid

    thread_id = str(uuid.uuid4())
    config = get_config(thread_id)

    try:
        result = get_graph().invoke(
            {"incident_id": request.incident_id.strip()},
            config=config,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation failed: {str(exc)}",
        ) from exc

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    snapshot = get_graph().get_state(config)
    state = snapshot.values

    if result.get("__interrupt__"):
        return {
            "thread_id": thread_id,
            "status": "awaiting_approval",
            "incident_id": state["incident"]["incident_id"],
            "analysis": state["analysis"],
            "evidence": state.get("evidence", {}),
            "proposed_action": state["proposed_action"],
            "warning": (
                "Remediation is simulated only. "
                "No real service will be modified."
            ),
        }

    return {
        "thread_id": thread_id,
        "status": "completed",
        "error": state.get("error"),
    }


@app.post("/incidents/{thread_id}/approval")
def approve_remediation(
    thread_id: str,
    request: ApprovalRequest,
):
    config = get_config(thread_id)
    graph = get_graph()

    snapshot = graph.get_state(config)

    if not snapshot.values:
        raise HTTPException(
            status_code=404,
            detail="Investigation thread not found.",
        )

    if not snapshot.next:
        raise HTTPException(
            status_code=409,
            detail="This workflow is no longer waiting for approval.",
        )

    if "request_approval" not in snapshot.next:
        raise HTTPException(
            status_code=409,
            detail="Workflow is not waiting at the approval step.",
        )

    try:
        result = graph.invoke(
            Command(
                resume={
                    "approved": request.approved,
                    "reason": request.reason,
                }
            ),
            config=config,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not resume workflow: {str(exc)}",
        ) from exc

    return {
        "thread_id": thread_id,
        "status": result.get("execution_result", {}).get(
            "status", "unknown"
        ),
        "execution_result": result.get("execution_result"),
        "verification": result.get("verification"),
        "real_service_modified": False,
    }
