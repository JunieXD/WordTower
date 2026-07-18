from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class FriendMessage(SQLModel, table=True):
    __tablename__ = "friend_message"
    __table_args__ = (
        Index("ix_friend_message_pair_created_at", "sender_id", "recipient_id", "created_at"),
        Index("ix_friend_message_recipient_read_at", "recipient_id", "read_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: int = Field(foreign_key="user.id", index=True)
    recipient_id: int = Field(foreign_key="user.id", index=True)
    content: str = Field(max_length=2000)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: Optional[datetime] = Field(default=None)
