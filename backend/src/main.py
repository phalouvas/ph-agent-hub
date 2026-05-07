# =============================================================================
# PH Agent Hub — Backend Entry Point
# =============================================================================
# Phase 1: FastAPI app with core utilities, ORM models, storage module,
# and API router stubs wired in.
# =============================================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.admin import router as admin_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.memory import router as memory_router
from .api.models import router as models_router
from .api.prompts import router as prompts_router
from .api.skills import router as skills_router
from .api.templates import router as templates_router
from .core.exceptions import AppException, app_exception_handler


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: scan MAF registry. Shutdown: no-op for now."""
    from .agents.registry import startup_scan
    from .db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await startup_scan(db)

    yield


app = FastAPI(title="PH Agent Hub", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
app.add_exception_handler(AppException, app_exception_handler)

# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(models_router)
app.include_router(admin_router)
app.include_router(templates_router)
app.include_router(prompts_router)
app.include_router(skills_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
