# ╔══════════════════════════════════════════════════════════════════╗
# ║  VIDHYA BOT — Telegram Bot Dockerfile                          ║
# ║  Phase 6: Full Aiogram bot implementation                      ║
# ╚══════════════════════════════════════════════════════════════════╝

FROM python:3.12-slim

# ── System dependencies ───────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user ─────────────────────────────────────────
RUN groupadd -r botuser && useradd -r -g botuser -d /app -s /sbin/nologin botuser

WORKDIR /app

# ── Install dependencies ─────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy code ────────────────────────────────────────────────────
COPY . .

# ── Set ownership ────────────────────────────────────────────────
RUN chown -R botuser:botuser /app

USER botuser

# ── Entrypoint ───────────────────────────────────────────────────
CMD ["python", "main.py"]
