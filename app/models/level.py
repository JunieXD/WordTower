from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from typing import Optional


class Level(SQLModel, table=True):
    __tablename__ = "level"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    floor: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
