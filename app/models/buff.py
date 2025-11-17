from sqlmodel import Field, SQLModel
from typing import Optional


class Buff(SQLModel, table=True):
    __tablename__ = "buff"
    
    id: int = Field(primary_key=True)
    name: str = Field(max_length=255, unique=True)
    description: Optional[str] = Field(default=None)
    duration: Optional[int] = Field(default=None)
    is_positive: bool = Field(default=True)
    icon_url: Optional[str] = Field(default=None, max_length=1024)
