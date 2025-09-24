"""creating table for oauth_session

Revision ID: 0f00ccb76d46
Revises: 2c2733f920bb
Create Date: 2025-09-24 18:21:07.937099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f00ccb76d46'
down_revision: Union[str, Sequence[str], None] = '2c2733f920bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('oauth_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('did', sa.String(length=255), nullable=False),
        sa.Column('handle', sa.String(length=255), nullable=False),
        sa.Column('pds_url', sa.String(length=512), nullable=False),
        sa.Column('authserver_iss', sa.String(length=512), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('dpop_authserver_nonce', sa.String(length=512), nullable=True),
        sa.Column('dpop_private_jwk', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('oauth_session')
