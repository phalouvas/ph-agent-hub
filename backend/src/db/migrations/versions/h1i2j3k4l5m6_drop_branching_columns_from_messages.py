"""drop_branching_columns_from_messages

Revision ID: h1i2j3k4l5m6
Revises: f0a1b2c3d4e5
Create Date: 2026-05-09

Remove parent_message_id and branch_index from the messages table.
Branching was removed as a feature — conversations are now linear.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("messages_ibfk_2", "messages", type_="foreignkey")
    op.drop_column("messages", "parent_message_id")
    op.drop_column("messages", "branch_index")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("parent_message_id", sa.CHAR(36), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("branch_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_foreign_key(
        "messages_ibfk_2",
        "messages",
        "messages",
        ["parent_message_id"],
        ["id"],
    )
