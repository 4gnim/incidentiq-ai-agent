
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from incidentiq.agent_tools import runbook_search
from incidentiq.config import DATA_DIR
from incidentiq.tools import (
    get_deployment_history,
    get_incident_details,
    get_incident_timeline,
    get_service_status,
)


MODEL_NAME = "qwen3:4b-instruct"


class IncidentState(TypedDict, total=False):
    incident_id: str
    incident: dict[str, Any]
    evidence: dict[str, Any]
    analysis: str
    proposed_action: dict[str, str]
    approval: dict[str, Any]
    execution_result: dict[str, Any]
    verification: dict[str, Any]
    error: str


ALLOWED_ACTIONS = {
    "svc-checkout": {
        "action": "simulate_rollback",
        "description": "Simulate rollback of the latest checkout release",
    },
    "svc-orders-db": {
        "action": "simulate_database_mitigation",
        "description": "Simulate a controlled database mitigation",
    },
    "svc-payment": {
        "action": "simulate_payment_failover",
        "description": "Simulate an approved payment failover procedure",
    },
    "default": {
        "action": "simulate_service_recovery",
        "description": "Simulate a generic service recovery procedure",
    },
}


def build_workflow(model=None, checkpointer=None):
    """Build the incident investigation and approval workflow."""
    llm = model or ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        num_predict=512,
    )

    def load_incident(state: IncidentState) -> dict:
        incident_id = state["incident_id"].strip()
        incident = get_incident_details(incident_id)

        if incident is None:
            return {"error": f"Incident not found: {incident_id}"}

        return {"incident": incident}

    def collect_evidence(state: IncidentState) -> dict:
        incident = state["incident"]
        service_id = incident["service_id"]

        timeline = get_incident_timeline(
            incident["incident_id"],
            limit=100,
        )
        deployments = get_deployment_history(
            service_id,
            limit=10,
        )
        service = get_service_status(service_id)

        query = (
            f"{incident['title']} "
            f"{incident['description']} "
            f"{' '.join(log['message'] for log in timeline[:10])}"
        )
        runbooks = runbook_search.invoke({"query": query, "k": 3})

        import json

        return {
            "evidence": {
                "timeline": timeline,
                "deployments": deployments,
                "service": service,
                "runbooks": json.loads(runbooks),
            }
        }

    def analyze_incident(state: IncidentState) -> dict:
        incident = state["incident"]
        evidence = state["evidence"]

        import json

        prompt_data = {
            "incident": incident,
            "evidence": evidence,
        }

        messages = [
            SystemMessage(
                content=(
                    "You are IncidentIQ, an incident investigation assistant. "
                    "Analyze only the supplied evidence. Separate observed facts "
                    "from hypotheses. Do not claim correlation proves causation. "
                    "Do not claim a service has recovered. Identify missing evidence "
                    "and explain why the proposed action may help. "
                    "No real action is permitted in this workflow."
                )
            ),
            HumanMessage(
                content=(
                    "Analyze this incident and its evidence. "
                    "Summarize observed facts, likely hypotheses, and remaining "
                    "uncertainties in Indonesian. Do not invent metrics.\n\n"
                    + json.dumps(prompt_data, ensure_ascii=False)
                )
            ),
        ]

        response = llm.invoke(messages)
        analysis = response.content

        if not isinstance(analysis, str) or not analysis.strip():
            analysis = "Model did not return a usable analysis."

        service_id = incident["service_id"]
        action = ALLOWED_ACTIONS.get(
            service_id,
            ALLOWED_ACTIONS["default"],
        )

        return {
            "analysis": analysis,
            "proposed_action": dict(action),
        }

    def request_approval(state: IncidentState) -> dict:
        decision = interrupt(
            {
                "type": "human_approval_required",
                "incident_id": state["incident"]["incident_id"],
                "analysis": state["analysis"],
                "proposed_action": state["proposed_action"],
                "warning": (
                    "This is a simulated remediation. "
                    "No real service will be changed."
                ),
            }
        )

        if not isinstance(decision, dict):
            decision = {"approved": False, "reason": "Invalid approval payload"}

        return {"approval": decision}

    def route_after_approval(state: IncidentState) -> str:
        if state.get("approval", {}).get("approved") is True:
            return "simulate_remediation"

        return "rejected"

    def simulate_remediation(state: IncidentState) -> dict:
        # This node only records a simulation result.
        # It does not execute commands or modify real services.
        return {
            "execution_result": {
                "status": "simulated",
                "action": state["proposed_action"]["action"],
                "message": (
                    "Simulation completed. No real service was modified."
                ),
            }
        }

    def verify_simulation(state: IncidentState) -> dict:
        result = state["execution_result"]

        return {
            "verification": {
                "status": "simulation_only",
                "execution_status": result["status"],
                "real_service_health_checked": False,
                "message": (
                    "The workflow verified that the simulation node completed. "
                    "It did not verify recovery of a real service."
                ),
            }
        }

    def rejected(state: IncidentState) -> dict:
        return {
            "execution_result": {
                "status": "rejected",
                "message": "Human approval was not granted; no action was executed.",
            },
            "verification": {
                "status": "not_executed",
                "real_service_health_checked": False,
            },
        }

    builder = StateGraph(IncidentState)

    builder.add_node("load_incident", load_incident)
    builder.add_node("collect_evidence", collect_evidence)
    builder.add_node("analyze_incident", analyze_incident)
    builder.add_node("request_approval", request_approval)
    builder.add_node("simulate_remediation", simulate_remediation)
    builder.add_node("verify_simulation", verify_simulation)
    builder.add_node("rejected", rejected)

    builder.add_edge(START, "load_incident")

    def route_after_load(state: IncidentState) -> str:
        if state.get("error"):
            return "end"
        return "collect_evidence"

    builder.add_conditional_edges(
        "load_incident",
        route_after_load,
        {
            "end": END,
            "collect_evidence": "collect_evidence",
        },
    )

    builder.add_edge("collect_evidence", "analyze_incident")
    builder.add_edge("analyze_incident", "request_approval")

    builder.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "simulate_remediation": "simulate_remediation",
            "rejected": "rejected",
        },
    )

    builder.add_edge("simulate_remediation", "verify_simulation")
    builder.add_edge("verify_simulation", END)
    builder.add_edge("rejected", END)

    return builder.compile(
        checkpointer=checkpointer or InMemorySaver()
    )
