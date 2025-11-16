from app.db.user import get_user_by_username
from app.db.database import Session

def user_upgrade_hp(session: Session, username: str, coin: int, hp: int):
    user = get_user_by_username(session, username)
    if user is None:
        return None
    user.coins -= coin
    user.max_hp += hp   
    session.add(user)
    session.commit()
    return user

def user_upgrade_attack(session: Session, username: str, coin: int, attack: int):
    user = get_user_by_username(session, username)
    if user is None:
        return None
    user.coins -= coin
    user.attack += attack
    session.add(user)
    session.commit()
    return user

def user_upgrade_crit_rate(session: Session, username: str, coin: int, crit_rate: float):
    user = get_user_by_username(session, username)
    if user is None:
        return None
    user.coins -= coin
    user.crit_rate += crit_rate
    session.add(user)
    session.commit()
    return user
