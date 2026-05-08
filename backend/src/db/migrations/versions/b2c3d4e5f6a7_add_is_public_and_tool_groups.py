"""add_is_public_and_tool_groups

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_public to tools
    op.add_column(
        "tools",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 2. Create tool_groups table
    op.create_table(
        "tool_groups",
        sa.Column("tool_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("group_id", mysql.CHAR(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"]),
        sa.PrimaryKeyConstraint("tool_id", "group_id"),
    )


def downgrade() -> None:
    op.drop_table("tool_groups")
    op.drop_column("tools", "is_public")
