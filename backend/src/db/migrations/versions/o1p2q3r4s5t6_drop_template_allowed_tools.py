"""drop template_allowed_tools table

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-05-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('template_allowed_tools')


def downgrade() -> None:
    op.create_table('template_allowed_tools',
        sa.Column('template_id', sa.CHAR(36), sa.ForeignKey('templates.id'), primary_key=True),
        sa.Column('tool_id', sa.CHAR(36), sa.ForeignKey('tools.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
