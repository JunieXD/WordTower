from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, String


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"

class UserBase(SQLModel):
    id: int = Field(primary_key=True)
    nickname: Optional[str] = Field(default=None, max_length=255)
    username: str = Field(max_length=255, unique=True)
    email: Optional[str] = Field(default=None, max_length=255, unique=True)
    avatar_url: Optional[str] = Field(default=None, max_length=1024)
    exp: int = Field(default=0)
    coins: int = Field(default=0)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = Field(default=None)
    status: UserStatus = Field(default=UserStatus.ACTIVE, sa_column=Column(String))
    max_hp: int = Field(default=100)
    attack: int = Field(default=10)
    crit_rate: float = Field(default=0.0)
    role: str = Field(default="player", max_length=50)
    max_floor: int = Field(default=0)


class User(UserBase, table=True):
    __tablename__ = "user"
    password_hash: str = Field(max_length=255)

class UserCreate(UserBase):
    password: str = Field(max_length=255)

class UserRead(UserBase):
    pass

class UserLogin(UserBase):
    password: str = Field(max_length=255)