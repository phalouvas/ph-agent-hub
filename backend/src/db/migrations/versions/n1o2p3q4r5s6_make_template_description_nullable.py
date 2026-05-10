"""make_template_description_nullable

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-05-10

Allow templates.description to be NULL so it's optional when creating templates.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "n1o2p3q4r5s6"
down_revision: Union[str, None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "templates",
        "description",
        existing_type=sa.String(1024),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "templates",
        "description",
        existing_type=sa.String(1024),
        nullable=False,
    )
