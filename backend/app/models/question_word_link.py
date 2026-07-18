from sqlmodel import Field, SQLModel
from typing import Optional
from sqlalchemy import Index


class QuestionWordLink(SQLModel, table=True):
    __tablename__ = "question_word_link"
    __table_args__ = (
        Index("ix_question_word_link_question_word", "question_id", "word_id"),
        Index("ix_question_word_link_word_question", "word_id", "question_id"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    word_id: int = Field(foreign_key="word.id")
