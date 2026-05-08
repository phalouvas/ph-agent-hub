"""add_user_groups_and_model_access_control

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-05-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_public to models
    op.add_column(
        'models',
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )

    # 2. Add default_model_id to users
    op.add_column(
        'users',
        sa.Column('default_model_id', mysql.CHAR(length=36), nullable=True),
    )
    op.create_foreign_key(
        None, 'users', 'models', ['default_model_id'], ['id']
    )

    # 3. Create user_groups table
    op.create_table(
        'user_groups',
        sa.Column('id', mysql.CHAR(length=36), nullable=False),
        sa.Column('tenant_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. Create user_group_members table
    op.create_table(
        'user_group_members',
        sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('group_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['group_id'], ['user_groups.id']),
        sa.PrimaryKeyConstraint('user_id', 'group_id'),
    )

    # 5. Create model_groups table
    op.create_table(
        'model_groups',
        sa.Column('model_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('group_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['model_id'], ['models.id']),
        sa.ForeignKeyConstraint(['group_id'], ['user_groups.id']),
        sa.PrimaryKeyConstraint('model_id', 'group_id'),
    )


def downgrade() -> None:
    op.drop_table('model_groups')
    op.drop_table('user_group_members')
    op.drop_table('user_groups')
    op.drop_constraint('users_ibfk_2', 'users', type_='foreignkey')
    op.drop_column('users', 'default_model_id')
    op.drop_column('models', 'is_public')
