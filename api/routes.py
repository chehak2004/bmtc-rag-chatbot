"""
routes.py
---------
Defines the FastAPI routes for the BMTC RAG Chatbot API.

Endpoints:
    POST /chat            -> main chatbot Q&A endpoint
    GET  /health           -> health check / readiness probe
    POST /admin/reingest    -> re-run ingestion pipeline and hot-reload the index
"""
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parents[1]))

from logger import logger
from rag.chatbot import generate_answer
from rag.retriever import retriever

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")


class ChatResponseModel(BaseModel):
    answer: str
    confidence: float
    sources: list[str]
    language: str
    used_llm: bool


class HealthResponse(BaseModel):
    status: str
    index_ready: bool
    total_vectors: int


@router.post("/chat", response_model=ChatResponseModel)
def chat(request: ChatRequest):
    """
    Main chatbot endpoint.

    Request:  {"question": "How do I register as a test center?"}
    Response: {"answer": "...", "confidence": 0.92, "sources": ["Center Portal"], ...}
    """
    try:
        result = generate_answer(request.question)
        return ChatResponseModel(
            answer=result.answer,
            confidence=result.confidence,
            sources=result.sources,
            language=result.language,
            used_llm=result.used_llm,
        )
    except Exception as e:
        logger.exception(f"Unhandled error in /chat endpoint: {e}")
        # Never let the API crash / 500 with no explanation - degrade gracefully.
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your question. Please try again shortly."
        )


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        index_ready=retriever.is_ready(),
        total_vectors=retriever.index.ntotal if retriever.is_ready() else 0,
    )


@router.post("/admin/reingest")
def reingest():
    """
    Triggers a full re-run of the ingestion pipeline (scrape -> clean -> embed)
    and hot-reloads the FAISS index in memory. Intended for admin/manual use;
    add authentication before exposing this publicly in production.
    """
    try:
        from ingest_pipeline import main as run_pipeline
        run_pipeline()
        retriever.reload()
        return {"status": "success", "message": "Re-ingestion complete and index reloaded."}
    except Exception as e:
        logger.exception(f"Re-ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Re-ingestion failed: {e}")
