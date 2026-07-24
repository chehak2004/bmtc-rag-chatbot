"""
cleaner.py
----------
Loads raw scraped JSON pages, cleans the text (removes extra whitespace,
boilerplate, non-informative lines), and splits it into overlapping chunks
suitable for embedding.

Output: data/processed/chunks.json -> a list of chunk dicts:
    {
        "id": "center_bookmytestcenter_com_ab12cd34_0",
        "text": "...",
        "source_url": "https://center.bookmytestcenter.com/",
        "source_domain": "center.bookmytestcenter.com",
        "title": "BMTC Center Portal - Overview"
    }
"""
import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
from logger import logger

# URL substrings that mark a page as legal/boilerplate rather than product
# content. These pages get scraped (useful to have on file) but are excluded
# from the chunks that feed the retriever/LLM, since they carry no
# information about what the product actually does and can cause the model
# to answer feature questions using irrelevant "evidence".
BOILERPLATE_URL_PATTERNS = [
    "privacy-policy",
    "terms-condition",
    "terms-of-service",
    "cookie-policy",
    "/cms/",
]


def is_boilerplate_page(url: str) -> bool:
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in BOILERPLATE_URL_PATTERNS)

# Human readable labels used in API responses / citations
DOMAIN_LABELS = {
    "bookmytestcenter.com": "Main Website",
    "center.bookmytestcenter.com": "Center Portal",
    "clients.bookmytestcenter.com": "Client Portal",
}


def domain_to_label(domain: str) -> str:
    return DOMAIN_LABELS.get(domain, domain)


def clean_text(text: str) -> str:
    """Normalize whitespace and drop very short / noisy lines."""
    text = text.replace("\xa0", " ")
    lines = [ln.strip() for ln in text.split("\n")]
    cleaned_lines = []
    for ln in lines:
        if not ln:
            continue
        if len(ln) < 3:
            continue
        # collapse repeated whitespace
        ln = re.sub(r"\s+", " ", ln)
        cleaned_lines.append(ln)
    return "\n".join(cleaned_lines)


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list:
    """
    Splits text into word-based chunks with overlap, trying to break on
    sentence boundaries where possible for more coherent chunks.

    chunk_size / overlap are measured in words.
    """
    # Split into sentences first for cleaner boundaries
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    chunks = []
    current_words = []

    for sentence in sentences:
        sentence_words = sentence.split()
        if not sentence_words:
            continue
        if len(current_words) + len(sentence_words) > chunk_size and current_words:
            chunks.append(" ".join(current_words))
            # start new chunk with overlap from the end of the previous chunk
            overlap_words = current_words[-overlap:] if overlap < len(current_words) else current_words
            current_words = overlap_words + sentence_words
        else:
            current_words.extend(sentence_words)

    if current_words:
        chunks.append(" ".join(current_words))

    # Filter out trivially small chunks
    return [c.strip() for c in chunks if len(c.split()) >= 15]


def load_raw_pages() -> list:
    raw_dir = settings.RAW_DATA_DIR
    pages = []
    for path in raw_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                pages.append(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
    logger.info(f"Loaded {len(pages)} raw pages from {raw_dir}")
    return pages


def build_chunks(chunk_size: int = 400, overlap: int = 60) -> list:
    pages = load_raw_pages()
    all_chunks = []

    for page in pages:
        if is_boilerplate_page(page.get("url", "")):
            logger.info(f"Skipping boilerplate page (not product content): {page.get('url')}")
            continue

        cleaned = clean_text(page.get("text", ""))
        if not cleaned:
            continue

        page_chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)
        base_id = re.sub(r"[^a-zA-Z0-9]+", "_", page["url"])[:60]

        for i, chunk in enumerate(page_chunks):
            all_chunks.append({
                "id": f"{base_id}_{i}",
                "text": chunk,
                "source_url": page.get("url", ""),
                "source_domain": page.get("source_domain", ""),
                "source_label": domain_to_label(page.get("source_domain", "")),
                "title": page.get("title", ""),
            })

    logger.info(f"Built {len(all_chunks)} chunks from {len(pages)} pages")
    return all_chunks


def save_chunks(chunks: list):
    out_path = settings.PROCESSED_DATA_DIR / "chunks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(chunks)} chunks -> {out_path}")


def run_cleaning(chunk_size: int = 400, overlap: int = 60):
    chunks = build_chunks(chunk_size=chunk_size, overlap=overlap)
    save_chunks(chunks)
    return chunks


if __name__ == "__main__":
    run_cleaning()
