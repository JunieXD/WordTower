from sqlmodel import Field, SQLModel
from typing import Optional, Dict, Any
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column


class Question(SQLModel, table=True):
    __tablename__ = "question"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    type: Optional[str] = Field(default=None, max_length=100)
    content: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

class QuestionCheck(SQLModel):
    target_word: str
    chinese_sentence: str
    user_input: str
    
class QuestionAnswer(SQLModel):
    is_correct: bool
    
class QuestionReport(SQLModel):
    report: str
    
class QuestionRating(SQLModel):
    rating: int