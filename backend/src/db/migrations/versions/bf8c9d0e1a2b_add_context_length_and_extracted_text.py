"""add_context_length_and_extracted_text

Revision ID: bf8c9d0e1a2b
Revises: 4290105c63b9
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bf8c9d0e1a2b"
down_revision: Union[str, None] = "4290105c63b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add context_length to models
    op.add_column(
        "models",
        sa.Column("context_length", sa.Integer(), nullable=True),
    )
    # Add extracted_text to file_uploads
    op.add_column(
        "file_uploads",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("file_uploads", "extracted_text")
    op.drop_column("models", "context_length")
