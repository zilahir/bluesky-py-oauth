"""extending campaigns table with user_did

Revision ID: 3814a29cf3f8
Revises: 5725f2450fa8
Create Date: 2025-09-24 21:50:09.305016

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3814a29cf3f8"
down_revision: Union[str, Sequence[str], None] = "5725f2450fa8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("campaigns", sa.Column("user_did", sa.String(255), nullable=True))
    op.create_index("idx_campaigns_user_did", "campaigns", ["user_did"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_campaigns_user_did", "campaigns")
    op.drop_column("campaigns", "user_did")
