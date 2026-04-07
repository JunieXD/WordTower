from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON
from sqlalchemy import Column, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from sqlalchemy.dialects.postgresql import JSONB


def _json_type():
    return JSONB().with_variant(JSON(), "sqlite")


class DailyChallengeRunStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    DEAD = "dead"
    COMPLETED_EXHAUSTED = "completed_exhausted"


class DailyChallengeQuestionType(str, Enum):
    CONTEXT_GUESS = "context_guess"
    CLOZE_TEST = "cloze_test"
    KEYWORD_TRANSLATION = "keyword_translation"


class DailyChallengeDay(SQLModel, table=True):
    __tablename__ = "daily_challenge_day"

    id: Optional[int] = Field(default=None, primary_key=True)
    day_key: str = Field(index=True, unique=True, max_length=32)
    opens_at: datetime
    closes_at: datetime
    source_tags: list[str] = Field(default_factory=list, sa_column=Column(_json_type()))
    config_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(_json_type()))
    created_at: datetime


class DailyChallengeFloorQuestion(SQLModel, table=True):
    __tablename__ = "daily_challenge_floor_question"
    __table_args__ = (
        UniqueConstraint("day_id", "floor", "question_index", name="uq_daily_floor_question_position"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    day_id: int = Field(foreign_key="daily_challenge_day.id", index=True)
    floor: int = Field(index=True)
    question_index: int = Field(default=1)
    question_id: int = Field(foreign_key="question.id")
    question_type: str = Field(sa_column=Column(String(100)))
    word_ids: list[int] = Field(default_factory=list, sa_column=Column(_json_type()))
    created_at: datetime


class DailyChallengeRun(SQLModel, table=True):
    __tablename__ = "daily_challenge_run"
    __table_args__ = (
        UniqueConstraint("day_id", "user_id", name="uq_daily_run_day_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    day_id: int = Field(foreign_key="daily_challenge_day.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    status: DailyChallengeRunStatus = Field(
        default=DailyChallengeRunStatus.IN_PROGRESS,
        sa_column=Column(String(32), index=True),
    )
    current_floor: int = Field(default=1)
    current_question_index: int = Field(default=1)
    current_hp: int = Field(default=100)
    current_enemy_hp: int = Field(default=30)
    best_floor: int = Field(default=1)
    best_floor_reached_at: datetime
    started_at: datetime
    ended_at: Optional[datetime] = None


class DailyChallengeAnswer(SQLModel, table=True):
    __tablename__ = "daily_challenge_answer"
    __table_args__ = (
        UniqueConstraint("run_id", "question_id", name="uq_daily_answer_run_question"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="daily_challenge_run.id", index=True)
    floor: int = Field(index=True)
    question_index: int = Field(default=1)
    question_id: int = Field(foreign_key="question.id", index=True)
    answer_detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(_json_type()))
    is_correct: bool
    answered_at: datetime


class DailyChallengeUsedWord(SQLModel, table=True):
    __tablename__ = "daily_challenge_used_word"
    __table_args__ = (
        UniqueConstraint("day_id", "word_id", name="uq_daily_used_word"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    day_id: int = Field(foreign_key="daily_challenge_day.id", index=True)
    floor: int = Field(index=True)
    question_index: int = Field(default=1)
    word_id: int = Field(foreign_key="word.id", index=True)
    created_at: datetime


class DailyChallengeQuestionRead(SQLModel):
    question_id: int
    floor: int
    question_index: int
    type: str
    content: dict[str, Any]


class DailyChallengeAnswerResultRead(SQLModel):
    is_correct: bool
    detail: dict[str, Any] = Field(default_factory=dict)


class DailyChallengeStateRead(SQLModel):
    run_id: int
    day_key: str
    status: str
    current_floor: int
    current_question_index: int
    current_hp: int
    current_enemy_hp: int
    player_max_hp: int
    player_attack: int
    enemy_max_hp: int
    enemy_attack: int
    heal_every_floors: int
    heal_amount: int
    best_floor: int
    best_floor_reached_at: datetime
    started_at: datetime
    ended_at: Optional[datetime] = None
    question: Optional[DailyChallengeQuestionRead] = None
    answer_result: Optional[DailyChallengeAnswerResultRead] = None


class DailyChallengeLeaderboardEntryRead(SQLModel):
    rank: int
    user_id: int
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    best_floor: int
    best_floor_reached_at: Optional[datetime] = None
    started_at: datetime
    status: str
    is_current_user: bool = False


class DailyChallengeOverviewRead(SQLModel):
    day_key: str
    opens_at: datetime
    closes_at: datetime
    seconds_until_reset: int
    user_status: str
    today_best_floor: Optional[int] = None
    active_run: Optional[DailyChallengeStateRead] = None
    leaderboard: list[DailyChallengeLeaderboardEntryRead] = Field(default_factory=list)
    current_user_rank: Optional[int] = None
    current_user_entry: Optional[DailyChallengeLeaderboardEntryRead] = None


class DailyChallengeAnswerSubmit(SQLModel):
    question_id: int
    selected_option: Optional[str] = None
    selected_sequence: Optional[list[str]] = None
    user_input: Optional[str] = None
    is_correct: Optional[bool] = None
    answer_detail: Optional[dict[str, Any]] = None
