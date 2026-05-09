"""add_updated_at_to_memory

Revision ID: g1h2i3j4k5l6
Revises: a2b3c4d5e6f7
Create Date: 2026-05-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'memory',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        ),
    )
    op.create_index(
        'ix_memory_user_id_tenant_id',
        'memory',
        ['user_id', 'tenant_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_memory_user_id_tenant_id', table_name='memory')
    op.drop_column('memory', 'updated_at')
