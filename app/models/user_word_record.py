from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from typing import Optional


class UserWordRecord(SQLModel, table=True):
    __tablename__ = "user_word_record"
    
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    word_id: int = Field(foreign_key="word.id")
    time: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    correct: Optional[bool] = Field(default=None)
