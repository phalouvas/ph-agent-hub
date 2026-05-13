"""add_temperature_to_sessions

Revision ID: 9a8b7c6d5e4f
Revises: 4290105c63b9
Create Date: 2026-05-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a8b7c6d5e4f'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('temperature', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'temperature')
