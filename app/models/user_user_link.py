from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, String


class FriendStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DELETED = "deleted"


class UserUserLink(SQLModel, table=True):
    __tablename__ = "user_user_link"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    friend_id: int = Field(foreign_key="user.id")
    status: FriendStatus = Field(default=FriendStatus.PENDING, sa_column=Column(String))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
