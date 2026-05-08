"""add_follow_up_questions_enabled_to_models

Revision ID: 5db963e14b25
Revises: bf8c9d0e1a2b
Create Date: 2026-05-08 08:42:52.224687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5db963e14b25"
down_revision: Union[str, None] = "bf8c9d0e1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column(
            "follow_up_questions_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("models", "follow_up_questions_enabled")
