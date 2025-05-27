"""add metadata_extracted and completed_with_errors to TaskStatusEnum

Revision ID: 5ca57b301e9d
Revises: 3da8d495710c
Create Date: 2025-05-27 23:09:57.893590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ca57b301e9d'
down_revision: Union[str, None] = '3da8d495710c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE taskstatusenum ADD VALUE IF NOT EXISTS 'metadata_extracted'")
    op.execute("ALTER TYPE taskstatusenum ADD VALUE IF NOT EXISTS 'completed_with_errors'")


def downgrade() -> None:
    """Downgrade schema."""
    # Downgrade for enums is not supported in PostgreSQL; this is a no-op.
    pass
