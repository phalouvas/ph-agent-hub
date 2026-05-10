"""drop_prompt_visibility_and_selected_prompt_id

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-05-10

1. Drop selected_prompt_id column (and its FK) from sessions table.
   Prompts are now a frontend-only feature — no backend involvement.
2. Drop visibility column from prompts table.
   All prompts are now private to each user.
3. Alter the FK on skills.default_prompt_id to ON DELETE SET NULL
   so deleting a prompt doesn't break referenced skills.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_if_exists(table: str, column: str) -> str | None:
    """Find and drop a foreign key on *table*.*column*.  Returns the old
    FK name so it can be recreated in a downgrade, or None if none found."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table):
        if column in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
            return fk["name"]
    return None


def upgrade() -> None:
    # 1. Drop FK + column on sessions.selected_prompt_id.
    #    In MariaDB dropping the column also drops the FK, but we explicitly
    #    drop the FK first for clarity and portability.
    _drop_fk_if_exists("sessions", "selected_prompt_id")
    op.drop_column("sessions", "selected_prompt_id")

    # 2. Drop the FK on skills.default_prompt_id and recreate with
    #    ON DELETE SET NULL so deleting a prompt nullifies the reference.
    _drop_fk_if_exists("skills", "default_prompt_id")
    op.create_foreign_key(
        None,
        "skills",
        "prompts",
        ["default_prompt_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Drop the visibility column from prompts.
    #    MySQL ENUM is column-level, so dropping the column removes it.
    op.drop_column("prompts", "visibility")


def downgrade() -> None:
    # Restore prompts.visibility
    prompt_visibility_enum = sa.Enum(
        "private", "tenant", name="prompt_visibility_enum"
    )
    prompt_visibility_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "prompts",
        sa.Column(
            "visibility",
            prompt_visibility_enum,
            nullable=False,
            server_default="private",
        ),
    )

    # Revert skills FK to NO ACTION (remove ON DELETE SET NULL)
    _drop_fk_if_exists("skills", "default_prompt_id")
    op.create_foreign_key(
        None,
        "skills",
        "prompts",
        ["default_prompt_id"],
        ["id"],
    )

    # Restore sessions.selected_prompt_id
    op.add_column(
        "sessions",
        sa.Column(
            "selected_prompt_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        None,
        "sessions",
        "prompts",
        ["selected_prompt_id"],
        ["id"],
    )
