"""优化单词搜索索引

Revision ID: 8f2f3b57b2aa
Revises: 5bb6d1f1c0ab
Create Date: 2026-04-09 17:05:00.000000
"""

from alembic import op


revision = "8f2f3b57b2aa"
down_revision = "5bb6d1f1c0ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_word_lower_text_trgm_clean
        ON word USING gin (lower(text) gin_trgm_ops)
        WHERE text NOT LIKE '% %'
          AND text NOT LIKE '%.%'
          AND text NOT LIKE '%''%';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_word_lower_text_prefix_clean
        ON word (lower(text) text_pattern_ops)
        WHERE text NOT LIKE '% %'
          AND text NOT LIKE '%.%'
          AND text NOT LIKE '%''%';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_word_lower_text_prefix_clean")
    op.execute("DROP INDEX IF EXISTS ix_word_lower_text_trgm_clean")
