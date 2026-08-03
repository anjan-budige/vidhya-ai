# ╔══════════════════════════════════════════════════════════════════╗
# ║  VIDHYA BOT — Backend Dockerfile (FastAPI + Celery)             ║
# ║  Multi-purpose: backend server, celery worker, beat, flower     ║
# ╚══════════════════════════════════════════════════════════════════╝

FROM python:3.12-slim AS base

# ── System dependencies ───────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user ─────────────────────────────────────────
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# ── Working directory ─────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ──────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Install PhonePe SDK from official PhonePe index ──────────────
RUN pip install --no-cache-dir phonepe-pg-sdk-python \
    --index-url https://api.phonepe.com/apis/pg-sdk/python \
    --extra-index-url https://pypi.org/simple

# ── Copy application code ────────────────────────────────────────
COPY app/ ./app/

# ── Set ownership ────────────────────────────────────────────────
RUN chown -R appuser:appuser /app

# ── Switch to non-root user ──────────────────────────────────────
USER appuser

# ── Expose port ──────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ─────────────────────────────────────────────────
HEALTHCHECK --interval=15s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# ── Default entrypoint: FastAPI with Uvicorn ─────────────────────
# Workers set to 2 for low-end machine; override via env
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--loop", "uvloop", "--http", "httptools"]
