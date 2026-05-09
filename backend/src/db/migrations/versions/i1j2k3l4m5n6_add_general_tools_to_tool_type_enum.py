"""add_general_tools_to_tool_type_enum

Add fetch_url, weather, calculator, wikipedia, rss_feed,
and currency_exchange to the tool_type_enum.

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "i1j2k3l4m5n6"
down_revision: Union[str, None] = "h1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search',"
        "'fetch_url','weather','calculator','wikipedia','rss_feed',"
        "'currency_exchange') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search') NOT NULL"
    )
