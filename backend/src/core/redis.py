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


# ---------------------------------------------------------------------------
# Temporary session helpers — Redis-backed session storage
# ---------------------------------------------------------------------------
TEMP_SESSION_PREFIX = "session:tmp:"


async def store_temp_session(
    session_id: str, data: dict, ttl: int | None = None
) -> None:
    """Store a temporary session JSON blob in Redis.

    Args:
        session_id: The session UUID.
        data: JSON-serialisable dict of session fields.
        ttl: TTL in seconds (defaults to settings.TEMPORARY_SESSION_TTL_SECONDS).
    """
    import json

    from .config import settings as _settings

    r = await get_redis()
    key = f"{TEMP_SESSION_PREFIX}{session_id}"
    ttl = ttl if ttl is not None else _settings.TEMPORARY_SESSION_TTL_SECONDS
    await r.setex(key, ttl, json.dumps(data))


async def get_temp_session(session_id: str) -> dict | None:
    """Retrieve a temporary session JSON blob from Redis.

    Returns None if the key does not exist.
    """
    import json

    r = await get_redis()
    key = f"{TEMP_SESSION_PREFIX}{session_id}"
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def delete_temp_session(session_id: str) -> None:
    """Delete a temporary session and its messages from Redis."""
    r = await get_redis()
    key = f"{TEMP_SESSION_PREFIX}{session_id}"
    msg_key = f"{TEMP_SESSION_PREFIX}{session_id}:messages"
    await r.delete(key, msg_key)


async def append_temp_message(session_id: str, msg: dict) -> None:
    """Append a message dict to the temporary session's message list.

    Messages are stored as a JSON list at ``session:tmp:{id}:messages``.
    The session TTL is refreshed on each append.
    """
    import json

    from .config import settings as _settings

    r = await get_redis()
    msg_key = f"{TEMP_SESSION_PREFIX}{session_id}:messages"
    session_key = f"{TEMP_SESSION_PREFIX}{session_id}"

    # Atomically append and refresh TTL
    pipe = r.pipeline()
    pipe.get(msg_key)
    pipe.ttl(session_key)
    existing_raw, ttl = await pipe.execute()

    messages: list[dict] = json.loads(existing_raw) if existing_raw else []
    messages.append(msg)

    ttl = ttl if ttl and ttl > 0 else _settings.TEMPORARY_SESSION_TTL_SECONDS
    pipe2 = r.pipeline()
    pipe2.setex(msg_key, ttl, json.dumps(messages))
    # Refresh the session blob TTL too so it doesn't expire before messages
    pipe2.expire(session_key, ttl)
    await pipe2.execute()


async def get_temp_messages(session_id: str) -> list[dict]:
    """Retrieve all messages for a temporary session.

    Returns an empty list if no messages exist.
    """
    import json

    r = await get_redis()
    msg_key = f"{TEMP_SESSION_PREFIX}{session_id}:messages"
    raw = await r.get(msg_key)
    if raw is None:
        return []
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Stream cancellation helpers — used by the SSE streaming endpoint to
# signal an in-progress agent run that it should abort.
# ---------------------------------------------------------------------------
STREAM_CANCEL_PREFIX = "stream:cancel:"


async def set_stream_cancel(session_id: str, ttl: int = 60) -> None:
    """Set a stream cancellation flag for *session_id*.

    The flag auto-expires after *ttl* seconds to prevent stale keys.
    """
    r = await get_redis()
    await r.setex(f"{STREAM_CANCEL_PREFIX}{session_id}", ttl, "1")


async def check_stream_cancel(session_id: str) -> bool:
    """Return True if a cancellation has been requested for *session_id*."""
    r = await get_redis()
    return await r.exists(f"{STREAM_CANCEL_PREFIX}{session_id}") > 0


async def clear_stream_cancel(session_id: str) -> None:
    """Remove the stream cancellation flag for *session_id*."""
    r = await get_redis()
    await r.delete(f"{STREAM_CANCEL_PREFIX}{session_id}")
