"""backfill_tool_categories

Set category for existing 13 tools based on their type.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Map tool type -> category
TYPE_TO_CATEGORY = {
    "currency_exchange": "financial",
    "web_search": "web",
    "fetch_url": "web",
    "rss_feed": "web",
    "wikipedia": "web",
    "erpnext": "enterprise",
    "membrane": "enterprise",
    "calculator": "utility",
    "datetime": "utility",
    "weather": "utility",
    "custom": "custom",
    "file_list": "system",
    "memory": "system",
}


def upgrade() -> None:
    for tool_type, category in TYPE_TO_CATEGORY.items():
        op.execute(
            f"UPDATE tools SET category = '{category}' WHERE type = '{tool_type}'"
        )


def downgrade() -> None:
    op.execute("UPDATE tools SET category = 'general'")
