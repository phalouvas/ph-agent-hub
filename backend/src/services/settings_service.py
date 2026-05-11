# =============================================================================
# PH Agent Hub — App Settings Service
# =============================================================================
# Key-value store for application-wide configuration.
# =============================================================================

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.orm.app_settings import AppSetting

logger = logging.getLogger(__name__)


async def get_setting(db: AsyncSession, key: str, default: str | None = None) -> str | None:
    """Get a single setting value by key. Returns default if not found."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    """Get all settings as a key-value dict."""
    result = await db.execute(select(AppSetting))
    return {s.key: s.value for s in result.scalars().all() if s.value is not None}


async def set_settings(db: AsyncSession, settings: dict[str, str]) -> dict[str, str]:
    """Bulk upsert settings. Returns the updated key-value dict."""
    for key, value in settings.items():
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            logger.info("Updated app setting: %s = %s", key, value)
        else:
            db.add(AppSetting(key=key, value=value))
            logger.info("Created app setting: %s = %s", key, value)

    await db.commit()
    return await get_all_settings(db)
