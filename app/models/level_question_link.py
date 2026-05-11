from sqlmodel import Field, SQLModel
from typing import Optional
from sqlalchemy import Index


class LevelQuestionLink(SQLModel, table=True):
    __tablename__ = "level_question_link"
    __table_args__ = (
        Index("ix_level_question_link_level_question", "level_id", "question_id"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    level_id: int = Field(foreign_key="level.id")
    question_id: int = Field(foreign_key="question.id")
    order_index: Optional[int] = Field(default=None)
