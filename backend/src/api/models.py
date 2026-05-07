# =============================================================================
# PH Agent Hub — Models API Router (User-Facing)
# =============================================================================

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_db
from ..db.orm.users import User as UserORM
from ..services.model_service import list_models as _svc_list_models

router = APIRouter(prefix="/models", tags=["models"])


class ModelResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    model_id: str | None
    provider: str
    base_url: str | None
    enabled: bool
    max_tokens: int
    temperature: float
    routing_priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ModelResponse])
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Return all enabled models for the current user's tenant."""
    models = await _svc_list_models(db, tenant_id=current_user.tenant_id)
    enabled = [m for m in models if m.enabled]
    return [ModelResponse.model_validate(m) for m in enabled]
