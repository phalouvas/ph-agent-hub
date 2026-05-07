# =============================================================================
# PH Agent Hub — FastAPI Dependencies (Auth Middleware)
# =============================================================================
# Reusable dependency callables for injecting the current user and DB session.
# =============================================================================

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db as _get_db
from ..db.orm.users import User
from ..services.user_service import get_user_by_id
from .exceptions import ForbiddenError, UnauthorizedError
from .jwt import decode_token

# ---------------------------------------------------------------------------
# OAuth2 scheme — tells OpenAPI that /auth/login issues bearer tokens
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# DB session dependency (re-exported for consistency)
# ---------------------------------------------------------------------------
get_db = _get_db


# ---------------------------------------------------------------------------
# get_current_user — JWT auth guard for protected endpoints
# ---------------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Decode JWT, load user from DB, raise 401 if anything is wrong."""
    try:
        payload = decode_token(token)
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Token missing subject claim")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")

    return user


# ---------------------------------------------------------------------------
# Role-based access control dependencies
# ---------------------------------------------------------------------------


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow only users with the 'admin' role."""
    if current_user.role != "admin":
        raise ForbiddenError("Admin access required")
    return current_user


async def require_admin_or_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow users with 'admin' or 'manager' role."""
    if current_user.role not in ("admin", "manager"):
        raise ForbiddenError("Admin or manager access required")
    return current_user
