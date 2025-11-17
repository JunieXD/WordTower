from sqlmodel import Field, SQLModel
from typing import Optional


class ChallengeBuffLink(SQLModel, table=True):
    __tablename__ = "challenge_buff_link"
    
    id: int = Field(primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id")
    buff_id: int = Field(foreign_key="buff.id")
    remaining_duration: Optional[int] = Field(default=None)
