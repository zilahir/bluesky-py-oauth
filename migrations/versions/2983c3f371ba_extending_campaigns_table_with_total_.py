"""extending campaigns table with total followers to get, is_campaign_running, is_setup_job_running

Revision ID: 2983c3f371ba
Revises: 3814a29cf3f8
Create Date: 2025-09-24 22:22:35.916260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2983c3f371ba'
down_revision: Union[str, Sequence[str], None] = '3814a29cf3f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('campaigns', sa.Column('total_followers_to_get', sa.Integer(), nullable=True, default=0))
    op.add_column('campaigns', sa.Column('is_campaign_running', sa.Boolean(), nullable=False, default=False, server_default=sa.false()))
    op.add_column('campaigns', sa.Column('is_setup_job_running', sa.Boolean(), nullable=False, default=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('campaigns', 'is_setup_job_running')
    op.drop_column('campaigns', 'is_campaign_running')
    op.drop_column('campaigns', 'total_followers_to_get')
