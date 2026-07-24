"""
chatbot.py
----------
Orchestrates the RAG pipeline end-to-end for a single user turn:

    1. Detect language (English / Hindi supported explicitly).
    2. Retrieve top-K relevant chunks from FAISS via retriever.py.
    3. If similarity confidence is too low -> return "not found" message
       (translated to the user's language if needed).
    4. Otherwise, build a context-grounded prompt and call Gemini.
    5. If Gemini fails (quota, network, API error) -> fall back to
       returning the retrieved context directly, without crashing.

Exposes:
    generate_answer(question: str) -> ChatResponse
"""
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
from logger import logger
from rag.retriever import retriever, RetrievedChunk
from rag.prompts import (
    build_qa_prompt,
    NO_CONTEXT_MESSAGE_EN,
    NO_CONTEXT_MESSAGE_HI,
    GEMINI_FAILURE_PREFIX_EN,
    GEMINI_FAILURE_PREFIX_HI,
)

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0  # deterministic language detection
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    _TRANSLATOR_AVAILABLE = False

try:
    from google import genai
    _GEMINI_SDK_AVAILABLE = True
except ImportError:
    _GEMINI_SDK_AVAILABLE = False


@dataclass
class ChatResponse:
    answer: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    language: str = "en"
    used_llm: bool = True
    error: str = None


# ---------------------------------------------------------------------------
# Language detection & translation helpers
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """Returns 'hi' for Hindi, 'en' for anything else / detection failure."""
    if not text.strip():
        return "en"
    if _LANGDETECT_AVAILABLE:
        try:
            lang = detect(text)
            return "hi" if lang == "hi" else "en"
        except Exception:
            pass
    # crude fallback: check for Devanagari unicode block
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "hi"
    return "en"


def translate_text(text: str, target_lang: str) -> str:
    """Best-effort translation; returns original text if translation unavailable/fails."""
    if not _TRANSLATOR_AVAILABLE:
        return text
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        logger.warning(f"Translation failed ({target_lang}): {e}")
        return text


# ---------------------------------------------------------------------------
# Gemini integration
# ---------------------------------------------------------------------------

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if not _GEMINI_SDK_AVAILABLE:
        raise RuntimeError("google-genai package not installed.")
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is not configured in .env")
    _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def call_gemini(prompt: str) -> str:
    """
    Calls Gemini with a fallback chain across models listed in settings.GEMINI_MODELS
    (e.g. gemini-2.5-flash -> gemini-1.5-flash -> ...). Raises the last exception if
    every model in the chain fails, so the caller can degrade gracefully.
    """
    client = _get_gemini_client()

    from google.genai import types
    generation_config = types.GenerateContentConfig(
        temperature=settings.GEMINI_TEMPERATURE,
        max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
    )

    last_error = None
    for model_name in settings.GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )
            text = getattr(response, "text", None)
            if text and text.strip():
                logger.info(f"Gemini call succeeded using model '{model_name}'")
                return text.strip()
            raise ValueError(f"Empty response from model {model_name}")
        except Exception as e:
            logger.warning(f"Gemini model '{model_name}' failed: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def build_context(chunks: List[RetrievedChunk], max_chars: int = 6000) -> str:
    parts = []
    total_len = 0
    for c in chunks:
        block = f"[Source: {c.source_label} | {c.title}]\n{c.text}\n"
        if total_len + len(block) > max_chars:
            break
        parts.append(block)
        total_len += len(block)
    return "\n---\n".join(parts)


def unique_sources(chunks: List[RetrievedChunk]) -> List[str]:
    seen = []
    for c in chunks:
        if c.source_label not in seen:
            seen.append(c.source_label)
    return seen


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def generate_answer(question: str) -> ChatResponse:
    start_time = time.time()
    question = (question or "").strip()

    if not question:
        return ChatResponse(
            answer="Please type a question so I can help you.",
            confidence=0.0,
            sources=[],
            language="en",
            used_llm=False,
        )

    user_lang = detect_language(question)
    logger.info(f"Incoming question (lang={user_lang}): {question}")

    # Retrieve relevant chunks (retrieval always happens in English-embedding space;
    # translating the query to English first improves retrieval quality for Hindi input)
    retrieval_query = question
    if user_lang == "hi":
        retrieval_query = translate_text(question, target_lang="en")

    results = retriever.retrieve(retrieval_query, top_k=settings.TOP_K)
    confidence = retriever.top_score(results)

    if not retriever.passes_threshold(results):
        logger.info(f"Confidence {confidence:.3f} below threshold "
                    f"{settings.SIMILARITY_THRESHOLD}. Returning 'not found' message.")
        message = NO_CONTEXT_MESSAGE_HI if user_lang == "hi" else NO_CONTEXT_MESSAGE_EN
        return ChatResponse(
            answer=message,
            confidence=round(confidence, 3),
            sources=[],
            language=user_lang,
            used_llm=False,
        )

    context = build_context(results)
    sources = unique_sources(results)

    # Ask Gemini in English (it handles Hindi fine too, but we pass original
    # question so the model can naturally respond in the same language per prompt rules)
    prompt = build_qa_prompt(context=context, question=question)

    try:
        answer = call_gemini(prompt)
        used_llm = True
        error = None
    except Exception as e:
        logger.error(f"Gemini generation failed, falling back to raw context: {e}")
        prefix = GEMINI_FAILURE_PREFIX_HI if user_lang == "hi" else GEMINI_FAILURE_PREFIX_EN
        # Fallback: return the most relevant retrieved snippet(s) directly, never crash.
        fallback_text = results[0].text
        if user_lang == "hi":
            fallback_text = translate_text(fallback_text, target_lang="hi")
        answer = prefix + fallback_text
        used_llm = False
        error = str(e)

    elapsed = time.time() - start_time
    logger.info(f"Answered in {elapsed:.2f}s | confidence={confidence:.3f} | "
                f"used_llm={used_llm} | sources={sources}")

    return ChatResponse(
        answer=answer,
        confidence=round(confidence, 3),
        sources=sources,
        language=user_lang,
        used_llm=used_llm,
        error=error,
    )
