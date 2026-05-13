"""add_code_to_tools

Revision ID: 0a1b2c3d4e5f
Revises: 9a8b7c6d5e4f
Create Date: 2026-05-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0a1b2c3d4e5f'
down_revision: Union[str, None] = '9a8b7c6d5e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tools', sa.Column('code', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('tools', 'code')
