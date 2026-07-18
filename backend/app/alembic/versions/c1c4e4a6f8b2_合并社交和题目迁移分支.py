"""合并社交和题目迁移分支

Revision ID: c1c4e4a6f8b2
Revises: 75b814fb7d86, 9df4c0d8d2b1
Create Date: 2026-04-05 23:50:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'c1c4e4a6f8b2'
down_revision: Union[str, Sequence[str], None] = ('75b814fb7d86', '9df4c0d8d2b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
