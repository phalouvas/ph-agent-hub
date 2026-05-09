# =============================================================================
# PH Agent Hub — Backend Dockerfile
# =============================================================================
# Multi-stage build:
#   1. builder — installs all Python dependencies
#   2. final — minimal runtime image with only what's needed
# =============================================================================

# ── Builder stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Use increased timeout (1000s) and retries for large packages like claude_agent_sdk (~75MB)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=1000 --retries=5 \
    --user \
    -r requirements.txt

# ── Final stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy only installed packages from builder (avoids build tools in final image)
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

EXPOSE 8000

# CMD is overridden in docker-compose.yml:
#   alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000
