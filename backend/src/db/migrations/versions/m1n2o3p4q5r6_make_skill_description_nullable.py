"""make_skill_description_nullable

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-05-10

Allow skills.description to be NULL so it's optional when creating skills.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "skills",
        "description",
        existing_type=sa.String(1024),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "skills",
        "description",
        existing_type=sa.String(1024),
        nullable=False,
    )
