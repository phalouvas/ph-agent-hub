# =============================================================================
# PH Agent Hub — Model Service (CRUD)
# =============================================================================

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..db.orm.models import Model


async def list_models(
    db: AsyncSession, tenant_id: str | None = None
) -> list[Model]:
    """Return all models, optionally filtered by tenant_id."""
    stmt = select(Model)
    if tenant_id is not None:
        stmt = stmt.where(Model.tenant_id == tenant_id)
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
    max_tokens: int = 4096,
    temperature: float = 0.7,
    routing_priority: int = 0,
) -> Model:
    """Create a new model. api_key is transparently encrypted by the ORM."""
    model = Model(
        tenant_id=tenant_id,
        name=name,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        enabled=enabled,
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
    """Delete a model by ID. Raises NotFoundError if missing."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise NotFoundError("Model not found")

    await db.delete(model)
    await db.commit()
