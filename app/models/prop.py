from sqlmodel import Field, SQLModel
from typing import Optional


class Prop(SQLModel, table=True):
    __tablename__ = "prop"
    
    id: int = Field(primary_key=True)
    name: str = Field(max_length=255, unique=True)
    description: Optional[str] = Field(default=None)
    rarity: int = Field(default=1)
    icon_url: Optional[str] = Field(default=None, max_length=1024)
