
import pytest

from incidentiq.agent_tools import AVAILABLE_TOOLS
from incidentiq.knowledge_base import load_runbooks, search_runbooks


def test_load_runbooks_finds_markdown_documents():
    documents = load_runbooks()

    assert len(documents) >= 3
    assert all(document.page_content.strip() for document in documents)

    sources = {
        document.metadata["source"]
        for document in documents
    }

    assert "01-checkout-http-500.md" in sources
    assert "02-database-latency.md" in sources
    assert "03-payment-timeouts.md" in sources


def test_runbook_search_rejects_empty_query():
    with pytest.raises(ValueError):
        search_runbooks("   ")


def test_runbook_search_rejects_invalid_k():
    with pytest.raises(ValueError):
        search_runbooks("database latency", k=0)


def test_all_investigation_tools_are_registered():
    tool_names = {item.name for item in AVAILABLE_TOOLS}

    assert tool_names == {
        "incident_details",
        "incident_timeline",
        "deployment_history",
        "service_status",
        "runbook_search",
    }
