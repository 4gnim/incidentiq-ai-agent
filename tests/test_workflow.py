
from langgraph.checkpoint.memory import InMemorySaver

from incidentiq.workflow import ALLOWED_ACTIONS, build_workflow


def test_unknown_incident_stops_before_analysis():
    graph = build_workflow(
        checkpointer=InMemorySaver(),
    )

    result = graph.invoke(
        {"incident_id": "INC-9999"},
        config={"configurable": {"thread_id": "unknown-incident-test"}},
    )

    assert result["error"] == "Incident not found: INC-9999"
    assert "analysis" not in result
    assert "execution_result" not in result


def test_checkout_action_is_a_simulation():
    action = ALLOWED_ACTIONS["svc-checkout"]

    assert action["action"] == "simulate_rollback"
    assert action["action"].startswith("simulate_")


def test_default_action_is_a_simulation():
    action = ALLOWED_ACTIONS["default"]

    assert action["action"].startswith("simulate_")
