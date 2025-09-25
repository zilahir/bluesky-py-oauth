"""changing is_following_me and me_following from bool to date

Revision ID: 46ba0469f702
Revises: 292dfff09bc9
Create Date: 2025-09-25 11:19:38.719993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46ba0469f702'
down_revision: Union[str, Sequence[str], None] = '292dfff09bc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change me_following from boolean to datetime with timezone
    # First drop the column, then recreate it with new type
    op.drop_column('followers_to_get', 'me_following')
    op.add_column('followers_to_get', sa.Column('me_following', sa.DateTime(timezone=True), nullable=True))

    # Change is_following_me from boolean to datetime with timezone
    # First drop the column, then recreate it with new type
    op.drop_column('followers_to_get', 'is_following_me')
    op.add_column('followers_to_get', sa.Column('is_following_me', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert is_following_me back to boolean
    op.drop_column('followers_to_get', 'is_following_me')
    op.add_column('followers_to_get', sa.Column('is_following_me', sa.Boolean(), nullable=False, default=False))

    # Revert me_following back to boolean
    op.drop_column('followers_to_get', 'me_following')
    op.add_column('followers_to_get', sa.Column('me_following', sa.Boolean(), nullable=False, default=False))
