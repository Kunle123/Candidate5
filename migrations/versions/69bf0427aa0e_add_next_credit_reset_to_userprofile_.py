"""add next_credit_reset to UserProfile for rolling credit resets

Revision ID: 69bf0427aa0e
Revises: 3479c49728c6
Create Date: 2025-09-24 15:24:36.540118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '69bf0427aa0e'
down_revision: Union[str, Sequence[str], None] = '3479c49728c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Only add the next_credit_reset column to users
    op.add_column('users', sa.Column('next_credit_reset', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Only remove the next_credit_reset column from users
    op.drop_column('users', 'next_credit_reset')
