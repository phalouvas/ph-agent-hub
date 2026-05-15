# =============================================================================
# PH Agent Hub — Users API Router (Current User Profile)
# =============================================================================

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_db
from ..core.exceptions import NotFoundError, ValidationError
from ..db.orm.users import User as UserORM
from ..services.model_service import get_model_by_id, list_models as _svc_list_models
from ..services.user_service import update_user_default_model

router = APIRouter(prefix="/users", tags=["users"])


class UserMeResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str
    is_active: bool
    default_model_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SetDefaultModelRequest(BaseModel):
    model_id: str | None = None


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: UserORM = Depends(get_current_user),
):
    """Return the current user's profile including default_model_id."""
    return UserMeResponse.model_validate(current_user)


@router.put("/me/default-model")
async def set_default_model(
    body: SetDefaultModelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Set the current user's default model.

    Validates that the model is accessible to the user.
    Set model_id to null to clear the default.
    """
    if body.model_id is not None:
        # Validate the model exists
        model = await get_model_by_id(db, body.model_id)
        if model is None:
            raise NotFoundError("Model not found")

        # Validate the model is accessible to this user
        accessible_models, _ = await _svc_list_models(
            db, tenant_id=current_user.tenant_id, user_id=current_user.id
        )
        accessible_ids = {m.id for m in accessible_models}
        if body.model_id not in accessible_ids:
            raise ValidationError("Model is not accessible to you")

    await update_user_default_model(db, current_user.id, body.model_id)
    return {"default_model_id": body.model_id}
