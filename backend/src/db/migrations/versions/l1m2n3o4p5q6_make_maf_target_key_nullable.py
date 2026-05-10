"""make_maf_target_key_nullable

Revision ID: l1m2n3o4p5q6
Revises: k2l3m4n5o6p7
Create Date: 2026-05-10

Allow skills.maf_target_key to be NULL so the backend can auto-generate
it from the skill title when not explicitly provided.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "skills",
        "maf_target_key",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "skills",
        "maf_target_key",
        existing_type=sa.String(255),
        nullable=False,
    )
