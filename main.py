"""
main.py
-------
FastAPI application entry point for the BMTC RAG Chatbot.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
or simply:
    python main.py
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from logger import logger
from api.routes import router as api_router

app = FastAPI(
    title="BMTC RAG Chatbot API",
    description="Retrieval-Augmented Generation chatbot for BookMyTestCenter (BMTC) portals.",
    version="1.0.0",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global exception handler: never let an unhandled error crash the process ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

# --- API routes ---
# Mounted at root so the primary endpoint is exactly POST /chat (per spec),
# with /health and /admin/reingest alongside it. Registered before the static
# file mount below so these exact paths take priority over the SPA catch-all.
app.include_router(api_router, tags=["chat"])

# --- Serve frontend static files at root ---
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("BMTC RAG Chatbot API starting up...")
    logger.info(f"Gemini models configured: {settings.GEMINI_MODELS}")
    logger.info(f"Embedding model: {settings.EMBEDDING_MODEL}")
    logger.info(f"Similarity threshold: {settings.SIMILARITY_THRESHOLD} | Top-K: {settings.TOP_K}")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
