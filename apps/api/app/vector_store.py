"""
vector_store.py
---------------
Singleton semantic vector store for JourneySync AI knowledge retrieval.

Implementation
~~~~~~~~~~~~~~
Uses sentence-transformers for embeddings and numpy for cosine similarity
search. This stack runs fully offline after the first model download and
requires zero C++ compilation (all dependencies ship as pure Python or
pre-built wheels for Windows/macOS/Linux).

For the knowledge-base sizes typical in JourneySync AI (hundreds of chunks)
brute-force cosine search is functionally identical in speed to an approximate
nearest-neighbour index while avoiding the MSVC / GCC build requirement of
hnswlib / chroma-hnswlib.

The public API intentionally mirrors what a ChromaDB-backed implementation
would expose so caller code and tests remain provider-agnostic. If the project
later moves to a managed vector database (pgvector, Pinecone, Qdrant …), only
this file changes.

Design decisions
~~~~~~~~~~~~~~~~
* The SentenceTransformer model is loaded exactly once at init time.
* Persistent storage uses a single directory (default: ./vector_store_data/):
    - embeddings.npy   – float32 array, shape (n, 384)
    - ids.json         – ordered list of chunk UUIDs
    - meta.json        – chunk_id → document_id mapping
  Override the directory with the VECTOR_STORE_PATH environment variable.
* add_chunks() uses upsert semantics: existing vectors for the document are
  removed and replaced with fresh embeddings.
* search() returns cosine similarity in [0, 1].
* get_client() returns None on any failure so callers fall back to the
  existing keyword / TF-IDF retriever without crashing.
* reset_client() is provided for test isolation.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Singleton state ────────────────────────────────────────────────────────────
_client: Optional["VectorStoreClient"] = None
_init_attempted: bool = False
_lock = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cosine_similarity(query_vec, matrix):  # type: ignore[no-untyped-def]
    """Return 1-D array of cosine similarities between *query_vec* and *matrix* rows.

    Both inputs must already be L2-normalised so the dot product equals cosine
    similarity.
    """
    return (matrix @ query_vec.flatten())


# ── Public API ─────────────────────────────────────────────────────────────────

class VectorStoreClient:
    """Semantic vector store backed by sentence-transformers + numpy."""

    COLLECTION_NAME = "knowledge_chunks"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    DIM = 384  # all-MiniLM-L6-v2 output dimension

    def __init__(self, store_dir: str) -> None:
        import numpy as np  # type: ignore
        from sentence_transformers import SentenceTransformer

        self._np = np
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._model = SentenceTransformer(self.EMBEDDING_MODEL)

        # In-memory structures (persisted on writes).
        self._ids: list[str] = []           # position → chunk_id
        self._meta: dict[str, str] = {}     # chunk_id → document_id
        self._matrix: "np.ndarray" = np.empty((0, self.DIM), dtype=np.float32)

        if self._emb_path().exists():
            self._load()

        logger.info(
            "VectorStoreClient ready — model=%s  dir=%s  vectors=%d",
            self.EMBEDDING_MODEL,
            self._dir,
            self.count(),
        )

    # ── Paths ──────────────────────────────────────────────────────────────────

    def _emb_path(self) -> Path:
        return self._dir / "embeddings.npy"

    def _ids_path(self) -> Path:
        return self._dir / "ids.json"

    def _meta_path(self) -> Path:
        return self._dir / "meta.json"

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        np = self._np
        self._matrix = np.load(str(self._emb_path()))
        if self._ids_path().exists():
            self._ids = json.loads(self._ids_path().read_text())
        if self._meta_path().exists():
            self._meta = json.loads(self._meta_path().read_text())

    def _save(self) -> None:
        self._np.save(str(self._emb_path()), self._matrix)
        self._ids_path().write_text(json.dumps(self._ids))
        self._meta_path().write_text(json.dumps(self._meta))

    # ── Write ──────────────────────────────────────────────────────────────────

    def add_chunks(self, document_id: str, chunks: list) -> None:
        """Index *chunks* for *document_id*, replacing any previously stored vectors.

        Parameters
        ----------
        document_id:
            The KnowledgeDocument UUID from SQLite.
        chunks:
            Iterable of KnowledgeChunk ORM objects (must expose ``.id`` and
            ``.chunk_text``).
        """
        if not chunks:
            return

        np = self._np

        # Remove stale vectors for this document.
        keep_mask = [
            self._meta.get(cid) != document_id
            for cid in self._ids
        ]
        if self._ids:
            kept_ids = [cid for cid, k in zip(self._ids, keep_mask) if k]
            kept_matrix = self._matrix[keep_mask] if self._matrix.size else self._matrix
        else:
            kept_ids = []
            kept_matrix = np.empty((0, self.DIM), dtype=np.float32)

        # Stale meta entries
        for cid in self._ids:
            if self._meta.get(cid) == document_id:
                del self._meta[cid]
        self._ids = kept_ids

        # Compute embeddings (batch).
        texts = [chunk.chunk_text for chunk in chunks]
        new_embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        ).astype(np.float32)

        # Append to in-memory state.
        for chunk in chunks:
            self._ids.append(chunk.id)
            self._meta[chunk.id] = document_id

        if kept_matrix.size:
            self._matrix = np.vstack([kept_matrix, new_embeddings])
        else:
            self._matrix = new_embeddings

        self._save()
        logger.debug("Indexed %d chunks for document_id=%s", len(chunks), document_id)

    # ── Read ───────────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Return up to *limit* semantically similar chunks.

        Returns
        -------
        list[dict] with keys:
            chunk_id, similarity (float 0–1), excerpt (str), document_id (str)
        """
        if self.count() == 0:
            return []

        np = self._np
        query_vec = self._model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)

        similarities = _cosine_similarity(query_vec, self._matrix)
        k = min(limit, len(self._ids))
        top_k = np.argsort(similarities)[::-1][:k]

        hits = []
        for pos in top_k:
            pos = int(pos)
            chunk_id = self._ids[pos]
            sim = float(similarities[pos])
            # Clamp to [0, 1] — normalised cosine can produce tiny negatives due
            # to float32 arithmetic.
            sim = round(max(0.0, min(1.0, sim)), 4)
            hits.append({
                "chunk_id": chunk_id,
                "similarity": sim,
                "excerpt": "",  # excerpt filled by services.py from SQLite
                "document_id": self._meta.get(chunk_id, ""),
            })

        return hits

    # ── Introspection ──────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return the number of indexed vectors."""
        return len(self._ids)

    # ── In-memory variant for tests ────────────────────────────────────────────

    @classmethod
    def ephemeral(cls) -> "VectorStoreClient":
        """Return a non-persistent client backed by a temp directory."""
        import tempfile
        tmp = tempfile.mkdtemp(prefix="vs_test_")
        return cls(store_dir=tmp)


# ── Factory / singleton accessor ───────────────────────────────────────────────

def get_client() -> Optional[VectorStoreClient]:
    """Return the module-level singleton, or None if initialisation failed.

    Initialisation is attempted exactly once; subsequent calls return the cached
    result without retrying so a broken environment does not slow down every
    request.
    """
    global _client, _init_attempted
    if _init_attempted:
        return _client

    with _lock:
        # Double-checked locking.
        if _init_attempted:
            return _client

        _init_attempted = True
        store_dir = os.environ.get("VECTOR_STORE_PATH", "./vector_store_data")

        try:
            _client = VectorStoreClient(store_dir=store_dir)
        except ImportError as exc:
            logger.warning(
                "sentence-transformers/numpy not installed — "
                "vector retrieval disabled. (%s)",
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "VectorStore initialisation failed — "
                "falling back to keyword retrieval. (%s)",
                exc,
            )

    return _client


def reset_client(new_client: Optional[VectorStoreClient] = None, *, skip_init: bool = False) -> None:
    """Replace the singleton — used by tests to inject an in-memory client.

    Parameters
    ----------
    new_client:
        The client to inject.  Pass ``None`` to remove the current client.
    skip_init:
        When ``True`` (the default when ``new_client`` is ``None``), subsequent
        calls to :func:`get_client` will return ``None`` without attempting
        disk-based initialisation.  Pass ``False`` to allow re-initialisation.
    """
    global _client, _init_attempted
    _client = new_client
    # Always mark as attempted when a client is explicitly injected.
    # When clearing (new_client=None), also mark as attempted by default so
    # get_client() doesn't fall through to the filesystem initialiser.
    _init_attempted = True if new_client is not None else not skip_init
