from datetime import datetime, timezone

from sqlmodel import select

from app.db.database import Session
from app.models.challenge import Challenge, ChallengeStatus
from app.models.level import Level
from app.models.user import User


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


def end_challenge(
    session: Session,
    user: User,
    end_hp: int,
    exp_gained: int,
    coins_gained: int,
) -> Challenge | None:
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


def get_last_failed_tower_run_rewards(session: Session, user: User) -> dict[str, int] | None:
    """计算用户最近一次以失败结束的连续闯塔累计获得的经验、金币和最高楼层。

    按 Challenge.start_time 升序获取该用户的所有已结束挑战，
    通过与 Level.floor 关联将这些挑战划分为若干次连续闯塔：

    * 同一次闯塔中，floor 从 1 开始，此后每一关 floor == 前一关 floor + 1
    * 当出现 floor == 1 或 floor 不是前一关 floor + 1 时，视为开启新的闯塔
    * 一次合法的闯塔要求首层 floor == 1，且最后一关 end_hp <= 0（失败）

    返回最近一条满足上述条件的闯塔的累计 exp_gained、coins_gained 以及本次闯塔最高 floor，
    若不存在则返回 None。
    """

    statement = (
        select(Challenge, Level.floor)
        .join(Level, Challenge.level_id == Level.id)
        .where(Challenge.user_id == user.id)
        .where(Challenge.status != ChallengeStatus.IN_PROGRESS)
        .order_by(Challenge.start_time.asc())
    )

    rows = session.exec(statement).all()
    if not rows:
        return None

    runs: list[list[tuple[Challenge, int]]] = []
    current_run: list[tuple[Challenge, int]] = []
    prev_floor: int | None = None

    for challenge, floor in rows:
        # 若楼层信息缺失，则跳过该记录
        if floor is None:
            continue

        if not current_run:
            # 开启新的闯塔序列
            current_run.append((challenge, floor))
        else:
            # 当 floor == 1 或 floor 不是前一关 + 1 时，认为是新的闯塔
            if floor == 1 or (prev_floor is not None and floor != prev_floor + 1):
                runs.append(current_run)
                current_run = [(challenge, floor)]
            else:
                current_run.append((challenge, floor))

        prev_floor = floor

    if current_run:
        runs.append(current_run)

    # 从最近的一次闯塔开始，查找最后一关是失败（end_hp <= 0）且楼层从 1 起连续递增的闯塔
    for run in reversed(runs):
        first_challenge, first_floor = run[0]
        last_challenge, _ = run[-1]

        # 要求本次闯塔以第 1 层开始
        if first_floor != 1:
            continue

        # 要求本次闯塔以失败结束
        if last_challenge.end_hp is None or last_challenge.end_hp > 0:
            continue

        total_exp = sum(ch.exp_gained for ch, _ in run)
        total_coins = sum(ch.coins_gained for ch, _ in run)
        max_floor = max(floor for _, floor in run)
        return {"total_exp": total_exp, "total_coins": total_coins, "max_floor": max_floor}

    return None
