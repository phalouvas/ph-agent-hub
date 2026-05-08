# =============================================================================
# PH Agent Hub — Model Service (CRUD)
# =============================================================================

from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..db.orm.models import Model
from ..db.orm.groups import ModelGroup, UserGroupMember
from ..db.orm.sessions import Session
from ..db.orm.templates import Template


async def list_models(
    db: AsyncSession,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> list[Model]:
    """Return all models, optionally filtered by tenant_id and user access.

    When user_id is provided, only returns models where:
    - is_public=True, OR
    - the model is assigned to a group the user belongs to
    """
    stmt = select(Model)
    if tenant_id is not None:
        stmt = stmt.where(Model.tenant_id == tenant_id)

    if user_id is not None:
        # Subquery: group IDs the user belongs to
        user_group_subq = (
            select(ModelGroup.model_id)
            .join(UserGroupMember, UserGroupMember.group_id == ModelGroup.group_id)
            .where(UserGroupMember.user_id == user_id)
        )
        stmt = stmt.where(
            or_(
                Model.is_public == True,  # noqa: E712
                Model.id.in_(user_group_subq),
            )
        )

    stmt = stmt.order_by(Model.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_model_by_id(db: AsyncSession, model_id: str) -> Model | None:
    """Look up a model by primary key."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    return result.scalar_one_or_none()


async def create_model(
    db: AsyncSession,
    tenant_id: str,
    name: str,
    provider: str,
    api_key: str,
    base_url: str | None = None,
    enabled: bool = True,
    is_public: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    routing_priority: int = 0,
    model_id: str | None = None,
) -> Model:
    """Create a new model. api_key is transparently encrypted by the ORM."""
    model = Model(
        tenant_id=tenant_id,
        name=name,
        model_id=model_id,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        enabled=enabled,
        is_public=is_public,
        max_tokens=max_tokens,
        temperature=temperature,
        routing_priority=routing_priority,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def update_model(db: AsyncSession, model_id: str, **fields) -> Model:
    """Update a model's fields. Raises NotFoundError if missing."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise NotFoundError("Model not found")

    for key, value in fields.items():
        if hasattr(model, key):
            setattr(model, key, value)

    await db.commit()
    await db.refresh(model)
    return model


async def delete_model(db: AsyncSession, model_id: str) -> None:
    """Delete a model by ID. Raises NotFoundError if missing.
    Clears references from sessions that use this model first."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise NotFoundError("Model not found")

    # Clear selected_model_id in sessions that reference this model
    await db.execute(
        update(Session)
        .where(Session.selected_model_id == model_id)
        .values(selected_model_id=None)
    )

    # Clear default_model_id in templates that reference this model
    await db.execute(
        update(Template)
        .where(Template.default_model_id == model_id)
        .values(default_model_id=None)
    )

    await db.delete(model)
    await db.commit()
