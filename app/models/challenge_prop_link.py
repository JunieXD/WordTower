from sqlmodel import Field, SQLModel
from typing import Optional


class ChallengePropLink(SQLModel, table=True):
    __tablename__ = "challenge_prop_link"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id")
    prop_id: int = Field(foreign_key="prop.id")
    remaining_count: Optional[int] = Field(default=None)
