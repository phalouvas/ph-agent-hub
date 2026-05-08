"""add_thinking_enabled

Revision ID: 4290105c63b9
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08 04:58:19.234879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4290105c63b9'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only the thinking_enabled columns (all other changes are false-positives)
    op.add_column('models', sa.Column('thinking_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('sessions', sa.Column('thinking_enabled', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'thinking_enabled')
    op.drop_column('models', 'thinking_enabled')
