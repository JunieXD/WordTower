"""新增每日挑战相关表

Revision ID: 5bb6d1f1c0ab
Revises: 1e4d6f8b9a21
Create Date: 2026-04-06 23:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "5bb6d1f1c0ab"
down_revision = "1e4d6f8b9a21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_challenge_day",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_key", sa.String(length=32), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_tags", sa.JSON(), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_key"),
    )
    op.create_index(op.f("ix_daily_challenge_day_day_key"), "daily_challenge_day", ["day_key"], unique=False)

    op.create_table(
        "daily_challenge_floor_question",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=100), nullable=True),
        sa.Column("word_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["day_id"], ["daily_challenge_day.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "floor", "question_index", name="uq_daily_floor_question_position"),
    )
    op.create_index(op.f("ix_daily_challenge_floor_question_day_id"), "daily_challenge_floor_question", ["day_id"], unique=False)
    op.create_index(op.f("ix_daily_challenge_floor_question_floor"), "daily_challenge_floor_question", ["floor"], unique=False)

    op.create_table(
        "daily_challenge_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("current_floor", sa.Integer(), nullable=False),
        sa.Column("current_question_index", sa.Integer(), nullable=False),
        sa.Column("current_hp", sa.Integer(), nullable=False),
        sa.Column("current_enemy_hp", sa.Integer(), nullable=False),
        sa.Column("best_floor", sa.Integer(), nullable=False),
        sa.Column("best_floor_reached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["day_id"], ["daily_challenge_day.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "user_id", name="uq_daily_run_day_user"),
    )
    op.create_index(op.f("ix_daily_challenge_run_day_id"), "daily_challenge_run", ["day_id"], unique=False)
    op.create_index(op.f("ix_daily_challenge_run_status"), "daily_challenge_run", ["status"], unique=False)
    op.create_index(op.f("ix_daily_challenge_run_user_id"), "daily_challenge_run", ["user_id"], unique=False)

    op.create_table(
        "daily_challenge_answer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_detail", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["daily_challenge_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "question_id", name="uq_daily_answer_run_question"),
    )
    op.create_index(op.f("ix_daily_challenge_answer_floor"), "daily_challenge_answer", ["floor"], unique=False)
    op.create_index(op.f("ix_daily_challenge_answer_question_id"), "daily_challenge_answer", ["question_id"], unique=False)
    op.create_index(op.f("ix_daily_challenge_answer_run_id"), "daily_challenge_answer", ["run_id"], unique=False)

    op.create_table(
        "daily_challenge_used_word",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["day_id"], ["daily_challenge_day.id"]),
        sa.ForeignKeyConstraint(["word_id"], ["word.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "word_id", name="uq_daily_used_word"),
    )
    op.create_index(op.f("ix_daily_challenge_used_word_day_id"), "daily_challenge_used_word", ["day_id"], unique=False)
    op.create_index(op.f("ix_daily_challenge_used_word_floor"), "daily_challenge_used_word", ["floor"], unique=False)
    op.create_index(op.f("ix_daily_challenge_used_word_word_id"), "daily_challenge_used_word", ["word_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_challenge_used_word_word_id"), table_name="daily_challenge_used_word")
    op.drop_index(op.f("ix_daily_challenge_used_word_floor"), table_name="daily_challenge_used_word")
    op.drop_index(op.f("ix_daily_challenge_used_word_day_id"), table_name="daily_challenge_used_word")
    op.drop_table("daily_challenge_used_word")

    op.drop_index(op.f("ix_daily_challenge_answer_run_id"), table_name="daily_challenge_answer")
    op.drop_index(op.f("ix_daily_challenge_answer_question_id"), table_name="daily_challenge_answer")
    op.drop_index(op.f("ix_daily_challenge_answer_floor"), table_name="daily_challenge_answer")
    op.drop_table("daily_challenge_answer")

    op.drop_index(op.f("ix_daily_challenge_run_user_id"), table_name="daily_challenge_run")
    op.drop_index(op.f("ix_daily_challenge_run_status"), table_name="daily_challenge_run")
    op.drop_index(op.f("ix_daily_challenge_run_day_id"), table_name="daily_challenge_run")
    op.drop_table("daily_challenge_run")

    op.drop_index(op.f("ix_daily_challenge_floor_question_floor"), table_name="daily_challenge_floor_question")
    op.drop_index(op.f("ix_daily_challenge_floor_question_day_id"), table_name="daily_challenge_floor_question")
    op.drop_table("daily_challenge_floor_question")

    op.drop_index(op.f("ix_daily_challenge_day_day_key"), table_name="daily_challenge_day")
    op.drop_table("daily_challenge_day")
