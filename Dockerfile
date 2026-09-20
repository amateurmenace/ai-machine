# Community AI on Cloud Run.
#
# Two-stage: build the React console, then serve it and the API from one
# container. One service is simpler to reason about than two, and at a town's
# traffic the static files cost nothing to serve from the same process.
#
# The image does NOT contain a model. Inference stays on hardware the community
# owns, reached over a tunnel; see ROADMAP.md for why that is the recommended
# shape and what the alternative costs.

# --- stage 1: the console -------------------------------------------------
FROM node:20-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# Same-origin API: the console and the gateway are one service, so the console
# calls relative paths and needs no base URL baked in at build time.
ENV REACT_APP_API_URL=""
RUN npm run build


# --- stage 2: the service -------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Sentence-transformers writes here; Cloud Run's filesystem is in-memory,
    # so keep it small and predictable rather than letting it land anywhere.
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers \
    # One instance owns the sync schedule. With more than one, turn this off
    # and drive sync from Cloud Scheduler instead; see deploy/README.md.
    COMMUNITY_SYNC_ENABLED=false

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Bake the embedding model into the image. Downloading it on first request
# would make every cold start a 90MB download and a very slow first answer.
RUN python3 -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .
COPY --from=frontend /build/build ./frontend/build

# Run as a non-root user. Cloud Run does not require it; defense in depth does.
RUN useradd --create-home --uid 1000 community \
 && mkdir -p /app/data /app/.cache \
 && chown -R community:community /app
USER community

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD curl -fsS "http://localhost:${PORT:-8080}/healthz" || exit 1

# One worker on purpose. The keyword index and the rate limiter live in process
# memory, so a second worker would double the memory and halve the rate limit's
# meaning. Concurrency within the worker handles a town's traffic; see
# deploy/README.md before raising either number.
CMD exec gunicorn app:app \
    --bind "0.0.0.0:${PORT:-8080}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --threads 8 \
    --timeout 0 \
    --access-logfile - \
    --error-logfile -
