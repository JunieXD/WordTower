from sqlmodel import create_engine, Session, SQLModel
from app.utils.config import settings
from fastapi import Depends
from typing import Annotated
from app.models import *

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]
