# =============================================================================
# PH Agent Hub — Async Redis Client (JTI Denylist)
# =============================================================================
# Single-module rule: ONLY this file imports `redis.asyncio`.
# =============================================================================

import redis.asyncio as aioredis

from .config import settings

# ---------------------------------------------------------------------------
# Lazy singleton Redis connection
# ---------------------------------------------------------------------------
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a connected async Redis client (lazy singleton)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


# ---------------------------------------------------------------------------
# Denylist helpers — JTI revocation for refresh tokens
# ---------------------------------------------------------------------------
DENYLIST_PREFIX = "jti_denylist:"


async def add_to_denylist(jti: str, ttl_seconds: int) -> None:
    """Add a JWT JTI to the Redis denylist with an absolute TTL."""
    r = await get_redis()
    await r.setex(f"{DENYLIST_PREFIX}{jti}", ttl_seconds, "1")


async def is_denylisted(jti: str) -> bool:
    """Check whether a JTI is present in the Redis denylist."""
    r = await get_redis()
    return await r.exists(f"{DENYLIST_PREFIX}{jti}") > 0
