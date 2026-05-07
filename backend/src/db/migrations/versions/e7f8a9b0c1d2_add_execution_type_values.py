"""Add prompt_based and workflow_based to skill_execution_enum

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-05-07

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE skills MODIFY COLUMN execution_type "
        "ENUM('agent','workflow','prompt_based','workflow_based') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE skills MODIFY COLUMN execution_type "
        "ENUM('agent','workflow') NOT NULL"
    )
