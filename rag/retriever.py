"""
retriever.py
------------
Loads the persisted FAISS index + metadata and exposes a `retrieve()`
function that returns the top-K most similar chunks for a query, along
with a similarity confidence score.

Since embeddings are L2-normalized and the index uses inner product,
similarity scores are cosine similarities in the range [-1, 1] (in
practice mostly [0, 1] for semantically related text).
"""
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field

import faiss

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
from logger import logger


@dataclass
class RetrievedChunk:
    text: str
    source_url: str
    source_domain: str
    source_label: str
    title: str
    score: float


class Retriever:
    """Wraps a FAISS index + metadata for semantic retrieval."""

    def __init__(self):
        self.index = None
        self.metadata = []
        self._load()

    def _load(self):
        index_path = settings.FAISS_INDEX_DIR / "index.faiss"
        meta_path = settings.FAISS_INDEX_DIR / "metadata.json"

        if not index_path.exists() or not meta_path.exists():
            logger.warning(
                f"FAISS index or metadata not found at {settings.FAISS_INDEX_DIR}. "
                "Run the ingestion pipeline (python ingest_pipeline.py) first. "
                "Retriever will operate in empty mode until then."
            )
            self.index = None
            self.metadata = []
            return

        self.index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        logger.info(f"Retriever loaded FAISS index with {self.index.ntotal} vectors "
                    f"and {len(self.metadata)} metadata records.")

    def is_ready(self) -> bool:
        return self.index is not None and self.index.ntotal > 0

    def reload(self):
        """Reload the index from disk (e.g. after re-running ingestion)."""
        self._load()

    def retrieve(self, query: str, top_k: int = None) -> list:
        """Return a list of RetrievedChunk sorted by descending similarity score."""
        if not self.is_ready():
            logger.warning("Retriever called but index is not ready / empty.")
            return []

        top_k = top_k or settings.TOP_K
        from ingestion.embedder import embed_texts
        query_vec = embed_texts([query])

        scores, indices = self.index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            chunk = self.metadata[idx]
            results.append(RetrievedChunk(
                text=chunk["text"],
                source_url=chunk.get("source_url", ""),
                source_domain=chunk.get("source_domain", ""),
                source_label=chunk.get("source_label", chunk.get("source_domain", "")),
                title=chunk.get("title", ""),
                score=float(score),
            ))
        return results

    @staticmethod
    def top_score(results: list) -> float:
        return results[0].score if results else 0.0

    @staticmethod
    def passes_threshold(results: list, threshold: float = None) -> bool:
        threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD
        return bool(results) and Retriever.top_score(results) >= threshold


# Singleton instance used across the app (loaded once at import time)
retriever = Retriever()
