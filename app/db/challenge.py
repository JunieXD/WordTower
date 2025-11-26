from sqlmodel import select
from app.db.database import Session
from app.models.user import User
from app.models.challenge import Challenge
from app.models.level import Level


def get_current_floor(session: Session, user: User) -> int | None:
    """获取用户当前所在楼层（最新的未结束挑战）"""
    statement = (
        select(Level.floor)
        .join(Challenge, Level.id == Challenge.level_id)
        .where(Challenge.user_id == user.id)
        .where(Challenge.start_time.isnot(None))
        .where(Challenge.end_time.is_(None))
        .order_by(Challenge.start_time.desc())
        .limit(1)
    )
    result = session.exec(statement).first()
    return result

def get_current_hp(session: Session, user: User) -> int | None:
    """获取用户当前生命值（最新的未结束挑战的剩余生命值）"""
    statement = (
        select(Challenge.end_hp)
        .where(Challenge.user_id == user.id)
        .where(Challenge.start_time.isnot(None))
        .where(Challenge.end_time.is_(None))
        .order_by(Challenge.start_time.desc())
        .limit(1)
    )
    result = session.exec(statement).first()
    return result