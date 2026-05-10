"""drop_routing_priority_from_models

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-05-10

Remove the routing_priority column from the models table.
This feature was never implemented — the field is unused.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i1j2k3l4m5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("models", "routing_priority")


def downgrade() -> None:
    op.add_column(
        "models",
        sa.Column(
            "routing_priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
