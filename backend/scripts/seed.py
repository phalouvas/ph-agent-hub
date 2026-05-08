# =============================================================================
# PH Agent Hub — Idempotent Admin Seed Script
# =============================================================================
# Creates the first admin user and default tenant on first run.
# Safe to run multiple times — skips existing records.
#
# Usage (from /app inside Docker container):
#   python scripts/seed.py
#
# Environment variables (NOT via Settings — seed-only):
#   ADMIN_EMAIL          — default: admin@phagent.local
#   ADMIN_PASSWORD       — default: admin
#   DEFAULT_TENANT_NAME  — default: Default
# =============================================================================

import asyncio
import os
import sys

# Make src/ importable when running from /app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from src.core.security import hash_password
from src.db.base import AsyncSessionLocal
from src.db.orm.tenants import Tenant
from src.db.orm.tools import Tool
from src.db.orm.users import User

# ---------------------------------------------------------------------------
# Configuration (from environment, not Settings)
# ---------------------------------------------------------------------------
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@phagent.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
DEFAULT_TENANT_NAME = os.getenv("DEFAULT_TENANT_NAME", "Default")
SEED_ALLOW_WEAK_PASSWORD = os.getenv("SEED_ALLOW_WEAK_PASSWORD", "false").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    # Safety check: refuse weak passwords unless explicitly allowed
    if ADMIN_PASSWORD == "admin" and not SEED_ALLOW_WEAK_PASSWORD:
        print(
            "[seed] ERROR: ADMIN_PASSWORD is set to the default 'admin' and "
            "SEED_ALLOW_WEAK_PASSWORD is not enabled.\n"
            "       Set SEED_ALLOW_WEAK_PASSWORD=true to override (dev only), "
            "or set a strong ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    async with AsyncSessionLocal() as db:
        # 1. Ensure default tenant exists
        result = await db.execute(
            select(Tenant).where(Tenant.name == DEFAULT_TENANT_NAME)
        )
        tenant = result.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(name=DEFAULT_TENANT_NAME)
            db.add(tenant)
            await db.flush()
            print(f"[seed] Created tenant: {DEFAULT_TENANT_NAME} (id={tenant.id})")
        else:
            print(f"[seed] Tenant already exists: {DEFAULT_TENANT_NAME} (id={tenant.id})")

        # 2. Ensure admin user exists
        result = await db.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = User(
                tenant_id=tenant.id,
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                display_name="Admin",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            print(f"[seed] Created admin user: {ADMIN_EMAIL} (id={admin.id})")
        else:
            print(f"[seed] Admin user already exists: {ADMIN_EMAIL} (id={admin.id})")

        # 3. Ensure default datetime tool exists
        result = await db.execute(
            select(Tool).where(
                Tool.tenant_id == tenant.id,
                Tool.type == "datetime",
                Tool.name == "Current Time",
            )
        )
        datetime_tool = result.scalar_one_or_none()

        if datetime_tool is None:
            datetime_tool = Tool(
                tenant_id=tenant.id,
                name="Current Time",
                type="datetime",
                config={"default_timezone": "UTC"},
                enabled=True,
                is_public=True,
            )
            db.add(datetime_tool)
            await db.flush()
            print(f"[seed] Created datetime tool: Current Time (id={datetime_tool.id})")
        else:
            print(f"[seed] Datetime tool already exists: Current Time (id={datetime_tool.id})")

        # 4. Ensure default web search tool exists
        result = await db.execute(
            select(Tool).where(
                Tool.tenant_id == tenant.id,
                Tool.type == "web_search",
                Tool.name == "Web Search",
            )
        )
        web_search_tool = result.scalar_one_or_none()

        if web_search_tool is None:
            web_search_tool = Tool(
                tenant_id=tenant.id,
                name="Web Search",
                type="web_search",
                config={
                    "max_results": 10,
                    "region": "us-en",
                    "safesearch": "moderate",
                    "backend": "auto",
                },
                enabled=True,
                is_public=True,
            )
            db.add(web_search_tool)
            await db.flush()
            print(f"[seed] Created web_search tool: Web Search (id={web_search_tool.id})")
        else:
            print(f"[seed] Web Search tool already exists: Web Search (id={web_search_tool.id})")

        await db.commit()

    print("[seed] Done.")


if __name__ == "__main__":
    asyncio.run(main())
