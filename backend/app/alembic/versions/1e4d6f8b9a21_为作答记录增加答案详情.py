"""为作答记录增加答案详情

Revision ID: 1e4d6f8b9a21
Revises: c1c4e4a6f8b2
Create Date: 2026-04-06 15:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1e4d6f8b9a21"
down_revision = "c1c4e4a6f8b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_question_record", sa.Column("answer_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_question_record", "answer_detail")
