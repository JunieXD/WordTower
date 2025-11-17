from sqlmodel import Field, SQLModel
from typing import Optional


class LibraryWordLink(SQLModel, table=True):
    __tablename__ = "library_word_link"
    
    id: int = Field(primary_key=True)
    library_id: int = Field(foreign_key="library.id")
    word_id: int = Field(foreign_key="word.id")
