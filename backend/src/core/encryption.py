# =============================================================================
# PH Agent Hub — Fernet Symmetric Encryption
# =============================================================================
# Single-module rule: ONLY this file imports `cryptography`.
# Provides encrypt/decrypt helpers and an EncryptedString SQLAlchemy type.
# =============================================================================

from cryptography.fernet import Fernet
from sqlalchemy.types import TypeDecorator, String

from .config import settings


_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt(value: str) -> str:
    """Encrypt a plaintext string. Returns the Fernet token as a string."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a Fernet token back to the original plaintext string."""
    return _fernet.decrypt(value.encode()).decode()


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts string columns.

    Usage in ORM models:
        api_key = Column(EncryptedString(512))
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 512):
        super().__init__(length)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
