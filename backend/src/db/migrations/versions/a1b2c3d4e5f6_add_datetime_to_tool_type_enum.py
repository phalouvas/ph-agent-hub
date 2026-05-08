"""add_datetime_to_tool_type_enum

Revision ID: a1b2c3d4e5f6
Revises: 5db963e14b25
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5db963e14b25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom') NOT NULL"
    )
