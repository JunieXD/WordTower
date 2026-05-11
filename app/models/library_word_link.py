from sqlmodel import Field, SQLModel
from typing import Optional
from sqlalchemy import Index


class LibraryWordLink(SQLModel, table=True):
    __tablename__ = "library_word_link"
    __table_args__ = (
        Index("ix_library_word_link_library_word", "library_id", "word_id"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    library_id: int = Field(foreign_key="library.id")
    word_id: int = Field(foreign_key="word.id")
