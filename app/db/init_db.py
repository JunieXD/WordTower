from sqlmodel import create_engine, SQLModel
from app.db.database import engine
from app.models import *

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

if __name__ == '__main__':
    create_db_and_tables()