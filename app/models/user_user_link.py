from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Index, String


class FriendStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DELETED = "deleted"


class UserUserLink(SQLModel, table=True):
    __tablename__ = "user_user_link"
    __table_args__ = (
        Index("ix_user_user_link_pair", "user_id", "friend_id"),
        Index("ix_user_user_link_friend_status", "friend_id", "status"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    friend_id: int = Field(foreign_key="user.id")
    status: FriendStatus = Field(default=FriendStatus.PENDING, sa_column=Column(String))
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
