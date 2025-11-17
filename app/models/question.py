from sqlmodel import Field, SQLModel
from typing import Optional, Dict, Any
from sqlalchemy.types import JSON
from sqlalchemy import Column


class Question(SQLModel, table=True):
    __tablename__ = "question"
    
    id: int = Field(primary_key=True)
    type: Optional[str] = Field(default=None, max_length=100)
    content: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    answer: Optional[str] = Field(default=None)
    explanation: Optional[str] = Field(default=None)
