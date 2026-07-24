# BMTC Assistant — RAG Chatbot for BookMyTestCenter

A production-ready Retrieval-Augmented Generation (RAG) chatbot that answers
candidate, test-center, and client-organization questions about
**BookMyTestCenter (BMTC)**, grounded strictly in official BMTC website content.

- **Main Website:** https://bookmytestcenter.com/
- **Center Portal:** https://center.bookmytestcenter.com/
- **Client Portal:** https://clients.bookmytestcenter.com/

---

## 1. How it works

```
┌─────────────┐    ┌──────────┐    ┌───────────┐    ┌─────────────┐
│  scraper.py │ →  │cleaner.py│ →  │embedder.py│ →  │ FAISS index │
│ (crawl BMTC)│    │(chunk txt)│    │(embed +   │    │  (on disk)  │
└─────────────┘    └──────────┘    │  index)   │    └──────┬──────┘
                                    └───────────┘           │
                                                             ▼
User question → language detect → retriever.py (top-K + score threshold)
                                             │
                          confidence ≥ threshold?
                          │ yes                    │ no
                          ▼                        ▼
                  build context + prompt   "not found in knowledge base"
                          │
                          ▼
                  Gemini (2.5-flash → 1.5-flash fallback chain)
                          │
             success │            │ failure (quota/network/API error)
                      ▼            ▼
              grounded answer   return retrieved context directly
                                (never crashes the API)
```

**Key design decisions**

- **Seed-content fallback:** if live scraping of bookmytestcenter.com is blocked
  (bot protection, firewall, offline dev environment), `ingestion/seed_content.py`
  supplies curated placeholder FAQ/registration content so the pipeline and demo
  always work end-to-end. Replace this with real scraped/official content before
  going to production — see [Section 7](#7-going-to-production).
- **Cosine similarity via FAISS `IndexFlatIP`** on L2-normalized SentenceTransformer
  embeddings — simple, fast, and accurate for a knowledge base of this size.
- **Confidence gating:** if the top retrieved chunk scores below
  `SIMILARITY_THRESHOLD` (default `0.35`), the bot refuses to guess and returns a
  clear "not found" message instead of hallucinating.
- **Gemini fallback chain + non-crashing degradation:** if every configured Gemini
  model fails (quota, network, invalid key), the API returns the raw retrieved
  context as the answer instead of a 500 error.
- **Multilingual (English + Hindi):** language is auto-detected; Hindi queries are
  translated to English for retrieval, and Gemini is instructed to reply in the
  same language the user used.

---

## 2. Project structure

```
bmtc_rag/
│
├── data/
│   ├── raw/                # scraped/seed page JSON (one file per page)
│   └── processed/          # chunks.json (cleaned + chunked text)
│
├── embeddings/
│   └── faiss_index/        # index.faiss + metadata.json (generated)
│
├── ingestion/
│   ├── scraper.py          # crawls BMTC domains, extracts readable text
│   ├── seed_content.py     # fallback curated content if scraping is blocked
│   ├── cleaner.py          # cleans + chunks text
│   └── embedder.py         # SentenceTransformer embeddings + FAISS index build
│
├── rag/
│   ├── retriever.py        # FAISS load + top-K similarity search + threshold
│   ├── chatbot.py          # orchestration: retrieval → Gemini → fallback
│   └── prompts.py          # prompt templates & canned multilingual messages
│
├── api/
│   └── routes.py           # /chat, /health, /admin/reingest
│
├── frontend/
│   ├── index.html          # chat UI (admit-card / ticket visual theme)
│   ├── style.css
│   └── script.js           # chat logic, voice input, TTS, health polling
│
├── config.py                # centralized settings loaded from .env
├── logger.py                 # loguru logging setup (console + rotating file)
├── ingest_pipeline.py         # one-command runner: scrape → clean → embed
├── main.py                    # FastAPI app entrypoint
├── requirements.txt
├── .env                        # environment variables (edit this!)
└── README.md
```

---

## 3. Installation

Requires **Python 3.10+**.

```bash
cd bmtc_rag
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

> **Note:** `sentence-transformers` will pull in PyTorch (large download, a few
> hundred MB). If you're on a machine with limited disk/bandwidth, install in two
> steps as shown in `requirements.txt` comments, or use a CPU-only Torch wheel.

### Configure environment variables

Edit `.env` (already scaffolded in the project root):

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODELS=gemini-2.5-flash,gemini-1.5-flash,gemini-1.5-flash-8b
EMBEDDING_MODEL=all-MiniLM-L6-v2
TOP_K=5
SIMILARITY_THRESHOLD=0.35
BMTC_URLS=https://bookmytestcenter.com/,https://center.bookmytestcenter.com/,https://clients.bookmytestcenter.com/
```

Get a Gemini API key from **https://aistudio.google.com/app/apikey**.

---

## 4. Build the knowledge base (ingestion)

Run the full pipeline (scrape → clean/chunk → embed → build FAISS index):

```bash
python ingest_pipeline.py
```

Options:

```bash
# Disable the curated seed-content fallback (fail loudly instead if scraping yields nothing)
python ingest_pipeline.py --no-seed-fallback

# Tune chunk size / overlap (in words)
python ingest_pipeline.py --chunk-size 300 --overlap 50
```

Or run each stage individually for debugging:

```bash
python ingestion/scraper.py      # → data/raw/*.json
python ingestion/cleaner.py      # → data/processed/chunks.json
python ingestion/embedder.py     # → embeddings/faiss_index/{index.faiss, metadata.json}
```

**If bookmytestcenter.com blocks the scraper** (bot protection, geo-block, or
you're running in a network-restricted sandbox), the pipeline automatically
falls back to the curated content in `ingestion/seed_content.py` so you still get
a working, demoable knowledge base. Check the logs — you'll see a line like:

```
WARNING  | No pages scraped for https://bookmytestcenter.com/. ...
INFO     | Using curated seed content for bookmytestcenter.com (2 docs).
```

---

## 5. Run the server

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open **http://localhost:8000/** in your browser for the chat UI, or call
the API directly.

---

## 6. API reference

### `POST /chat`

**Request**

```json
{
  "question": "How do I register as a test center?"
}
```

**Response**

```json
{
  "answer": "To register your test center, go to the Center Portal and click Register as a Test Center...",
  "confidence": 0.82,
  "sources": ["Center Portal"],
  "language": "en",
  "used_llm": true
}
```

- `confidence` — top FAISS cosine similarity score (0–1) for the retrieved context.
- `sources` — human-readable labels of the portal(s) the answer was grounded in
  (`Main Website`, `Center Portal`, `Client Portal`).
- `used_llm` — `false` when Gemini failed and the raw retrieved context was
  returned instead (fallback mode), or when confidence was too low to answer at all.

### `GET /health`

```json
{"status": "ok", "index_ready": true, "total_vectors": 128}
```

### `POST /admin/reingest`

Re-runs the full ingestion pipeline and hot-reloads the FAISS index without
restarting the server. **Add authentication before exposing this endpoint
publicly** — it is unauthenticated by default for local/admin use only.

### Testing examples (curl)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I register as a test center?"}'

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "मुझे सेंटर कैसे रजिस्टर करना है?"}'

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
# → returns the "not found in BMTC knowledge base" message (out-of-domain, low confidence)

curl http://localhost:8000/health
```

---

## 7. Frontend features

- Chat bubbles for user vs. bot messages, with source-portal "stamps" and a
  confidence badge on each bot reply.
- Loading / typing indicator while waiting for a response.
- Send button + **Enter key** support.
- **Voice input** via the Web Speech API (`micBtn` — falls back to disabled with
  a tooltip if the browser doesn't support `SpeechRecognition`).
- **Text-to-speech** playback of bot replies, toggleable (`speechSynthesis`,
  auto-detects Hindi vs English for voice selection).
- Fully responsive down to mobile (single-column layout, brand rail collapses).
- Quick-ask shortcut buttons for common questions (including a Hindi example).

No frontend build step is required — it's static HTML/CSS/JS served directly by
FastAPI's `StaticFiles` mount at `/`.

---

## 8. Multilingual support

- Language is detected per-message with `langdetect` (Devanagari Unicode range
  used as a secondary check for robustness).
- Hindi questions are translated to English (via `deep-translator` / Google
  Translate) before FAISS retrieval, since the embedding model is English-centric.
- The Gemini prompt instructs the model to reply in the same language the user
  wrote in.
- If translation fails (e.g. no internet access to the translation backend), the
  original text is used as-is and retrieval still proceeds, just with reduced
  accuracy for non-English queries — it does not crash.

---

## 9. Production hardening notes

- **Logging:** structured logs via `loguru`, written both to console and to
  rotating daily files under `logs/`.
- **Exception handling:** a global FastAPI exception handler prevents unhandled
  errors from crashing the process or leaking stack traces to clients; the
  Gemini call chain and translation calls are individually wrapped so partial
  failures degrade gracefully instead of cascading.
- **Environment variables:** all secrets/config live in `.env` via
  `config.py` / `pydantic`-free lightweight settings loader — never hardcoded.
- **CORS:** configurable via `CORS_ORIGINS` in `.env`; lock this down to your
  real frontend origin(s) in production instead of `*`.
- **Before going live:**
  1. Replace `ingestion/seed_content.py` reliance with verified, complete scraped
     (or officially provided) BMTC content — treat the seed file as scaffolding only.
  2. Add authentication/rate-limiting to `/admin/reingest` and consider running
     ingestion as a separate scheduled job rather than an HTTP-triggered action.
  3. Put the FastAPI app behind a proper ASGI server (e.g. `uvicorn` with
     `gunicorn` workers) and a reverse proxy (nginx) with HTTPS.
  4. Monitor Gemini quota usage and tune `GEMINI_MODELS` fallback order /
     `SIMILARITY_THRESHOLD` based on real query logs.
  5. Consider periodic re-ingestion (cron / scheduler) to keep the knowledge
     base in sync with BMTC website updates.

---

## 10. Tech stack summary

| Layer        | Technology |
|--------------|------------|
| Backend      | Python, FastAPI, Uvicorn |
| Scraping     | requests, BeautifulSoup4, lxml |
| Embeddings   | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector store | FAISS (`IndexFlatIP`, cosine via normalized vectors) |
| LLM          | Google Gemini (`google-genai` SDK), model fallback chain |
| Language     | langdetect, deep-translator |
| Frontend     | HTML, CSS, vanilla JavaScript, Web Speech API |
| Logging      | loguru |

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` shows `index_ready: false` | Ingestion pipeline hasn't been run yet | `python ingest_pipeline.py` |
| Scraper collects 0 pages | Site blocks bots / network restricted | Seed-content fallback kicks in automatically; verify with logs |
| Every answer is "not found in knowledge base" | `SIMILARITY_THRESHOLD` too high, or index built from too little content | Lower threshold in `.env`, or expand seed/scraped content |
| Answers ignore Gemini and always show "fallback mode" | `GEMINI_API_KEY` missing/invalid, or quota exhausted | Check `.env`, check Google AI Studio quota/billing |
| `sentence-transformers` fails to load model | No internet access to huggingface.co | Ensure the deployment environment can reach huggingface.co, or pre-download/cache the model |
