from app.db.user import get_user_by_username
from app.models.library import Library
from sqlmodel import select
from app.db.database import Session
from app.models.library import LibraryVisibility


def get_library_by_name(session: Session, library_name: str, username: str) -> Library | None:
    user = get_user_by_username(session, username)
    if user is None:
        return None
    statement = select(Library).where((Library.name == library_name) & (Library.creator_id == user.id))
    return session.exec(statement).one_or_none()

def get_library(session: Session, username: str) -> list[Library]:
    user = get_user_by_username(session, username)
    if user is None:
        return []
    statement = select(Library).where((Library.creator_id == user.id) | (Library.visibility == LibraryVisibility.PUBLIC))
    return session.exec(statement).all()

def create_library_(session: Session, library: Library) -> None:
    session.add(library)
    session.commit()

def remove_library_(session: Session, library: Library) -> None:
    session.delete(library)
    session.commit()