"""add_selected_model_id_to_sessions

Revision ID: a0d649bdc5b6
Revises: 6b6bd31267a0
Create Date: 2026-05-07 09:15:05.416839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'a0d649bdc5b6'
down_revision: Union[str, None] = '6b6bd31267a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sessions',
        sa.Column('selected_model_id', mysql.CHAR(length=36), nullable=True),
    )
    op.create_foreign_key(
        None, 'sessions', 'models', ['selected_model_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint(
        'sessions_ibfk_6', 'sessions', type_='foreignkey'
    )
    op.drop_column('sessions', 'selected_model_id')
