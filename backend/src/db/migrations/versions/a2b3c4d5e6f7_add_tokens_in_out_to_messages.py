"""add_tokens_in_out_to_messages

Revision ID: a2b3c4d5e6f7
Revises: e8f9a0b1c2d3
Create Date: 2026-05-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("tokens_in", sa.Integer(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("tokens_out", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "tokens_out")
    op.drop_column("messages", "tokens_in")
