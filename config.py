"""
Central configuration for the BMTC RAG Chatbot.
Loads settings from environment variables / .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root regardless of current working directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_list(env_val: str) -> list:
    return [x.strip() for x in env_val.split(",") if x.strip()]


class Settings:
    # --- Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODELS: list = _get_list(os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-1.5-flash"))
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", 0.2))
    GEMINI_MAX_OUTPUT_TOKENS: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", 1024))

    # --- Embeddings ---
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # --- Retrieval ---
    TOP_K: int = int(os.getenv("TOP_K", 5))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", 0.35))

    # --- Paths ---
    RAW_DATA_DIR: Path = BASE_DIR / os.getenv("RAW_DATA_DIR", "data/raw")
    PROCESSED_DATA_DIR: Path = BASE_DIR / os.getenv("PROCESSED_DATA_DIR", "data/processed")
    FAISS_INDEX_DIR: Path = BASE_DIR / os.getenv("FAISS_INDEX_DIR", "embeddings/faiss_index")

    # --- Scraping ---
    BMTC_URLS: list = _get_list(os.getenv(
        "BMTC_URLS",
        "https://bookmytestcenter.com/,https://center.bookmytestcenter.com/,https://clients.bookmytestcenter.com/"
    ))
    MAX_PAGES_PER_DOMAIN: int = int(os.getenv("MAX_PAGES_PER_DOMAIN", 40))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", 15))

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CORS_ORIGINS: list = _get_list(os.getenv("CORS_ORIGINS", "*"))


settings = Settings()

# Ensure directories exist
for d in [settings.RAW_DATA_DIR, settings.PROCESSED_DATA_DIR, settings.FAISS_INDEX_DIR]:
    d.mkdir(parents=True, exist_ok=True)
