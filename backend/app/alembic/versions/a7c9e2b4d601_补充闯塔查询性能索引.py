"""补充闯塔查询性能索引

Revision ID: a7c9e2b4d601
Revises: 8f2f3b57b2aa
Create Date: 2026-05-11 00:00:00.000000
"""

from alembic import op

revision = "a7c9e2b4d601"
down_revision = "8f2f3b57b2aa"
branch_labels = None
depends_on = None


def _create_index(name: str, table_name: str, columns: list[str], postgresql_sql: str | None = None) -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        sql = postgresql_sql or (
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
            f"ON {table_name} ({', '.join(columns)})"
        )
        with context.autocommit_block():
            op.execute(sql)
        return

    op.create_index(name, table_name, columns)


def _drop_index(name: str, table_name: str) -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        with context.autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
        return

    op.drop_index(name, table_name=table_name)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    _create_index(
        "ix_user_question_record_user_question_time",
        "user_question_record",
        ["user_id", "question_id", "time"],
    )
    _create_index(
        "ix_user_question_record_user_time",
        "user_question_record",
        ["user_id", "time"],
    )
    _create_index(
        "ix_question_word_link_question_word",
        "question_word_link",
        ["question_id", "word_id"],
    )
    _create_index(
        "ix_question_word_link_word_question",
        "question_word_link",
        ["word_id", "question_id"],
    )
    _create_index(
        "ix_library_word_link_library_word",
        "library_word_link",
        ["library_id", "word_id"],
    )
    _create_index(
        "ix_user_library_select_user_library",
        "user_library_select",
        ["user_id", "library_id"],
    )
    _create_index("ix_question_type_id", "question", ["type", "id"])
    _create_index(
        "ix_challenge_user_status_start_time",
        "challenge",
        ["user_id", "status", "start_time"],
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_challenge_user_status_start_time "
        "ON challenge (user_id, status, start_time DESC)",
    )
    _create_index(
        "ix_challenge_user_start_time",
        "challenge",
        ["user_id", "start_time"],
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_challenge_user_start_time "
        "ON challenge (user_id, start_time DESC)",
    )
    _create_index(
        "ix_level_question_link_level_question",
        "level_question_link",
        ["level_id", "question_id"],
    )
    _create_index(
        "ix_daily_challenge_run_day_rank",
        "daily_challenge_run",
        ["day_id", "best_floor", "best_floor_reached_at", "started_at", "user_id"],
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_daily_challenge_run_day_rank "
        "ON daily_challenge_run (day_id, best_floor DESC, best_floor_reached_at ASC, started_at ASC, user_id ASC)",
    )
    _create_index(
        "ix_daily_challenge_run_user_status_started",
        "daily_challenge_run",
        ["user_id", "status", "started_at"],
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_daily_challenge_run_user_status_started "
        "ON daily_challenge_run (user_id, status, started_at DESC)",
    )

    if context.dialect.name == "postgresql":
        _create_index(
            "ix_word_tags_trgm",
            "word",
            ["tags"],
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_word_tags_trgm "
            "ON word USING gin (tags gin_trgm_ops) WHERE tags IS NOT NULL",
        )


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        _drop_index("ix_word_tags_trgm", "word")

    _drop_index("ix_daily_challenge_run_user_status_started", "daily_challenge_run")
    _drop_index("ix_daily_challenge_run_day_rank", "daily_challenge_run")
    _drop_index("ix_level_question_link_level_question", "level_question_link")
    _drop_index("ix_challenge_user_start_time", "challenge")
    _drop_index("ix_challenge_user_status_start_time", "challenge")
    _drop_index("ix_question_type_id", "question")
    _drop_index("ix_user_library_select_user_library", "user_library_select")
    _drop_index("ix_library_word_link_library_word", "library_word_link")
    _drop_index("ix_question_word_link_word_question", "question_word_link")
    _drop_index("ix_question_word_link_question_word", "question_word_link")
    _drop_index("ix_user_question_record_user_time", "user_question_record")
    _drop_index("ix_user_question_record_user_question_time", "user_question_record")
