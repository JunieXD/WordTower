from sqlmodel import select
from app.db.database import Session
from app.models.user import User
from app.models.challenge import Challenge
from app.models.level import Level
from datetime import datetime, timezone
from app.models.challenge import ChallengeStatus

def current_challenge(session: Session, user: User) -> Challenge | None:
    """获取用户当前进行中的战斗"""
    statement = (
        select(Challenge)
        .where(Challenge.user_id == user.id)
        .where(Challenge.status == ChallengeStatus.IN_PROGRESS)
        .order_by(Challenge.start_time.desc())
    )
    return session.exec(statement).first()

def last_challenge(session: Session, user: User) -> Challenge | None:
    """获取用户上次战斗"""
    statement = (
        select(Challenge)
        .where(Challenge.user_id == user.id)
        .where(Challenge.status != ChallengeStatus.IN_PROGRESS)
        .order_by(Challenge.start_time.desc())
    )
    return session.exec(statement).first()

def get_current_floor(session: Session, user: User) -> int | None:
    """获取用户当前所在楼层"""
    challenge = current_challenge(session, user)
    if not challenge:
        return None
    statement = select(Level.floor).where(Level.id == challenge.level_id)
    return session.exec(statement).first()

def get_last_hp(session: Session, user: User) -> int | None:
    """获取用户上次战斗结束时生命值"""
    challenge = last_challenge(session, user)
    if not challenge:
        return None
    return challenge.end_hp

def new_challenge(session: Session, user: User, level: Level) -> Challenge:
    challenge = Challenge(user_id=user.id, level_id=level.id)
    session.add(challenge)
    session.commit()
    session.refresh(challenge)
    return challenge

def end_challenge(session: Session, user: User, end_hp: int, exp_gained: int, coins_gained: int) -> Challenge | None:
    challenge = current_challenge(session, user)
    if not challenge:
        return None
    challenge.end_time = datetime.now(timezone.utc)
    challenge.status = ChallengeStatus.COMPLETED
    challenge.end_hp = end_hp
    challenge.exp_gained = exp_gained
    challenge.coins_gained = coins_gained

    # 将奖励加到用户属性
    user.exp += exp_gained
    user.coins += coins_gained

    session.add(challenge)
    session.add(user)
    session.commit()
    session.refresh(challenge)
    return challenge