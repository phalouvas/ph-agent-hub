"""add_category_to_tools

Add category VARCHAR(50) NOT NULL DEFAULT 'general' to the tools table.

Revision ID: p1q2r3s4t5u6
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tools",
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default="general",
        ),
    )


def downgrade() -> None:
    op.drop_column("tools", "category")
