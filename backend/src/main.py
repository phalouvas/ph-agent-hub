# =============================================================================
# PH Agent Hub — Backend Entry Point (Phase 0 Stub)
# =============================================================================
# Phase 0: minimal FastAPI app with a /health endpoint.
# No database, auth, or other modules are imported yet.
# =============================================================================

from fastapi import FastAPI

app = FastAPI(title="PH Agent Hub", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
