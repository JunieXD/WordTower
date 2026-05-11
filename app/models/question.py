from sqlmodel import Field, SQLModel
from typing import Optional, Dict, Any
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Index


class Question(SQLModel, table=True):
    __tablename__ = "question"
    __table_args__ = (
        Index("ix_question_type_id", "type", "id"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    type: Optional[str] = Field(default=None, max_length=100)
    content: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

class QuestionCheck(SQLModel):
    target_word: str
    chinese_sentence: str
    user_input: str
    
class QuestionAnswer(SQLModel):
    is_correct: bool
    level_id: int
    answer_detail: Optional[Dict[str, Any]] = None
    
class QuestionReport(SQLModel):
    report: str
    
class QuestionRating(SQLModel):
    rating: int
