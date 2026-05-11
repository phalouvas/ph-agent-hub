"""add_pricing_cost_and_denormalized_logs

Revision ID: c1d2e3f4a5b6
Revises: d6e7f8a9b0c1
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add pricing columns to models table
    # ------------------------------------------------------------------
    op.add_column(
        "models",
        sa.Column(
            "input_price_per_1m",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "models",
        sa.Column(
            "output_price_per_1m",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "models",
        sa.Column(
            "cache_hit_price_per_1m",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 2. Drop FKs on usage_logs + add snapshot and cost columns
    # ------------------------------------------------------------------
    op.drop_constraint("usage_logs_ibfk_1", "usage_logs", type_="foreignkey")
    op.drop_constraint("usage_logs_ibfk_2", "usage_logs", type_="foreignkey")
    op.drop_constraint("usage_logs_ibfk_3", "usage_logs", type_="foreignkey")

    op.add_column(
        "usage_logs",
        sa.Column("tenant_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column("user_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column("user_full_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column("model_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column("provider", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column(
            "cost",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "usage_logs",
        sa.Column("cache_hit_tokens", sa.Integer(), nullable=True),
    )

    # ------------------------------------------------------------------
    # 3. Drop FKs on audit_logs + add snapshot columns
    # ------------------------------------------------------------------
    op.drop_constraint("audit_logs_ibfk_1", "audit_logs", type_="foreignkey")
    op.drop_constraint("audit_logs_ibfk_2", "audit_logs", type_="foreignkey")

    op.add_column(
        "audit_logs",
        sa.Column("tenant_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("actor_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("actor_full_name", sa.String(length=255), nullable=True),
    )

    # ------------------------------------------------------------------
    # 4. Create app_settings table
    # ------------------------------------------------------------------
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed default currency
    op.execute("INSERT INTO app_settings (`key`, `value`) VALUES ('currency', 'EUR')")


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 4. Drop app_settings table
    # ------------------------------------------------------------------
    op.drop_table("app_settings")

    # ------------------------------------------------------------------
    # 3. Restore audit_logs
    # ------------------------------------------------------------------
    op.drop_column("audit_logs", "actor_full_name")
    op.drop_column("audit_logs", "actor_email")
    op.drop_column("audit_logs", "tenant_name")

    op.create_foreign_key(
        "audit_logs_ibfk_2", "audit_logs", "users", ["actor_id"], ["id"]
    )
    op.create_foreign_key(
        "audit_logs_ibfk_1", "audit_logs", "tenants", ["tenant_id"], ["id"]
    )

    # ------------------------------------------------------------------
    # 2. Restore usage_logs
    # ------------------------------------------------------------------
    op.drop_column("usage_logs", "cache_hit_tokens")
    op.drop_column("usage_logs", "cost")
    op.drop_column("usage_logs", "provider")
    op.drop_column("usage_logs", "model_name")
    op.drop_column("usage_logs", "user_full_name")
    op.drop_column("usage_logs", "user_email")
    op.drop_column("usage_logs", "tenant_name")

    op.create_foreign_key(
        "usage_logs_ibfk_3", "usage_logs", "models", ["model_id"], ["id"]
    )
    op.create_foreign_key(
        "usage_logs_ibfk_2", "usage_logs", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "usage_logs_ibfk_1", "usage_logs", "tenants", ["tenant_id"], ["id"]
    )

    # ------------------------------------------------------------------
    # 1. Drop pricing columns from models
    # ------------------------------------------------------------------
    op.drop_column("models", "cache_hit_price_per_1m")
    op.drop_column("models", "output_price_per_1m")
    op.drop_column("models", "input_price_per_1m")
