# =============================================================================
# PH Agent Hub — Configuration (Single Source of Truth)
# =============================================================================
# Loads all environment variables once at startup via Pydantic BaseSettings.
# Every other module imports `settings` from here.
# =============================================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str

    # --- Cache ---
    REDIS_URL: str

    # --- Object Storage (MinIO) ---
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_PREFIX: str

    # --- File Upload Limits ---
    UPLOAD_MAX_SIZE_BYTES: int = 20_971_520  # 20 MiB
    UPLOAD_ALLOWED_TYPES: str = (
        "text/plain,text/csv,text/markdown,application/pdf,"
        "application/json,image/png,image/jpeg,image/gif,image/webp"
    )

    # --- Authentication (JWT) ---
    JWT_SECRET: str
    JWT_EXPIRES_IN: int = 3600
    JWT_REFRESH_EXPIRES_IN: int = 2_592_000

    # --- Encryption ---
    ENCRYPTION_KEY: str

    model_config = {"env_file": ".env", "extra": "ignore"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY is required but empty. "
                "Generate one with: python -c "
                "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )


settings = Settings()
