"""Merge heads

Revision ID: 3479c49728c6
Revises: 7951a2b4a1e9, c6c33b634925
Create Date: 2025-09-20 00:48:02.777925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3479c49728c6'
down_revision: Union[str, Sequence[str], None] = ('7951a2b4a1e9', 'c6c33b634925')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
