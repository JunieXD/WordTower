from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from redis.asyncio import Redis
from sqlmodel import Session

from app.db.database import engine
from app.db.redis import pool
from app.db.user import get_user_by_username
from app.models.user import User
from app.utils.logger import get_logger

ACTIVITY_TTL_SECONDS = 180
PERSIST_INTERVAL_SECONDS = 60
PERSIST_MARK_TTL_SECONDS = 60 * 60 * 24
logger = get_logger(__name__)


@dataclass
class PresenceSnapshot:
    social_status: str
    last_online_at: datetime | None


def _last_active_key(username: str) -> str:
    return f"social:last_active:{username}"


def _last_combat_active_key(username: str) -> str:
    return f"social:last_combat_active:{username}"


def _last_persist_key(username: str) -> str:
    return f"social:last_persist:{username}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _normalize_datetime(datetime.fromisoformat(value))
    except ValueError:
        return None


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_time(*values: datetime | None) -> datetime | None:
    candidates = [_normalize_datetime(value) for value in values if value is not None]
    if not candidates:
        return None
    return max(candidates)


def _is_recent(value: datetime | None, now: datetime) -> bool:
    value = _normalize_datetime(value)
    if value is None:
        return False
    return (now - value).total_seconds() <= ACTIVITY_TTL_SECONDS


async def touch_user_presence(username: str, path: str) -> None:
    now = datetime.now(timezone.utc)
    redis = Redis(connection_pool=pool)
    try:
        now_iso = now.isoformat()
        pipeline = redis.pipeline()
        pipeline.setex(_last_active_key(username), ACTIVITY_TTL_SECONDS, now_iso)
        if path.startswith("/api/combat") or path.startswith("/api/question"):
            pipeline.setex(_last_combat_active_key(username), ACTIVITY_TTL_SECONDS, now_iso)
        await pipeline.execute()

        last_persist = _parse_datetime(await redis.get(_last_persist_key(username)))
        if last_persist and (now - last_persist).total_seconds() < PERSIST_INTERVAL_SECONDS:
            return

        with Session(engine) as session:
            user = get_user_by_username(session, username)
            if user is None:
                return
            user.last_active_at = now
            session.add(user)
            session.commit()

        await redis.set(_last_persist_key(username), now_iso, ex=PERSIST_MARK_TTL_SECONDS)
    finally:
        await redis.close()


async def get_presence_map(users: Sequence[User]) -> dict[int, PresenceSnapshot]:
    if not users:
        return {}

    now = datetime.now(timezone.utc)
    values: list[str | None]
    redis = Redis(connection_pool=pool)
    try:
        keys: list[str] = []
        for user in users:
            keys.append(_last_active_key(user.username))
            keys.append(_last_combat_active_key(user.username))
        values = await redis.mget(keys)
    except Exception:
        logger.warning("读取社交在线态失败，回退数据库时间")
        values = [None] * (len(users) * 2)
    finally:
        await redis.close()

    presence_by_user: dict[int, PresenceSnapshot] = {}
    for index, user in enumerate(users):
        last_active = _parse_datetime(values[index * 2])
        last_combat_active = _parse_datetime(values[index * 2 + 1])
        last_online_at = _latest_time(last_active, user.last_active_at)
        if _is_recent(last_combat_active, now):
            social_status = "combat"
        elif _is_recent(last_online_at, now):
            social_status = "online"
        else:
            social_status = "offline"

        presence_by_user[user.id] = PresenceSnapshot(
            social_status=social_status,
            last_online_at=last_online_at,
        )

    return presence_by_user
