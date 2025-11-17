from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, String


class ChallengeStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Challenge(SQLModel, table=True):
    __tablename__ = "challenge"
    
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    level_id: int = Field(foreign_key="level.id")
    start_time: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = Field(default=None)
    end_hp: Optional[int] = Field(default=None)
    status: ChallengeStatus = Field(default=ChallengeStatus.IN_PROGRESS, sa_column=Column(String))
    exp_gained: int = Field(default=0)
    coins_gained: int = Field(default=0)
