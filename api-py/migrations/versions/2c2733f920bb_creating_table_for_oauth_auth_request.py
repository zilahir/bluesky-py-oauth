"""creating table for oauth_auth_request

Revision ID: 2c2733f920bb
Revises: 28b09521042d
Create Date: 2025-09-24 18:16:42.946777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c2733f920bb'
down_revision: Union[str, Sequence[str], None] = '28b09521042d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'oauth_auth_request',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('state', sa.String(255), nullable=False, unique=True),
        sa.Column('authserver_iss', sa.String(255), nullable=False),
        sa.Column('did', sa.String(255), nullable=True),
        sa.Column('handle', sa.String(255), nullable=True),
        sa.Column('pds_url', sa.String(255), nullable=True),
        sa.Column('pkce_verifier', sa.String(255), nullable=False),
        sa.Column('scope', sa.String(255), nullable=True),
        sa.Column('dpop_authserver_nonce', sa.String(255), nullable=True),
        sa.Column('dpop_private_jwk', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('oauth_auth_request')
