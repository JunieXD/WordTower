from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel


class SocialUserSummary(SQLModel):
    id: int
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    exp: int
    level: int
    max_floor: int
    social_status: str
    last_online_at: Optional[datetime] = None


class FriendMessagePreview(SQLModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    created_at: datetime
    read_at: Optional[datetime] = None


class FriendConversationRead(SQLModel):
    relation_id: int
    friend: SocialUserSummary
    unread_count: int = 0
    last_message: Optional[FriendMessagePreview] = None


class FriendRequestCreate(SQLModel):
    user_id: int


class FriendRequestRead(SQLModel):
    request_id: int
    created_at: datetime
    requester: SocialUserSummary


class SocialSearchUser(SQLModel):
    user: SocialUserSummary
    relation_status: str
    request_id: Optional[int] = None


class FriendMessageCreate(SQLModel):
    content: str


class FriendMessageRead(SQLModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    created_at: datetime
    read_at: Optional[datetime] = None
    is_mine: bool


class SocialChatRead(SQLModel):
    friend: SocialUserSummary
    messages: list[FriendMessageRead]
    has_more: bool


class FriendMessagesPage(SQLModel):
    messages: list[FriendMessageRead]
    has_more: bool


class UnreadSummary(SQLModel):
    total: int
