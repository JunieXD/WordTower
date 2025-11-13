from sqlmodel import create_engine, Session, SQLModel
from app.utils.config import settings
from fastapi import Depends
from typing import Annotated
from app.models import *

engine = create_engine(settings.DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

SessionDep = Annotated[Session, Depends(get_session)]