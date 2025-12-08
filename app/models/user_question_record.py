from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from typing import Optional


class UserQuestionRecord(SQLModel, table=True):
    __tablename__ = "user_question_record"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    question_id: int = Field(foreign_key="question.id")
    time: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    correct: Optional[bool] = Field(default=None)
    report: Optional[str] = Field(default=None)
    rating: Optional[int] = Field(default=None)
