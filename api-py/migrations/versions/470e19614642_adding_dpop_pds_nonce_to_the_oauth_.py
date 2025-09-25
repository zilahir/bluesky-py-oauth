"""adding dpop_pds_nonce to the oauth_session table

Revision ID: 470e19614642
Revises: 46ba0469f702
Create Date: 2025-09-25 19:31:15.193772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '470e19614642'
down_revision: Union[str, Sequence[str], None] = '46ba0469f702'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add dpop_pds_nonce column to oauth_session table
    op.add_column('oauth_session', sa.Column('dpop_pds_nonce', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove dpop_pds_nonce column from oauth_session table
    op.drop_column('oauth_session', 'dpop_pds_nonce')
