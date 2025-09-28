"""add_campaign_tracking_columns_to_followers_to_get

Revision ID: 5937776593b2
Revises: 470e19614642
Create Date: 2025-09-28 01:04:43.985183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5937776593b2'
down_revision: Union[str, Sequence[str], None] = '470e19614642'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to followers_to_get table
    op.add_column('followers_to_get', sa.Column('unfollowed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('followers_to_get', sa.Column('follow_attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('followers_to_get', sa.Column('unfollow_attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('followers_to_get', sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('followers_to_get', sa.Column('status', sa.String(50), nullable=False, server_default='ready_to_follow'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the added columns
    op.drop_column('followers_to_get', 'status')
    op.drop_column('followers_to_get', 'last_checked_at')
    op.drop_column('followers_to_get', 'unfollow_attempt_count')
    op.drop_column('followers_to_get', 'follow_attempt_count')
    op.drop_column('followers_to_get', 'unfollowed_at')
