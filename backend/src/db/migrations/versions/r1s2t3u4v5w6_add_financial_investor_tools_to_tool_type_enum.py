"""add_financial_investor_tools_to_tool_type_enum

Add market_overview, etf_data, stock_data, portfolio,
and sec_filings to the tool_type_enum.

Revision ID: r1s2t3u4v5w6
Revises: q2r3s4t5u6v7
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search',"
        "'fetch_url','weather','calculator','wikipedia','rss_feed',"
        "'currency_exchange','market_overview','etf_data',"
        "'stock_data','portfolio','sec_filings') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search',"
        "'fetch_url','weather','calculator','wikipedia','rss_feed',"
        "'currency_exchange') NOT NULL"
    )
