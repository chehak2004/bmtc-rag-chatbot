"""
scraper.py
----------
Crawls the BMTC websites (main site, center portal, client portal),
extracts readable text content from each page, and stores raw page
data as JSON files under data/raw/.

Design notes:
- Uses BFS crawling restricted to the same domain as each seed URL.
- Skips binary assets (images, pdfs handled separately if needed), scripts,
  styles, nav/footer boilerplate.
- Polite crawling: small delay between requests, timeout, and a max page cap
  per domain (configurable via .env) to avoid hammering the site.
"""
import json
import time
import hashlib
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
from logger import logger

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BMTC-RAG-Bot/1.0"
    )
}

# Tags whose content is boilerplate / navigation noise and should be dropped
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header", "form"]

# Common boilerplate phrases to filter (case-insensitive substring match)
NOISE_PHRASES = [
    "all rights reserved",
    "cookie policy",
    "privacy policy",
    "terms of service",
    "follow us on",
]


def _same_domain(url: str, root: str) -> bool:
    return urlparse(url).netloc == urlparse(root).netloc


def _clean_url(url: str) -> str:
    """Strip fragments/query noise that create duplicate pages."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def extract_text_from_html(html: str) -> dict:
    """Extract title + meaningful body text from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.get_text(strip=True) if soup.title else ""

    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    # Prefer <main> or <article> if present, else fall back to <body>
    main_content = soup.find("main") or soup.find("article") or soup.body or soup

    text_blocks = []
    for el in main_content.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "div"]):
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 2:
            continue
        lower = text.lower()
        if any(phrase in lower for phrase in NOISE_PHRASES):
            continue
        text_blocks.append(text)

    # De-duplicate consecutive repeated lines (common with nested divs)
    deduped = []
    seen_recent = set()
    for block in text_blocks:
        key = block[:120]
        if key in seen_recent:
            continue
        seen_recent.add(key)
        deduped.append(block)

    full_text = "\n".join(deduped)
    return {"title": title, "text": full_text}


def discover_links(soup: BeautifulSoup, current_url: str, root: str) -> list:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full_url = urljoin(current_url, href)
        full_url = _clean_url(full_url)
        if _same_domain(full_url, root) and full_url.startswith("http"):
            links.append(full_url)
    return links


def crawl_site(seed_url: str, max_pages: int = 40, timeout: int = 15, delay: float = 0.5) -> list:
    """BFS crawl of a single domain starting at seed_url. Returns list of page dicts."""
    visited = set()
    queue = deque([_clean_url(seed_url)])
    pages = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        extracted = extract_text_from_html(resp.text)

        if extracted["text"].strip():
            pages.append({
                "url": url,
                "title": extracted["title"],
                "text": extracted["text"],
                "source_domain": urlparse(seed_url).netloc,
            })
            logger.info(f"Scraped ({len(pages)}): {url}  [{len(extracted['text'])} chars]")

        for link in discover_links(soup, url, seed_url):
            if link not in visited:
                queue.append(link)

        time.sleep(delay)

    return pages


def save_raw_pages(pages: list, domain_label: str):
    """Save scraped pages as individual JSON files keyed by URL hash."""
    out_dir = settings.RAW_DATA_DIR
    for page in pages:
        url_hash = hashlib.md5(page["url"].encode()).hexdigest()[:12]
        out_path = out_dir / f"{domain_label}_{url_hash}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(page, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(pages)} raw pages for {domain_label} -> {out_dir}")


def run_scraper(use_seed_fallback: bool = True):
    """Entry point: crawl every seed URL configured in .env and persist raw pages.

    If a domain returns zero pages (e.g. network blocked, site unreachable,
    robots restrictions), and use_seed_fallback is True, we fall back to the
    curated seed content in seed_content.py for that domain so the pipeline
    still produces a usable knowledge base.
    """
    all_pages = []

    seed_by_domain = {}
    if use_seed_fallback:
        from ingestion.seed_content import get_seed_pages
        for p in get_seed_pages():
            seed_by_domain.setdefault(p["source_domain"], []).append(p)

    for seed in settings.BMTC_URLS:
        domain_label = urlparse(seed).netloc.replace(".", "_")
        domain_key = urlparse(seed).netloc
        logger.info(f"Starting crawl for {seed} (domain label: {domain_label})")
        pages = crawl_site(
            seed_url=seed,
            max_pages=settings.MAX_PAGES_PER_DOMAIN,
            timeout=settings.REQUEST_TIMEOUT,
        )
        if not pages:
            logger.warning(f"No pages scraped for {seed}. Site may block bots or be unreachable "
                            f"from this environment.")
            if use_seed_fallback and domain_key in seed_by_domain:
                logger.info(f"Using curated seed content for {domain_key} "
                            f"({len(seed_by_domain[domain_key])} docs).")
                pages = seed_by_domain[domain_key]

        save_raw_pages(pages, domain_label)
        all_pages.extend(pages)

    logger.info(f"Total pages scraped across all domains: {len(all_pages)}")
    return all_pages


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BMTC website scraper")
    parser.add_argument("--no-seed-fallback", action="store_true",
                         help="Disable falling back to curated seed content if live scraping fails")
    args = parser.parse_args()
    run_scraper(use_seed_fallback=not args.no_seed_fallback)
