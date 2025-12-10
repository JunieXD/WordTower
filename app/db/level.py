from app.db.database import Session
from app.models.level import Level
from app.models.question import Question
from app.models.level_question_link import LevelQuestionLink
from app.db.challenge import current_challenge
from app.models.user import User
from app.models.challenge import Challenge
from sqlmodel import select

def new_level(session: Session, floor: int) -> Level:
    level = Level(floor=floor)
    session.add(level)
    session.commit()
    session.refresh(level)
    return level

def link_level_question(session: Session, level_id: int, question_id: int) -> None:
    statement = select(LevelQuestionLink).where(LevelQuestionLink.level_id == level_id).where(LevelQuestionLink.question_id == question_id)
    if session.exec(statement).first():
        return
    level_question_link = LevelQuestionLink(level_id=level_id, question_id=question_id)
    session.add(level_question_link)
    session.commit()

def get_current_level(session: Session, user: User) -> Level | None:
    challenge = current_challenge(session, user)
    if not challenge:
        return None
    statement = select(Level).where(Level.id == challenge.level_id)
    return session.exec(statement).first()