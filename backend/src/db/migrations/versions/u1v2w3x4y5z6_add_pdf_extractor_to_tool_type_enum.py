"""add_pdf_extractor_to_tool_type_enum

Add pdf_extractor to the tool_type_enum.

Revision ID: u1v2w3x4y5z6
Revises: t5u6v7w8x9y0
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "y1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search',"
        "'fetch_url','weather','calculator','wikipedia','rss_feed',"
        "'currency_exchange','market_overview','etf_data',"
        "'stock_data','portfolio','sec_filings','pdf_extractor',"
        "'code_interpreter','sql_query','document_generation','browser',"
        "'rag_search','github','calendar','image_generation',"
        "'slack','email') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tools MODIFY COLUMN type "
        "ENUM('erpnext','membrane','custom','datetime','web_search',"
        "'fetch_url','weather','calculator','wikipedia','rss_feed',"
        "'currency_exchange','market_overview','etf_data',"
        "'stock_data','portfolio','sec_filings',"
        "'code_interpreter','sql_query','document_generation','browser',"
        "'rag_search','github','calendar','image_generation',"
        "'slack','email') NOT NULL"
    )
