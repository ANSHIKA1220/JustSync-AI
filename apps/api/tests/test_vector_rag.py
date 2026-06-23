"""
test_vector_rag.py
------------------
Tests for the semantic retrieval layer added in the Vector RAG sprint.

Implementation notes
~~~~~~~~~~~~~~~~~~~~
* Uses VectorStoreClient.ephemeral() which creates a temporary directory so
  tests do not touch the production ./vector_store_data/ directory.
* vector_store.reset_client() injects / removes the test client between tests,
  leaving no cross-test global state.
* SQLite is seeded once via the existing seed_database helper.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_journeysync.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AI_PROVIDER"] = "mock"

import pytest  # noqa: E402

from app import vector_store  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument  # noqa: E402
from app.seed import seed_database  # noqa: E402
from app.services import chunk_document, search_knowledge  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

def setup_module():
    """Seed the test database once before any test in this module runs."""
    seed_database(reset=True)


@pytest.fixture(autouse=True)
def isolate_vector_store():
    """Reset the global singleton before and after each test."""
    vector_store.reset_client(None)
    yield
    vector_store.reset_client(None)


# ── Test 1: Indexing success ───────────────────────────────────────────────────

def test_vector_indexing_success():
    """chunk_document() must populate the vector store with embeddings."""
    client = vector_store.VectorStoreClient.ephemeral()
    vector_store.reset_client(client)

    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocument).first()
        assert doc is not None, "Seed database must contain at least one KnowledgeDocument."

        # Re-chunk the document so chunk_document() calls add_chunks().
        chunk_document(db, doc)

        expected_count = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.document_id == doc.id
        ).count()
        assert client.count() >= expected_count > 0, (
            f"Expected {expected_count} vectors in the store, got {client.count()}."
        )
    finally:
        db.close()


# ── Test 2: Semantic retrieval success ────────────────────────────────────────

def test_semantic_retrieval_success():
    """search_knowledge() must return results with provider='chromadb' when the
    vector store is available and the index contains relevant chunks."""
    client = vector_store.VectorStoreClient.ephemeral()

    # Index all documents so the store has content to search.
    db = SessionLocal()
    try:
        docs = db.query(KnowledgeDocument).all()
        assert docs, "Seed database must contain KnowledgeDocuments."
        for doc in docs:
            client.add_chunks(
                doc.id,
                db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all(),
            )

        vector_store.reset_client(client)

        results = search_knowledge(db, "damaged product replacement", limit=3)

        assert results, "Expected at least one result from semantic search."
        for r in results:
            assert r["provider"] == "chromadb", (
                f"Expected provider='chromadb', got {r['provider']!r}."
            )
            assert "chunk_id" in r
            assert "similarity" in r
            assert "retrieved_at" in r
            assert "title" in r
            assert "excerpt" in r
            assert 0.0 <= r["similarity"] <= 1.0, (
                f"similarity must be in [0, 1], got {r['similarity']}."
            )
    finally:
        db.close()


# ── Test 3: Fallback retrieval path ───────────────────────────────────────────

def test_fallback_retrieval_path():
    """When get_client() returns None, search_knowledge() must transparently
    fall back to the keyword/TF-IDF retriever and return results with
    provider='keyword'."""
    # No client injected — get_client() will return None.
    vector_store.reset_client(None)

    db = SessionLocal()
    try:
        results = search_knowledge(db, "damaged replacement", limit=3)

        assert results, "Keyword fallback must return at least one result."
        for r in results:
            assert r["provider"] == "keyword", (
                f"Expected provider='keyword' on fallback, got {r['provider']!r}."
            )
            assert "chunk_id" in r
            assert "similarity" in r
            assert "retrieved_at" in r
            assert "title" in r
            assert "excerpt" in r
            # The legacy 'score' field must still be present for backward compat.
            assert "score" in r
    finally:
        db.close()
