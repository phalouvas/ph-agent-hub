"""drop_prompt_visibility_and_selected_prompt_id

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-05-10

1. Drop selected_prompt_id column (and its FK) from sessions table.
   Prompts are now a frontend-only feature — no backend involvement.
2. Drop visibility column (and its enum) from prompts table.
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


def upgrade() -> None:
    # 1. Drop the FK and column on sessions.selected_prompt_id
    # MySQL auto-names constraints; use raw SQL to find and drop it.
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sessions'
              AND COLUMN_NAME = 'selected_prompt_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        );
        SET @drop_sql = IF(@fk_name IS NOT NULL,
            CONCAT('ALTER TABLE sessions DROP FOREIGN KEY ', @fk_name), 'SELECT 1');
        PREPARE stmt FROM @drop_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    """)
    op.drop_column("sessions", "selected_prompt_id")

    # 2. Drop the FK on skills.default_prompt_id and recreate with ON DELETE SET NULL
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'skills'
              AND COLUMN_NAME = 'default_prompt_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        );
        SET @drop_sql = IF(@fk_name IS NOT NULL,
            CONCAT('ALTER TABLE skills DROP FOREIGN KEY ', @fk_name), 'SELECT 1');
        PREPARE stmt FROM @drop_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    """)
    op.create_foreign_key(
        None,
        "skills",
        "prompts",
        ["default_prompt_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Drop the visibility column (the enum type is auto-dropped by MySQL)
    op.execute("ALTER TABLE prompts DROP COLUMN visibility")


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
    op.execute("""
        SET @fk_name = (
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'skills'
              AND COLUMN_NAME = 'default_prompt_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
        );
        SET @drop_sql = IF(@fk_name IS NOT NULL,
            CONCAT('ALTER TABLE skills DROP FOREIGN KEY ', @fk_name), 'SELECT 1');
        PREPARE stmt FROM @drop_sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    """)
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
