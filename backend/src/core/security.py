# =============================================================================
# PH Agent Hub — Password Hashing & Verification
# =============================================================================

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)
