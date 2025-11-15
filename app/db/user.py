from sqlmodel import Session, select
from app.models import User, UserCreate, UserLogin
from app.utils.security import hash_password, verify_password, encode_token
from datetime import datetime, timezone

def get_user_by_username(session: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    session_user = session.exec(statement).first()
    return session_user

def create_user(session: Session, user_in: UserCreate) -> User:
    if get_user_by_username(session, user_in.username):
        return None
    
    db_user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password)
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def set_user_last_login(session: Session, username: str) -> None:
    user = get_user_by_username(session, username)
    if user:
        user.last_login = datetime.now(timezone.utc)
        session.commit()