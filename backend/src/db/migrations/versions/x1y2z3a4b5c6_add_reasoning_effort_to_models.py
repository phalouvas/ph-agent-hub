"""add_reasoning_effort_to_models

Add reasoning_effort column to the models table for DeepSeek thinking
mode effort control (values: high, max).

Revision ID: x1y2z3a4b5c6
Revises: t5u6v7w8x9y0
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "x1y2z3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "t5u6v7w8x9y0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column(
            "reasoning_effort",
            sa.String(length=10),
            nullable=True,
            comment="DeepSeek thinking effort level (high, max); only applies when thinking_enabled is True",
        ),
    )


def downgrade() -> None:
    op.drop_column("models", "reasoning_effort")
