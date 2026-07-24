"""
embedder.py
-----------
Generates text embeddings for the processed chunks using `fastembed`
(ONNX Runtime under the hood — no PyTorch), and builds/persists a FAISS
similarity index, along with a metadata sidecar file that maps FAISS row
index -> chunk metadata (text, source url, label, etc).

Why fastembed instead of sentence-transformers/PyTorch:
PyTorch's baseline memory footprint (300-500MB+) is too heavy for small
free-tier hosting (e.g. Render's 512MB free instances), causing OOM restarts
under real request load. fastembed uses quantized ONNX models and typically
runs comfortably in well under 200MB total, at a small cost in raw embedding
speed/accuracy that doesn't meaningfully affect retrieval quality for a
knowledge base of this size.

Artifacts produced:
    embeddings/faiss_index/index.faiss   -> FAISS index (cosine sim via inner product on normalized vectors)
    embeddings/faiss_index/metadata.json -> list aligned with FAISS row order
"""
import json
import sys
from pathlib import Path

import numpy as np
import faiss
from fastembed import TextEmbedding

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
from logger import logger

_model_cache = {}


def get_embedding_model() -> TextEmbedding:
    """Cache the fastembed model so it's only loaded once per process."""
    name = settings.EMBEDDING_MODEL
    if name not in _model_cache:
        logger.info(f"Loading fastembed model: {name}")
        _model_cache[name] = TextEmbedding(model_name=name, threads=1)
    return _model_cache[name]


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # avoid divide-by-zero for empty/degenerate vectors
    return vectors / norms


def embed_texts(texts: list) -> np.ndarray:
    model = get_embedding_model()
    # fastembed returns a generator of np.ndarray, one per input text
    raw = np.array(list(model.embed(texts, batch_size=32)), dtype="float32")
    # normalize ourselves so inner product == cosine similarity (matches
    # how retriever.py / FAISS IndexFlatIP expect vectors to be prepared)
    return _l2_normalize(raw).astype("float32")


def load_chunks() -> list:
    chunks_path = settings.PROCESSED_DATA_DIR / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"{chunks_path} not found. Run ingestion/cleaner.py before embedder.py."
        )
    with open(chunks_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_faiss_index(chunks: list):
    texts = [c["text"] for c in chunks]
    logger.info(f"Embedding {len(texts)} chunks using '{settings.EMBEDDING_MODEL}' (fastembed/ONNX)...")
    embeddings = embed_texts(texts)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized vectors = cosine similarity
    index.add(embeddings)

    logger.info(f"Built FAISS index with {index.ntotal} vectors of dim {dim}")
    return index, embeddings


def save_index(index, chunks: list):
    index_dir = settings.FAISS_INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_dir / "index.faiss"))
    with open(index_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved FAISS index and metadata -> {index_dir}")


def run_embedding_pipeline():
    chunks = load_chunks()
    if not chunks:
        raise ValueError("No chunks found to embed. Run the scraper and cleaner first.")
    index, _ = build_faiss_index(chunks)
    save_index(index, chunks)
    return index, chunks


if __name__ == "__main__":
    run_embedding_pipeline()
