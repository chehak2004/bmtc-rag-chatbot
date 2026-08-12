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
       returning the retrieved context directly, without crashing, and
       without revealing to the customer that a fallback occurred (see
       prompts.py — GEMINI_FAILURE_PREFIX is intentionally empty).

Exposes:
    generate_answer(question: str) -> ChatResponse
"""
import sys
import time
import re
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


def _has_markdown_structure(text: str) -> bool:
    """Detects whether text already has bullet/numbered/bold markdown
    structure on its own lines (as our curated seed content now does), in
    which case it should NOT be re-flowed through sentence-based
    paragraphizing — doing so would merge separate bullet/numbered lines
    together and destroy the structure. Plain-prose scraped content (which
    has no such structure) still benefits from paragraphizing."""
    for line in text.split("\n"):
        line = line.strip()
        if re.match(r"^\*\s+", line) or re.match(r"^\d+\.\s+", line):
            return True
    return False


# ---------------------------------------------------------------------------
# Conversational intent shortcuts (greetings, thanks, farewells, "who are
# you"-style meta questions). These are handled directly, without touching
# retrieval/Gemini at all — they don't need knowledge-base grounding, and
# routing them through the normal RAG pipeline would either produce a bad
# robotic "couldn't find this in the knowledge base" refusal (since a
# greeting has no meaningful similarity to any BMTC content chunk) or waste
# an LLM call on something a simple pattern match handles instantly and
# reliably.
# ---------------------------------------------------------------------------
_GREETING_PATTERNS = [
    r"^h(i|ey|ello)+!?$", r"^good\s*(morning|afternoon|evening)!?$",
    r"^नमस्ते!?$", r"^नमस्कार!?$", r"^हैलो!?$",
]
_THANKS_PATTERNS = [
    r"^thanks?( you)?!?$", r"^thank\s*you( so much| a lot)?!?$", r"^(ty|thx)!?$",
    r"^धन्यवाद!?$", r"^शुक्रिया!?$",
]
_FAREWELL_PATTERNS = [
    r"^bye!?$", r"^goodbye!?$", r"^see\s*you!?$", r"^अलविदा!?$", r"^बाय!?$",
]
_ABOUT_BOT_PATTERNS = [
    r"^who are you\??$", r"^what are you\??$", r"^what can you (do|help with)\??$",
    r"^what do you do\??$", r"^tum kaun ho\??$", r"^आप कौन हैं\??$", r"^आप क्या कर सकते हैं\??$",
]

_CANNED_RESPONSES = {
    "greeting": {
        "en": "Hello! I'm the BMTC Assistant. I can help with candidate registration, "
              "the Center Portal, the Client Portal, bookings, and general FAQs. What "
              "would you like to know?",
        "hi": "नमस्ते! मैं BMTC Assistant हूँ। मैं उम्मीदवार पंजीकरण, सेंटर पोर्टल, क्लाइंट पोर्टल, "
              "बुकिंग और सामान्य प्रश्नों में मदद कर सकता हूँ। आप क्या जानना चाहते हैं?",
    },
    "thanks": {
        "en": "You're welcome! Let me know if there's anything else you'd like to know about BMTC.",
        "hi": "आपका स्वागत है! अगर BMTC के बारे में कुछ और जानना हो तो बताइए।",
    },
    "farewell": {
        "en": "Goodbye! Feel free to come back anytime you have a question about BMTC.",
        "hi": "अलविदा! जब भी BMTC से जुड़ा कोई सवाल हो, आप कभी भी वापस आ सकते हैं।",
    },
    "about_bot": {
        "en": "I'm the BMTC Assistant — I answer questions about BookMyTestCenter's "
              "candidate registration, the Center Portal, the Client Portal, exam "
              "bookings, and general FAQs, based on official BMTC documentation.",
        "hi": "मैं BMTC Assistant हूँ — मैं BookMyTestCenter के उम्मीदवार पंजीकरण, सेंटर पोर्टल, "
              "क्लाइंट पोर्टल, परीक्षा बुकिंग और सामान्य प्रश्नों के बारे में आधिकारिक BMTC "
              "दस्तावेज़ों के आधार पर जवाब देता हूँ।",
    },
}


def _detect_conversational_intent(question: str) -> str:
    """Returns 'greeting' / 'thanks' / 'farewell' / 'about_bot' if the
    message matches one of those patterns exactly (after trimming/lowering
    for the English patterns), else None. Intentionally conservative —
    only matches short, unambiguous conversational messages, never partial
    matches within a longer real question, so it can't accidentally
    swallow an actual BMTC question that happens to start with "hi" etc."""
    normalized = question.strip()
    normalized_lower = normalized.lower()

    for pattern in _GREETING_PATTERNS:
        if re.match(pattern, normalized_lower) or re.match(pattern, normalized):
            return "greeting"
    for pattern in _THANKS_PATTERNS:
        if re.match(pattern, normalized_lower) or re.match(pattern, normalized):
            return "thanks"
    for pattern in _FAREWELL_PATTERNS:
        if re.match(pattern, normalized_lower) or re.match(pattern, normalized):
            return "farewell"
    for pattern in _ABOUT_BOT_PATTERNS:
        if re.match(pattern, normalized_lower) or re.match(pattern, normalized):
            return "about_bot"
    return None


def _paragraphize(text: str, sentences_per_paragraph: int = 2) -> str:
    """
    Breaks a dense block of prose into readable paragraphs by grouping a few
    sentences at a time. Used specifically for fallback answers (raw
    retrieved context) that have no inherent paragraph/list structure of
    their own — typically plain-prose scraped content, as opposed to our
    curated seed content, which already carries real markdown structure and
    is left untouched (see _has_markdown_structure).
    """
    text = text.strip()
    if not text:
        return text

    if _has_markdown_structure(text):
        return text

    # Split on sentence-ending punctuation (., !, ?, or Hindi danda ।)
    # followed by whitespace, while keeping the punctuation attached.
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    paragraphs = []
    for i in range(0, len(sentences), sentences_per_paragraph):
        paragraphs.append(" ".join(sentences[i:i + sentences_per_paragraph]))

    return "\n\n".join(paragraphs)


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

    # Conversational shortcuts (greetings, thanks, farewells, "who are you")
    # bypass retrieval/Gemini entirely — see _detect_conversational_intent.
    intent = _detect_conversational_intent(question)
    if intent:
        logger.info(f"Detected conversational intent: {intent}")
        canned = _CANNED_RESPONSES[intent]
        answer = canned.get(user_lang, canned["en"])
        return ChatResponse(
            answer=answer,
            confidence=1.0,
            sources=[],
            language=user_lang,
            used_llm=False,
        )

    # Retrieve relevant chunks (retrieval always happens in English-embedding space;
    # translating the query to English first improves retrieval quality for Hindi input)
    retrieval_query = question
    if user_lang == "hi":
        retrieval_query = translate_text(question, target_lang="en")

    results = retriever.retrieve(retrieval_query, top_k=settings.TOP_K)
    confidence = retriever.top_score(results)

    # --- Tier 1: confidence too low even for a clarifying attempt -> this
    # is genuinely out of scope (e.g. "what is the capital of France").
    # Never call the LLM here — hardcoded refusal keeps the
    # anti-hallucination guarantee airtight for clearly unrelated questions.
    if confidence < settings.CLARIFICATION_THRESHOLD or not results:
        logger.info(f"Confidence {confidence:.3f} below clarification floor "
                    f"{settings.CLARIFICATION_THRESHOLD}. Returning 'not found' message.")
        message = NO_CONTEXT_MESSAGE_HI if user_lang == "hi" else NO_CONTEXT_MESSAGE_EN
        return ChatResponse(
            answer=message,
            confidence=round(confidence, 3),
            sources=[],
            language=user_lang,
            used_llm=False,
        )

    # --- Tier 2 & 3: confidence is at least plausible. Whether it's a
    # confident direct answer (Tier 3, >= SIMILARITY_THRESHOLD) or an
    # ambiguous/underspecified question that's still plausibly BMTC-related
    # (Tier 2, between the two thresholds), both go to Gemini with the same
    # context — the prompt itself (see prompts.py rule 5) instructs the
    # model to ask a clarifying question rather than guess when the
    # question is vague, so we don't need separate prompt paths here.
    is_ambiguous_zone = confidence < settings.SIMILARITY_THRESHOLD
    if is_ambiguous_zone:
        logger.info(f"Confidence {confidence:.3f} in ambiguous zone "
                    f"[{settings.CLARIFICATION_THRESHOLD}, {settings.SIMILARITY_THRESHOLD}) — "
                    f"asking Gemini to clarify rather than refusing outright.")

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
        # Fallback: return the most relevant retrieved snippet directly, never
        # crash, and never reveal the internal failure to the customer (the
        # prefix is intentionally empty — see prompts.py). Break the raw
        # context into paragraphs since it has no inherent structure the way
        # a normal Gemini-authored answer would.
        fallback_text = results[0].text
        if user_lang == "hi":
            fallback_text = translate_text(fallback_text, target_lang="hi")
        fallback_text = _paragraphize(fallback_text)
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
