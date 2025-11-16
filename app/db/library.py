from app.db.user import get_user_by_username
from app.models.library import Library
from sqlmodel import select
from app.db.database import Session
from app.models.library import LibraryVisibility


def get_library(session: Session, username: str) -> list[Library]:
    user = get_user_by_username(session, username)
    if user is None:
        return []
    statement = select(Library).where((Library.creator_id == user.id) | (Library.visibility == LibraryVisibility.PUBLIC))
    return session.exec(statement).all()


def create_library_(session: Session, library: Library) -> None:
    session.add(library)
    session.commit()