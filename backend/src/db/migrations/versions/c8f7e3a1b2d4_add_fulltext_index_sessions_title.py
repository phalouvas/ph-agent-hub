"""add_fulltext_index_sessions_title

Revision ID: c8f7e3a1b2d4
Revises: a0d649bdc5b6
Create Date: 2026-05-07 14:00:00.000000

Add FULLTEXT index on sessions.title for the session search endpoint.
MariaDB cannot FULLTEXT-index a native JSON column (messages.content),
so message search uses LIKE/JSON_SEARCH in the API layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f7e3a1b2d4'
down_revision: Union[str, None] = 'a0d649bdc5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'idx_sessions_title_ft',
        'sessions',
        ['title'],
        mysql_prefix='FULLTEXT',
    )


def downgrade() -> None:
    op.drop_index('idx_sessions_title_ft', 'sessions')
