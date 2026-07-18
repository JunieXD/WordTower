from sqlmodel import Field, SQLModel
from typing import Optional
from sqlalchemy import Index


class UserLibrarySelect(SQLModel, table=True):
    __tablename__ = "user_library_select"
    __table_args__ = (
        Index("ix_user_library_select_user_library", "user_id", "library_id"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    library_id: int = Field(foreign_key="library.id")
    priority: Optional[int] = Field(default=None)

class PriorityItem(SQLModel):
    library_id: int
    priority: int

class UpdatePriorityRequest(SQLModel):
    priorities: list[PriorityItem]
