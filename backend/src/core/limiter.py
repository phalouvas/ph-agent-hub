# =============================================================================
# PH Agent Hub — Rate Limiter (slowapi singleton)
# =============================================================================
# Single-module rule: ONLY this file imports `slowapi`.
# =============================================================================

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter", "RateLimitExceeded"]
