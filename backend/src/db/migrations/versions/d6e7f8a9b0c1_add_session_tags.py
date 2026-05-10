"""add_session_tags

Revision ID: d6e7f8a9b0c1
Revises: n1o2p3q4r5s6
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', mysql.CHAR(36), nullable=False),
        sa.Column('tenant_id', mysql.CHAR(36), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_tags_tenant_id_name'),
    )

    # Create session_tags join table
    op.create_table(
        'session_tags',
        sa.Column('session_id', mysql.CHAR(36), nullable=False),
        sa.Column('tag_id', mysql.CHAR(36), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.PrimaryKeyConstraint('session_id', 'tag_id'),
    )


def downgrade() -> None:
    op.drop_table('session_tags')
    op.drop_table('tags')
