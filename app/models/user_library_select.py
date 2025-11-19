from sqlmodel import Field, SQLModel
from typing import Optional


class UserLibrarySelect(SQLModel, table=True):
    __tablename__ = "user_library_select"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    library_id: int = Field(foreign_key="library.id")
    priority: Optional[int] = Field(default=None)

class PriorityItem(SQLModel):
    library_id: int
    priority: int

class UpdatePriorityRequest(SQLModel):
    priorities: list[PriorityItem]