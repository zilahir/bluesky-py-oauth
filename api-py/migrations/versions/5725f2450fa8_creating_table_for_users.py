"""creating table for users

Revision ID: 5725f2450fa8
Revises: 0f00ccb76d46
Create Date: 2025-09-24 21:17:54.211010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5725f2450fa8'
down_revision: Union[str, Sequence[str], None] = '0f00ccb76d46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('did', sa.String(255), nullable=False),
        sa.Column('handle', sa.String(255), nullable=False),
        sa.Column('avatar', sa.String(512), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('did'),
        sa.Index('idx_users_did', 'did'),
        sa.Index('idx_users_handle', 'handle')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
