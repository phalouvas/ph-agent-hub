"""Add model_id column to models table

Revision ID: d4e5f6a7b8c9
Revises: c8f7e3a1b2d4
Create Date: 2026-05-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c8f7e3a1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("models", sa.Column("model_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("models", "model_id")
