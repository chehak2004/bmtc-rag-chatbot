"""
ingest_pipeline.py
------------------
Convenience entry point that runs the full ingestion pipeline end-to-end:

    1. Scrape BMTC websites (with seed-content fallback)         -> ingestion/scraper.py
    2. Clean + chunk the scraped text                            -> ingestion/cleaner.py
    3. Embed chunks and build the FAISS index                    -> ingestion/embedder.py

Usage:
    python ingest_pipeline.py
    python ingest_pipeline.py --no-seed-fallback
    python ingest_pipeline.py --chunk-size 300 --overlap 50
"""
import argparse

from logger import logger
from ingestion.scraper import run_scraper
from ingestion.cleaner import run_cleaning
from ingestion.embedder import run_embedding_pipeline


def main():
    parser = argparse.ArgumentParser(description="Run the full BMTC RAG ingestion pipeline")
    parser.add_argument("--no-seed-fallback", action="store_true",
                         help="Disable curated seed content fallback when live scraping yields nothing")
    parser.add_argument("--chunk-size", type=int, default=400, help="Chunk size in words")
    parser.add_argument("--overlap", type=int, default=60, help="Chunk overlap in words")
    args = parser.parse_args()

    logger.info("=== STEP 1/3: Scraping BMTC websites ===")
    pages = run_scraper(use_seed_fallback=not args.no_seed_fallback)
    logger.info(f"Scraping complete. {len(pages)} pages collected.")

    logger.info("=== STEP 2/3: Cleaning & chunking text ===")
    chunks = run_cleaning(chunk_size=args.chunk_size, overlap=args.overlap)
    logger.info(f"Chunking complete. {len(chunks)} chunks created.")

    logger.info("=== STEP 3/3: Generating embeddings & building FAISS index ===")
    run_embedding_pipeline()
    logger.info("Ingestion pipeline finished successfully. The chatbot knowledge base is ready.")


if __name__ == "__main__":
    main()
