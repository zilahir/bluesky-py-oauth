"""create_campaign_execution_log_table

Revision ID: 412215757f14
Revises: 5937776593b2
Create Date: 2025-09-28 01:05:40.259875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '412215757f14'
down_revision: Union[str, Sequence[str], None] = '5937776593b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create campaign_execution_log table
    op.create_table(
        'campaign_execution_log',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('campaign_id', sa.Integer(), nullable=False, index=True),
        sa.Column('execution_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('follows_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unfollows_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('follow_backs_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('errors_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('execution_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop campaign_execution_log table
    op.drop_table('campaign_execution_log')
