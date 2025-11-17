from sqlmodel import Session, select
from app.models import User, UserCreate
from app.utils.security import hash_password
from datetime import datetime, timezone

def get_user_by_username(session: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    return session.exec(statement).one_or_none()

def create_user(session: Session, user_in: UserCreate) -> None:
    if get_user_by_username(session, user_in.username):
        return None
    
    db_user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password)
    )
    session.add(db_user)
    session.commit()

def set_user_last_login(session: Session, username: str) -> None:
    user = get_user_by_username(session, username)
    if user:
        user.last_login = datetime.now(timezone.utc)
        session.commit()