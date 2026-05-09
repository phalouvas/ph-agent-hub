# =============================================================================
# PH Agent Hub — Backend Dockerfile
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
# Use increased timeout (1000s) and retries for large packages like claude_agent_sdk (~75MB)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=1000 --retries=5 -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# CMD is overridden in docker-compose.yml:
#   alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000
