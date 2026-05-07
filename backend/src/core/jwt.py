# =============================================================================
# PH Agent Hub — JWT Encode / Decode
# =============================================================================
# Single-module rule: ONLY this file imports `python-jose`.
# =============================================================================

from datetime import datetime, timedelta, timezone

from jose import jwt as jose_jwt

from .config import settings


def create_access_token(payload: dict) -> str:
    """Create a signed JWT access token.

    The provided payload should contain at minimum:
        sub (subject / user id), tenant_id, role
    The `exp` (expiration) and `iat` (issued-at) claims are added automatically.
    """
    now = datetime.now(timezone.utc)
    to_encode = payload.copy()
    to_encode.update(
        {
            "iat": now,
            "exp": now + timedelta(seconds=settings.JWT_EXPIRES_IN),
        }
    )
    return jose_jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(payload: dict) -> str:
    """Create a signed JWT refresh token with longer TTL."""
    now = datetime.now(timezone.utc)
    to_encode = payload.copy()
    to_encode.update(
        {
            "iat": now,
            "exp": now + timedelta(seconds=settings.JWT_REFRESH_EXPIRES_IN),
        }
    )
    return jose_jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns the claims dict."""
    return jose_jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
