import json

from langchain_core.tools import tool

from incidentiq.knowledge_base import search_runbooks
from incidentiq.tools import(
    get_deployment_history,
    get_incident_details,
    get_incident_timeline,
    get_service_status,
)


@tool
def incident_details(incident_id: str) -> str:
    """Get the incident details and current metrics of its affected service."""
    result = get_incident_details(incident_id)

    if result is None:
        return json.dumps(
            {"error": "Incident not found", "incident_id": incident_id}
        )

    return json.dumps(result, ensure_ascii=False)


@tool
def incident_timeline(incident_id: str, limit: int = 100) -> str:
    """Get chronological logs for an incident. Use this to collect evidence."""
    result = get_incident_timeline(incident_id, limit=limit)

    return json.dumps(result, ensure_ascii=False)


@tool
def deployment_history(service_id: str, limit: int = 10) -> str:
    """Get recent deployments for a service to investigate possible regressions."""
    result = get_deployment_history(service_id, limit=limit)

    return json.dumps(result, ensure_ascii=False)


@tool
def service_status(service_id: str) -> str:
    """Get the recorded health, latency, and error rate of a service."""
    result = get_service_status(service_id)

    if result is None:
        return json.dumps(
            {"error": "Service not found", "service_id": service_id}
        )

    return json.dumps(result, ensure_ascii=False)


@tool
def runbook_search(query: str, k: int = 3) -> str:
    """Search operational runbooks for investigation and safe remediation guidance."""
    results = search_runbooks(query, k=k)

    return json.dumps(results, ensure_ascii=False)


AVAILABLE_TOOLS = [
    incident_details,
    incident_timeline,
    deployment_history,
    service_status,
    runbook_search
]