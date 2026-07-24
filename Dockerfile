# ---------------------------------------------------------------------------
# BMTC RAG Chatbot — Dockerfile
# Multi-stage-free single image (simplicity over minimal size for this scale).
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# System deps: lxml needs libxml2/libxslt at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Ensure runtime dirs exist even if not baked in from build context
RUN mkdir -p data/raw data/processed embeddings/faiss_index logs

# Pre-download the embedding model at build time so cold-starts don't hit
# the model host on every container restart.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
