"""creating followers_to_get table

Revision ID: 292dfff09bc9
Revises: 2983c3f371ba
Create Date: 2025-09-24 22:56:08.147521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '292dfff09bc9'
down_revision: Union[str, Sequence[str], None] = '2983c3f371ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'followers_to_get',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('account_handle', sa.String(255), nullable=False),
        sa.Column('me_following', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_following_me', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.Index('idx_followers_to_get_campaign_id', 'campaign_id'),
        sa.Index('idx_followers_to_get_account_handle', 'account_handle')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('followers_to_get')
