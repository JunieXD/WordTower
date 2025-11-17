from sqlmodel import Field, SQLModel
from typing import Optional


class QuestionWordLink(SQLModel, table=True):
    __tablename__ = "question_word_link"
    
    id: int = Field(primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    word_id: int = Field(foreign_key="word.id")
