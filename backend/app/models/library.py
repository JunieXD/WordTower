from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, String
from pydantic import ConfigDict
from app.models.word import Word

class LibraryVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"

class LibraryBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None)
    creator_id: Optional[int] = Field(default=None, foreign_key="user.id")
    visibility: LibraryVisibility = Field(default=LibraryVisibility.PRIVATE, sa_column=Column(String))
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    word_count: int = Field(default=0)
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class Library(LibraryBase, table=True):
    __tablename__ = "library"
    pass
    
class LibraryWithSelectAndPriority(LibraryBase):
    selected: bool = Field(default=False)
    priority: Optional[int] = Field(default=None)

class LibraryDetail(LibraryBase):
    model_config = ConfigDict(from_attributes=True)
    
    words: list[Word] = Field(default_factory=list)

class LibraryWithWordsId(LibraryBase):
    model_config = ConfigDict(from_attributes=True)
    
    words_id: list[int] = Field(default_factory=list)
    
    