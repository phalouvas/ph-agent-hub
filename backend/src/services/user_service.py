# =============================================================================
# PH Agent Hub — User Service (CRUD)
# =============================================================================

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ConflictError, NotFoundError
from ..core.security import hash_password
from ..db.orm.users import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Look up a user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession, tenant_id: str | None = None
) -> list[User]:
    """Return all users, optionally filtered by tenant_id."""
    stmt = select(User)
    if tenant_id is not None:
        stmt = stmt.where(User.tenant_id == tenant_id)
    stmt = stmt.order_by(User.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    tenant_id: str,
    email: str,
    password: str,
    display_name: str,
    role: str = "user",
) -> User:
    """Create a new user. Raises ConflictError if email already exists."""
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise ConflictError("A user with this email already exists")

    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: str,
    **fields: str | bool,
) -> User:
    """Update a user's fields. Raises NotFoundError if missing.

    Supported fields: email, display_name, role, is_active, password.
    'password' will be hashed before storage.
    """
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    # Handle email uniqueness separately
    if "email" in fields and fields["email"] != user.email:
        existing = await db.execute(
            select(User).where(User.email == fields["email"], User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("A user with this email already exists")

    if "password" in fields:
        user.password_hash = hash_password(fields.pop("password"))

    for key, value in fields.items():
        if hasattr(user, key):
            setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: str) -> None:
    """Delete a user by ID. Raises NotFoundError if missing."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    await db.delete(user)
    await db.commit()


async def update_user_default_model(
    db: AsyncSession, user_id: str, model_id: str | None
) -> User:
    """Set or clear a user's default model. Raises NotFoundError if user missing."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    user.default_model_id = model_id
    await db.commit()
    await db.refresh(user)
    return user
