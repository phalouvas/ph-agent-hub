"""add_user_tool_preferences

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_tool_preferences",
        sa.Column("user_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("tool_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("always_on", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"]),
        sa.PrimaryKeyConstraint("user_id", "tool_id"),
    )


def downgrade() -> None:
    op.drop_table("user_tool_preferences")
