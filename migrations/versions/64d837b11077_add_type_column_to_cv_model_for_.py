"""Add type column to CV model for distinguishing CVs and cover letters

Revision ID: 64d837b11077
Revises: c69b4d295cad
Create Date: 2025-06-24 20:26:16.802568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64d837b11077'
down_revision: Union[str, None] = 'c69b4d295cad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add as nullable with default, fill, then alter to non-nullable
    op.add_column('cvs', sa.Column('type', sa.String(length=32), nullable=True, server_default='cv'))
    op.execute("UPDATE cvs SET type='cv' WHERE type IS NULL")
    op.alter_column('cvs', 'type', nullable=False, server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cvs', 'type')
