from sqlmodel import Session, select
from app.models import User, UserCreate, UserQuestionRecord, Question
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

def user_question_answer(session: Session, user: User, question: Question, is_correct: bool) -> None:
    user_question_record = UserQuestionRecord(user_id=user.id, question_id=question.id, correct=is_correct)
    session.add(user_question_record)
    session.commit()
    
def user_question_report(session: Session, user: User, question: Question, report: str) -> None:
    select_statement = select(UserQuestionRecord).where(UserQuestionRecord.user_id == user.id).where(UserQuestionRecord.question_id == question.id)
    user_question_record = session.exec(select_statement).first()
    if user_question_record:
        user_question_record.report = report
        session.commit()
        
def user_question_rating(session: Session, user: User, question: Question, rating: int) -> None:
    select_statement = select(UserQuestionRecord).where(UserQuestionRecord.user_id == user.id).where(UserQuestionRecord.question_id == question.id)
    user_question_record = session.exec(select_statement).first()
    if user_question_record:
        user_question_record.rating = rating
        session.commit()
    
def update_user_max_floor(session: Session, user: User, max_floor: int) -> None:
    user.max_floor = max(user.max_floor, max_floor)
    session.commit()