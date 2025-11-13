from sqlmodel import Field, SQLModel
from typing import Optional


class Word(SQLModel, table=True):
    __tablename__ = "word"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = Field(max_length=255, unique=True)
    meaning: Optional[str] = Field(default=None)
    phonetic: Optional[str] = Field(default=None, max_length=255)
    part_of_speech: Optional[str] = Field(default=None, max_length=100)
    example: Optional[str] = Field(default=None)
    difficulty: Optional[int] = Field(default=None)
    tags: Optional[str] = Field(default=None, max_length=255)
