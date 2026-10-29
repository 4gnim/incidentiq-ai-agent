from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from incidentiq.config import DATA_DIR, RUNBOOK_DIR

CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION_NAME = "incidentiq_runbooks"
EMBEDDING_MODEL = "nomic-embed-text"


def load_runbooks() -> list[Document]:
    """Load Markdown runbooks as LangChain documents."""
    documents = []

    for path in sorted(RUNBOOK_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8").strip()

        if not content:
            continue

        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": path.name,
                    "document_type": "runbook",
                },
            )
        )

    return documents


def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBEDDING_MODEL)


def rebuild_knowledge_base() -> int:
    """Rebuild the persistent Chroma collection from current runbooks."""
    documents = load_runbooks()

    if not documents:
        raise ValueError(
            f"No Markdown runbooks found in {RUNBOOK_DIR}"
        )

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )

    # Replace old indexed content to prevent duplicate chunks/documents.
    vector_store.reset_collection()
    vector_store.add_documents(documents)

    return len(documents)


def search_runbooks(
        query: str,
        k: int = 3,
) -> list[dict]:
    """Find relevant runbooks for an incident investigation."""
    if not query.strip():
        raise ValueError("Search query must not be empty.")

    if not 1 <= k <= 10:
        raise ValueError("k must be between 1 and 10.")

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )

    results = vector_store.similarity_search_with_score(
        query,
        k=k,
    )

    return [
        {
            "content": document.page_content,
            "source": document.metadata.get("source", "unknown"),
            "distance": float(distance),
        }
        for document, distance in results
    ]


if __name__ == "__main__":
    count = rebuild_knowledge_base()
    print(f"Indexed {count} runbooks.")