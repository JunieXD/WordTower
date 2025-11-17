from sqlmodel import Field, SQLModel
from typing import Optional


class LevelQuestionLink(SQLModel, table=True):
    __tablename__ = "level_question_link"
    
    id: int = Field(primary_key=True)
    level_id: int = Field(foreign_key="level.id")
    question_id: int = Field(foreign_key="question.id")
    order_index: Optional[int] = Field(default=None)
