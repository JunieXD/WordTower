from sqlmodel import Field, SQLModel


class UserLibrarySelect(SQLModel, table=True):
    __tablename__ = "user_library_select"
    
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    library_id: int = Field(foreign_key="library.id")
