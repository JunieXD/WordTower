from datetime import datetime
from typing import Any, Optional

from sqlmodel import SQLModel


class HistoryAnswerRead(SQLModel):
    id: int
    answered_at: Optional[datetime] = None
    correct: Optional[bool] = None
    answer_detail: Optional[dict[str, Any]] = None
    rating: Optional[int] = None
    report: Optional[str] = None


class HistoryQuestionRead(SQLModel):
    question_id: int
    order_index: int
    floor: int
    question_index: Optional[int] = None
    level_id: Optional[int] = None
    question_type: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    first_answer: Optional[HistoryAnswerRead] = None


class HistoryRunSummary(SQLModel):
    run_ref: str
    run_id: int
    mode: str
    status: str
    day_key: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    highest_floor: int = 0
    current_floor: Optional[int] = None
    total_exp: int = 0
    total_coins: int = 0
    question_count: int = 0
    last_hp: Optional[int] = None


class HistoryRunDetail(SQLModel):
    run: HistoryRunSummary
    questions: list[HistoryQuestionRead]
