import asyncio
import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from sqlalchemy import and_, exists, func
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.db.challenge import get_current_floor
from app.db.database import Session
from app.db.database import engine
from app.db.redis import pool
from app.db.word import get_user_selected_words
from app.models.question import Question
from app.models.question_word_link import QuestionWordLink
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord
from app.models.word import Word
from app.services.spaced_repetition import rank_words_with_srs_priority
from app.services.question_generation import generate_question_content
from app.utils.config import get_question_type_weights, settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

def insert_question_word_link(session: Session, question: Question, word: Word) -> None:
    question_word_link = QuestionWordLink(question_id=question.id, word_id=word.id)
    session.add(question_word_link)
    session.commit()


def random_select_question_type(floor: int) -> str:
    weights = get_question_type_weights(floor)
    return random.choices(settings.QUESTION_TYPES, weights=weights)[0]

def get_question_words(session: Session, question: Question) -> list[Word]:
    statement = select(Word).join(QuestionWordLink).where(QuestionWordLink.question_id == question.id)
    return session.exec(statement).all()

QUEUE_KEY_PREFIX = "questions:queue:"
QUEUE_ID_SET_KEY_PREFIX = "questions:queue:ids:"
QUEUE_FP_SET_KEY_PREFIX = "questions:queue:fps:"
QUEUE_DAY_KEY_PREFIX = "questions:queue:day:"
LAST_QUESTION_ID_KEY_PREFIX = "questions:last:id:"
LAST_QUESTION_FP_KEY_PREFIX = "questions:last:fp:"
LAST_QUESTION_TTL_SECONDS = 60 * 30
WORD_QUEUE_KEY_PREFIX = "questions:word:queue:"
WORD_QUEUE_LOCK_KEY_PREFIX = "questions:word:queue:lock:"
WORD_QUEUE_DAY_KEY_PREFIX = "questions:word:queue:day:"
WORD_RECENT_SET_KEY_PREFIX = "questions:word:recent:"
WORD_DAILY_SET_KEY_PREFIX = "questions:word:daily:"
WORD_TEXT_DAILY_SET_KEY_PREFIX = "questions:word:text:daily:"
WORD_GENERATION_FAILURE_KEY_PREFIX = "questions:word:generation:failure:"
WORD_GENERATION_COOLDOWN_KEY_PREFIX = "questions:word:generation:cooldown:"
WORD_QUEUE_LOCK_SECONDS = 5
WORD_RECENT_TTL_SECONDS = 60 * 10
WORD_GENERATION_FAILURE_THRESHOLD = 2
WORD_GENERATION_MAX_QUEUE_CANDIDATES = 2
WORD_QUEUE_REBUILD_WAIT_TIMEOUT_SECONDS = 6.0
WORD_QUEUE_REBUILD_POLL_INTERVAL_SECONDS = 0.05
WORD_RESERVE_STATUS_OK = "ok"
WORD_RESERVE_STATUS_INSUFFICIENT = "insufficient"
WORD_RESERVE_STATUS_REBUILDING = "rebuilding"


class QuestionGenerationRequestContext:
    """单次请求内共享的生成上下文（用于 single-flight 与兜底去重预留）。"""

    def __init__(self) -> None:
        self.word_reserve_lock = asyncio.Lock()
        self.fallback_lock = asyncio.Lock()
        self.fallback_reserved_question_ids: set[int] = set()


def _question_queue_key(user_id: int) -> str:
    return f"{QUEUE_KEY_PREFIX}{user_id}"


def _queue_id_set_key(user_id: int) -> str:
    return f"{QUEUE_ID_SET_KEY_PREFIX}{user_id}"


def _queue_fp_set_key(user_id: int) -> str:
    return f"{QUEUE_FP_SET_KEY_PREFIX}{user_id}"


def _question_queue_day_key(user_id: int) -> str:
    return f"{QUEUE_DAY_KEY_PREFIX}{user_id}"


def _last_question_id_key(user_id: int) -> str:
    return f"{LAST_QUESTION_ID_KEY_PREFIX}{user_id}"


def _last_question_fp_key(user_id: int) -> str:
    return f"{LAST_QUESTION_FP_KEY_PREFIX}{user_id}"


def _word_queue_key(user_id: int) -> str:
    return f"{WORD_QUEUE_KEY_PREFIX}{user_id}"


def _word_queue_lock_key(user_id: int) -> str:
    return f"{WORD_QUEUE_LOCK_KEY_PREFIX}{user_id}"


def _word_queue_day_key(user_id: int) -> str:
    return f"{WORD_QUEUE_DAY_KEY_PREFIX}{user_id}"


def _word_recent_set_key(user_id: int) -> str:
    return f"{WORD_RECENT_SET_KEY_PREFIX}{user_id}"


def _word_daily_set_key(user_id: int, day_key: str) -> str:
    return f"{WORD_DAILY_SET_KEY_PREFIX}{user_id}:{day_key}"


def _word_text_daily_set_key(user_id: int, day_key: str) -> str:
    return f"{WORD_TEXT_DAILY_SET_KEY_PREFIX}{user_id}:{day_key}"


def _word_generation_failure_key(user_id: int, day_key: str, q_type: str, signature: str) -> str:
    return f"{WORD_GENERATION_FAILURE_KEY_PREFIX}{user_id}:{day_key}:{q_type}:{signature}"


def _word_generation_cooldown_key(user_id: int, day_key: str, q_type: str, signature: str) -> str:
    return f"{WORD_GENERATION_COOLDOWN_KEY_PREFIX}{user_id}:{day_key}:{q_type}:{signature}"


def _get_srs_timezone():
    try:
        return ZoneInfo(settings.DAILY_CHALLENGE_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8))


def _current_srs_day_key(now_utc: datetime | None = None) -> str:
    current = now_utc or datetime.now(timezone.utc)
    return current.astimezone(_get_srs_timezone()).date().isoformat()


def _current_srs_day_window_utc(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    current = now_utc or datetime.now(timezone.utc)
    tz = _get_srs_timezone()
    local_now = current.astimezone(tz)
    day_start_local = datetime.combine(local_now.date(), datetime.min.time(), tz)
    next_day_start_local = day_start_local + timedelta(days=1)
    return (
        day_start_local.astimezone(timezone.utc),
        next_day_start_local.astimezone(timezone.utc),
    )


def _seconds_until_srs_day_end(now_utc: datetime | None = None) -> int:
    current = now_utc or datetime.now(timezone.utc)
    tz = _get_srs_timezone()
    local_now = current.astimezone(tz)
    next_day = local_now.date() + timedelta(days=1)
    next_day_start = datetime.combine(next_day, datetime.min.time(), tz)
    seconds = int((next_day_start - local_now).total_seconds())
    return max(seconds, 60)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_word_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def _question_word_keys_from_type_and_content(question_type: Any, content: Any) -> list[str]:
    if not isinstance(content, dict):
        return []

    normalized_keys: list[str] = []
    seen_keys: set[str] = set()

    def add_candidate(candidate: Any) -> None:
        normalized = _normalize_word_key(candidate)
        if normalized and normalized not in seen_keys:
            normalized_keys.append(normalized)
            seen_keys.add(normalized)

    q_type = str(question_type or "")

    if q_type in ("context_guess", "keyword_translation") or "target_word" in content:
        add_candidate(content.get("target_word"))

    if q_type == "cloze_test" or "correct_sequence" in content:
        correct_sequence = content.get("correct_sequence")
        if isinstance(correct_sequence, list):
            for item in correct_sequence:
                add_candidate(item)

    return normalized_keys


def _question_word_keys_from_model(question: Question) -> list[str]:
    return _question_word_keys_from_type_and_content(question.type, question.content)


def _question_word_keys_from_payload(question_data: dict[str, Any]) -> list[str]:
    return _question_word_keys_from_type_and_content(
        question_data.get("type"),
        question_data.get("content"),
    )


def _word_generation_signature(word_texts: list[str]) -> tuple[str | None, list[str]]:
    normalized_word_keys: list[str] = []
    for item in word_texts:
        normalized = _normalize_word_key(item)
        if normalized:
            normalized_word_keys.append(normalized)

    if not normalized_word_keys:
        return None, []

    raw_signature = json.dumps(normalized_word_keys, ensure_ascii=False, separators=(",", ":"))
    signature = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()
    return signature, normalized_word_keys


def _question_fingerprint(question_type: str, content: Any) -> str:
    payload = {"type": question_type or "", "content": content if content is not None else {}}
    try:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        normalized = json.dumps(
            {"type": question_type or "", "content": str(content)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _question_identity_from_model(question: Question) -> tuple[str | None, str | None]:
    question_id = str(question.id) if question.id is not None else None
    if question.type:
        fingerprint = _question_fingerprint(str(question.type), question.content)
    else:
        fingerprint = None
    return question_id, fingerprint


def _question_identity_from_payload(question_data: dict[str, Any]) -> tuple[str | None, str | None]:
    question_id_int = _safe_int(question_data.get("id"))
    question_id = str(question_id_int) if question_id_int is not None else None
    q_type = question_data.get("type")
    if q_type is None:
        return question_id, None
    fingerprint = _question_fingerprint(str(q_type), question_data.get("content"))
    return question_id, fingerprint


async def ensure_question_queue_day(redis: Redis, user_id: int) -> None:
    queue_key = _question_queue_key(user_id)
    day_key = _question_queue_day_key(user_id)
    current_day = _current_srs_day_key()
    ttl_seconds = _seconds_until_srs_day_end()

    queue_day = await redis.get(day_key)
    if isinstance(queue_day, bytes):
        queue_day = queue_day.decode("utf-8", errors="ignore")

    if queue_day and queue_day != current_day:
        await redis.delete(
            queue_key,
            _queue_id_set_key(user_id),
            _queue_fp_set_key(user_id),
            day_key,
        )
        logger.info(
            "题目队列跨天重置：用户ID=%s 旧日期=%s 新日期=%s",
            user_id,
            queue_day,
            current_day,
        )
        queue_day = None

    if not queue_day:
        queue_len = await redis.llen(queue_key)
        if queue_len and int(queue_len) > 0:
            await redis.delete(
                queue_key,
                _queue_id_set_key(user_id),
                _queue_fp_set_key(user_id),
            )
            logger.info(
                "题目队列缺少日期标记，按过期队列清空：用户ID=%s 队列长度=%s 日期=%s",
                user_id,
                int(queue_len),
                current_day,
            )
        await redis.setex(day_key, ttl_seconds, current_day)
        return

    await redis.expire(day_key, ttl_seconds)


async def remove_question_from_queue_indexes(redis: Redis, user_id: int, question_data: dict[str, Any]) -> None:
    """题目出队后，清理 Redis 去重索引。"""
    question_id, fingerprint = _question_identity_from_payload(question_data)
    if question_id:
        await redis.srem(_queue_id_set_key(user_id), question_id)
    if fingerprint:
        await redis.srem(_queue_fp_set_key(user_id), fingerprint)


async def is_recent_duplicate_payload(redis: Redis, user_id: int, question_data: dict[str, Any]) -> bool:
    """判断队列题是否与用户最近一次返回题重复（按 ID 或内容指纹）。"""
    question_id, fingerprint = _question_identity_from_payload(question_data)
    last_id = await redis.get(_last_question_id_key(user_id))
    last_fp = await redis.get(_last_question_fp_key(user_id))
    duplicate_by_id = bool(question_id and last_id and question_id == last_id)
    duplicate_by_fp = bool(fingerprint and last_fp and fingerprint == last_fp)
    return duplicate_by_id or duplicate_by_fp


async def is_recent_duplicate_question(redis: Redis, user_id: int, question: Question) -> bool:
    """判断数据库题是否与用户最近一次返回题重复（按 ID 或内容指纹）。"""
    question_id, fingerprint = _question_identity_from_model(question)
    last_id = await redis.get(_last_question_id_key(user_id))
    last_fp = await redis.get(_last_question_fp_key(user_id))
    duplicate_by_id = bool(question_id and last_id and question_id == last_id)
    duplicate_by_fp = bool(fingerprint and last_fp and fingerprint == last_fp)
    return duplicate_by_id or duplicate_by_fp


def _load_served_word_keys_for_today(user_id: int) -> list[str]:
    day_start_utc, day_end_utc = _current_srs_day_window_utc()
    with DBSession(engine) as session:
        statement = (
            select(Question)
            .join(UserQuestionRecord, UserQuestionRecord.question_id == Question.id)
            .where(UserQuestionRecord.user_id == user_id)
            .where(UserQuestionRecord.time >= day_start_utc)
            .where(UserQuestionRecord.time < day_end_utc)
            .order_by(UserQuestionRecord.time.asc(), Question.id.asc())
        )
        questions = list(session.exec(statement).all())

    normalized_word_keys: list[str] = []
    seen_keys: set[str] = set()
    for question in questions:
        for word_key in _question_word_keys_from_model(question):
            if word_key not in seen_keys:
                normalized_word_keys.append(word_key)
                seen_keys.add(word_key)
    return normalized_word_keys


async def _get_served_word_keys_today(redis: Redis, user_id: int) -> set[str]:
    day_key = _current_srs_day_key()
    redis_key = _word_text_daily_set_key(user_id, day_key)
    values = await redis.smembers(redis_key)
    served_word_keys: set[str] = set()
    for item in values:
        normalized = _normalize_word_key(item.decode("utf-8", errors="ignore") if isinstance(item, bytes) else item)
        if normalized:
            served_word_keys.add(normalized)
    if served_word_keys:
        return served_word_keys

    backfilled_word_keys = await asyncio.to_thread(_load_served_word_keys_for_today, user_id)
    if backfilled_word_keys:
        await _mark_served_word_keys_today(redis, user_id, backfilled_word_keys)
        served_word_keys.update(backfilled_word_keys)
    return served_word_keys


async def _mark_served_word_keys_today(redis: Redis, user_id: int, word_keys: list[str]) -> None:
    normalized_word_keys: list[str] = []
    seen_keys: set[str] = set()
    for item in word_keys:
        normalized = _normalize_word_key(item)
        if normalized and normalized not in seen_keys:
            normalized_word_keys.append(normalized)
            seen_keys.add(normalized)

    if not normalized_word_keys:
        return

    day_key = _current_srs_day_key()
    key = _word_text_daily_set_key(user_id, day_key)
    ttl_seconds = _seconds_until_srs_day_end()
    await redis.sadd(key, *normalized_word_keys)
    await redis.expire(key, ttl_seconds)


async def is_same_day_word_duplicate_payload(redis: Redis, user_id: int, question_data: dict[str, Any]) -> bool:
    question_word_keys = _question_word_keys_from_payload(question_data)
    if not question_word_keys:
        return False
    served_word_keys = await _get_served_word_keys_today(redis, user_id)
    return any(word_key in served_word_keys for word_key in question_word_keys)


async def is_same_day_word_duplicate_question(redis: Redis, user_id: int, question: Question) -> bool:
    question_word_keys = _question_word_keys_from_model(question)
    if not question_word_keys:
        return False
    served_word_keys = await _get_served_word_keys_today(redis, user_id)
    return any(word_key in served_word_keys for word_key in question_word_keys)


async def mark_question_served_payload(redis: Redis, user_id: int, question_data: dict[str, Any]) -> None:
    """记录用户最近一次返回题（payload 版本），用于避免连续重复。"""
    question_id, fingerprint = _question_identity_from_payload(question_data)
    pipe = redis.pipeline()
    if question_id:
        pipe.setex(_last_question_id_key(user_id), LAST_QUESTION_TTL_SECONDS, question_id)
    if fingerprint:
        pipe.setex(_last_question_fp_key(user_id), LAST_QUESTION_TTL_SECONDS, fingerprint)
    if pipe.command_stack:
        await pipe.execute()
    await _mark_served_word_keys_today(redis, user_id, _question_word_keys_from_payload(question_data))


async def mark_question_served_question(redis: Redis, user_id: int, question: Question) -> None:
    """记录用户最近一次返回题（Question 对象版本），用于避免连续重复。"""
    question_id, fingerprint = _question_identity_from_model(question)
    pipe = redis.pipeline()
    if question_id:
        pipe.setex(_last_question_id_key(user_id), LAST_QUESTION_TTL_SECONDS, question_id)
    if fingerprint:
        pipe.setex(_last_question_fp_key(user_id), LAST_QUESTION_TTL_SECONDS, fingerprint)
    if pipe.command_stack:
        await pipe.execute()
    await _mark_served_word_keys_today(redis, user_id, _question_word_keys_from_model(question))

def _prepare_generation_data(user_id: int) -> dict[str, Any] | None:
    """
    同步函数：准备生成题目所需的数据（在线程池中运行）
    """
    with DBSession(engine) as session:
        user = session.get(User, user_id)
        if not user:
            logger.debug("准备题目数据失败：用户不存在，用户ID=%s", user_id)
            return None

        floor = get_current_floor(session, user) or 1
        weights = get_question_type_weights(floor)
        q_type = random.choices(settings.QUESTION_TYPES, weights=weights)[0]
        logger.debug(
            "准备题目数据：用户ID=%s 当前楼层=%s 题型权重=%s 选中题型=%s",
            user_id,
            floor,
            weights,
            q_type,
        )

        word_count = 4 if q_type == "cloze_test" else 1
        return {
            "q_type": q_type,
            "word_count": word_count,
        }


def _prepare_ranked_words_for_queue(
    user_id: int,
    recent_excluded_word_ids: set[int] | None = None,
    daily_excluded_word_ids: set[int] | None = None,
) -> list[int]:
    with DBSession(engine) as session:
        user = session.get(User, user_id)
        if not user:
            return []
        all_words = get_user_selected_words(session, user)
        if not all_words:
            return []
        ranked_words = rank_words_with_srs_priority(session, user, all_words)
        ranked_word_ids = [int(word.id) for word in ranked_words if word.id is not None]
        after_daily = (
            [word_id for word_id in ranked_word_ids if word_id not in daily_excluded_word_ids]
            if daily_excluded_word_ids
            else ranked_word_ids
        )
        if not recent_excluded_word_ids:
            return after_daily
        filtered = [word_id for word_id in after_daily if word_id not in recent_excluded_word_ids]
        # `recent` is soft suppression; if filtered is empty, keep non-daily candidates.
        return filtered if filtered else after_daily


def _fetch_word_texts_by_ids(word_ids: list[int]) -> list[str]:
    if not word_ids:
        return []
    with DBSession(engine) as session:
        statement = select(Word).where(Word.id.in_(word_ids))
        words = session.exec(statement).all()
        text_by_id = {int(word.id): word.text for word in words if word.id is not None}
    return [text_by_id[word_id] for word_id in word_ids if word_id in text_by_id]


async def clear_word_selection_queue(redis: Redis, user_id: int) -> None:
    key = _word_queue_key(user_id)
    await redis.delete(
        key,
        _word_queue_lock_key(user_id),
        _word_queue_day_key(user_id),
        _word_recent_set_key(user_id),
    )


async def _get_words_used_today(redis: Redis, user_id: int) -> set[int]:
    day_key = _current_srs_day_key()
    values = await redis.smembers(_word_daily_set_key(user_id, day_key))
    return {value for value in (_safe_int(item) for item in values) if value is not None}


async def _mark_words_used_today(redis: Redis, user_id: int, word_ids: list[int]) -> None:
    if not word_ids:
        return
    day_key = _current_srs_day_key()
    key = _word_daily_set_key(user_id, day_key)
    ttl_seconds = _seconds_until_srs_day_end()
    await redis.sadd(key, *[str(word_id) for word_id in word_ids])
    await redis.expire(key, ttl_seconds)


async def _get_word_generation_failure_count(
    redis: Redis,
    user_id: int,
    q_type: str,
    word_texts: list[str],
) -> int:
    signature, _ = _word_generation_signature(word_texts)
    if not signature:
        return 0
    day_key = _current_srs_day_key()
    count = _safe_int(await redis.get(_word_generation_failure_key(user_id, day_key, q_type, signature)))
    return count or 0


async def _record_word_generation_failure(
    redis: Redis,
    user_id: int,
    q_type: str,
    word_texts: list[str],
) -> int:
    signature, normalized_word_keys = _word_generation_signature(word_texts)
    if not signature:
        return 0

    day_key = _current_srs_day_key()
    ttl_seconds = _seconds_until_srs_day_end()
    key = _word_generation_failure_key(user_id, day_key, q_type, signature)
    next_count = (_safe_int(await redis.get(key)) or 0) + 1
    await redis.setex(key, ttl_seconds, str(next_count))
    logger.info(
        "记录题目生成失败：用户ID=%s 题型=%s 词=%s 次数=%s",
        user_id,
        q_type,
        normalized_word_keys,
        next_count,
    )
    return next_count


async def _clear_word_generation_failure(
    redis: Redis,
    user_id: int,
    q_type: str,
    word_texts: list[str],
) -> None:
    signature, _ = _word_generation_signature(word_texts)
    if not signature:
        return
    day_key = _current_srs_day_key()
    await redis.delete(
        _word_generation_failure_key(user_id, day_key, q_type, signature),
        _word_generation_cooldown_key(user_id, day_key, q_type, signature),
    )


async def _is_word_generation_cooled_down(
    redis: Redis,
    user_id: int,
    q_type: str,
    word_texts: list[str],
) -> bool:
    signature, _ = _word_generation_signature(word_texts)
    if not signature:
        return False
    day_key = _current_srs_day_key()
    cooldown_value = await redis.get(_word_generation_cooldown_key(user_id, day_key, q_type, signature))
    return bool(cooldown_value)


async def _mark_word_generation_cooldown(
    redis: Redis,
    user_id: int,
    q_type: str,
    word_texts: list[str],
) -> None:
    signature, normalized_word_keys = _word_generation_signature(word_texts)
    if not signature:
        return
    day_key = _current_srs_day_key()
    ttl_seconds = _seconds_until_srs_day_end()
    await redis.setex(
        _word_generation_cooldown_key(user_id, day_key, q_type, signature),
        ttl_seconds,
        "1",
    )
    logger.warning(
        "目标词触发生成冷却：用户ID=%s 题型=%s 词=%s 阈值=%s",
        user_id,
        q_type,
        normalized_word_keys,
        WORD_GENERATION_FAILURE_THRESHOLD,
    )


async def _rebuild_word_selection_queue(redis: Redis, user_id: int) -> int | None:
    queue_key = _word_queue_key(user_id)
    lock_key = _word_queue_lock_key(user_id)
    day_key = _word_queue_day_key(user_id)
    recent_key = _word_recent_set_key(user_id)
    lock_value = f"{user_id}:{time.time_ns()}"

    locked = await redis.set(lock_key, lock_value, nx=True, ex=WORD_QUEUE_LOCK_SECONDS)
    if not locked:
        # Another worker is rebuilding.
        return None

    try:
        recent_items = await redis.smembers(recent_key)
        recent_excluded_word_ids = {
            value for value in (_safe_int(item) for item in recent_items) if value is not None
        }
        daily_excluded_word_ids = await _get_words_used_today(redis, user_id)
        ranked_word_ids = await asyncio.to_thread(
            _prepare_ranked_words_for_queue,
            user_id,
            recent_excluded_word_ids,
            daily_excluded_word_ids,
        )
        current_day = _current_srs_day_key()
        ttl_seconds = _seconds_until_srs_day_end()
        pipe = redis.pipeline()
        pipe.delete(queue_key)
        if ranked_word_ids:
            pipe.rpush(queue_key, *[str(word_id) for word_id in ranked_word_ids])
            pipe.expire(queue_key, ttl_seconds)
        pipe.setex(day_key, ttl_seconds, current_day)
        await pipe.execute()
        return len(ranked_word_ids)
    finally:
        current_lock = await redis.get(lock_key)
        if current_lock == lock_value:
            await redis.delete(lock_key)


async def _wait_for_queue_rebuild(redis: Redis, user_id: int) -> tuple[int, str]:
    queue_key = _word_queue_key(user_id)
    lock_key = _word_queue_lock_key(user_id)
    deadline = perf_counter() + WORD_QUEUE_REBUILD_WAIT_TIMEOUT_SECONDS

    while True:
        queue_len = int(await redis.llen(queue_key) or 0)
        if queue_len > 0:
            return queue_len, WORD_RESERVE_STATUS_OK

        if not await redis.exists(lock_key):
            return 0, WORD_RESERVE_STATUS_INSUFFICIENT

        if perf_counter() >= deadline:
            return 0, WORD_RESERVE_STATUS_REBUILDING

        await asyncio.sleep(WORD_QUEUE_REBUILD_POLL_INTERVAL_SECONDS)


async def _ensure_word_selection_queue(redis: Redis, user_id: int) -> tuple[int, str]:
    queue_key = _word_queue_key(user_id)
    lock_key = _word_queue_lock_key(user_id)
    day_key = _word_queue_day_key(user_id)
    recent_key = _word_recent_set_key(user_id)
    current_day = _current_srs_day_key()

    queue_day = await redis.get(day_key)
    if isinstance(queue_day, bytes):
        queue_day = queue_day.decode("utf-8", errors="ignore")
    if queue_day and queue_day != current_day:
        await redis.delete(queue_key, lock_key, day_key, recent_key)

    queue_len = await redis.llen(queue_key)
    if queue_len and int(queue_len) > 0:
        if not queue_day:
            await redis.setex(day_key, _seconds_until_srs_day_end(), current_day)
        return int(queue_len), WORD_RESERVE_STATUS_OK

    rebuilt_count = await _rebuild_word_selection_queue(redis, user_id)
    if rebuilt_count is None:
        return await _wait_for_queue_rebuild(redis, user_id)

    if rebuilt_count > 0:
        return rebuilt_count, WORD_RESERVE_STATUS_OK
    return 0, WORD_RESERVE_STATUS_INSUFFICIENT


async def _pop_word_ids_from_queue(redis: Redis, user_id: int, word_count: int) -> tuple[list[int], str]:
    if word_count <= 0:
        return [], WORD_RESERVE_STATUS_INSUFFICIENT
    queue_key = _word_queue_key(user_id)
    recent_key = _word_recent_set_key(user_id)
    selected: list[int] = []
    selected_set: set[int] = set()
    max_attempts = max(word_count * 8, 16)
    attempts = 0
    reserve_status = WORD_RESERVE_STATUS_OK

    while len(selected) < word_count and attempts < max_attempts:
        attempts += 1
        item = await redis.lpop(queue_key)
        if item is None:
            rebuilt, status = await _ensure_word_selection_queue(redis, user_id)
            if rebuilt <= 0:
                reserve_status = status
                break
            item = await redis.lpop(queue_key)
            if item is None:
                reserve_status = WORD_RESERVE_STATUS_REBUILDING if status == WORD_RESERVE_STATUS_REBUILDING else WORD_RESERVE_STATUS_INSUFFICIENT
                break

        word_id = _safe_int(item)
        if word_id is None:
            continue
        if word_id in selected_set:
            continue
        selected.append(word_id)
        selected_set.add(word_id)
        await redis.sadd(recent_key, str(word_id))
        await redis.expire(recent_key, WORD_RECENT_TTL_SECONDS)

    if selected:
        await redis.expire(queue_key, _seconds_until_srs_day_end())
        return selected, WORD_RESERVE_STATUS_OK
    if reserve_status == WORD_RESERVE_STATUS_OK:
        reserve_status = WORD_RESERVE_STATUS_INSUFFICIENT
    return [], reserve_status


async def _push_word_ids_back_to_queue(redis: Redis, user_id: int, word_ids: list[int]) -> None:
    if not word_ids:
        return
    queue_key = _word_queue_key(user_id)
    recent_key = _word_recent_set_key(user_id)
    # Restore original relative order back to queue front.
    pipe = redis.pipeline()
    pipe.lpush(queue_key, *[str(word_id) for word_id in reversed(word_ids)])
    pipe.expire(queue_key, _seconds_until_srs_day_end())
    pipe.srem(recent_key, *[str(word_id) for word_id in word_ids])
    pipe.expire(recent_key, WORD_RECENT_TTL_SECONDS)
    await pipe.execute()


async def _push_word_ids_to_queue_tail(redis: Redis, user_id: int, word_ids: list[int]) -> None:
    if not word_ids:
        return
    queue_key = _word_queue_key(user_id)
    recent_key = _word_recent_set_key(user_id)
    pipe = redis.pipeline()
    pipe.rpush(queue_key, *[str(word_id) for word_id in word_ids])
    pipe.expire(queue_key, _seconds_until_srs_day_end())
    pipe.srem(recent_key, *[str(word_id) for word_id in word_ids])
    pipe.expire(recent_key, WORD_RECENT_TTL_SECONDS)
    await pipe.execute()


def _save_generated_question(type: str, content: dict, word_ids: list[int]) -> Question:
    """
    同步函数：保存生成的题目（在线程池中运行）
    """
    with DBSession(engine) as session:
        logger.debug(
            "保存题目开始：题型=%s 关联词ID=%s content_keys=%s",
            type,
            word_ids,
            list(content.keys()) if isinstance(content, dict) else [],
        )
        # 重新创建 Question 对象
        question = Question(type=type, content=content)
        session.add(question)
        session.commit()
        session.refresh(question)
        
        # 重新建立关联（因为是在新的Session中）
        for w_id in word_ids:
            # 不需要查询Word对象，直接使用ID插入链接
            link = QuestionWordLink(question_id=question.id, word_id=w_id)
            session.add(link)
            
        session.commit()
        
        # 刷新并移除，以便返回
        session.refresh(question)
        session.expunge(question)
        logger.debug("保存题目完成：题目ID=%s 题型=%s", question.id, type)
        return question

async def generate_single_question(
    user_id: int,
    request_context: QuestionGenerationRequestContext | None = None,
) -> Question | None:
    """
    为用户生成一个单独的问题。
    异步协调：同步DB读 -> 异步LLM -> 同步DB写
    """
    start_ts = perf_counter()
    q_type = settings.QUESTION_TYPES[0]
    question: Question | None = None
    used_fallback = False
    stage = "start"
    current_word_ids: list[int] = []
    current_word_texts: list[str] = []
    current_candidate_reserved = False
    try:
        logger.debug("开始生成单题：用户ID=%s", user_id)
        stage = "prepare_data"
        # 1. 在线程池中执行同步的数据库读取操作
        result = await asyncio.to_thread(_prepare_generation_data, user_id)
        if not result:
            logger.warning("生成题目失败：准备数据为空，用户ID=%s", user_id)
            stage = "prepare_data_empty"
        else:
            q_type = str(result["q_type"])
            required_word_count = int(result.get("word_count", 4 if q_type == "cloze_test" else 1))
            queue_selection_mode = not ("word_ids" in result and "word_texts" in result)
            max_queue_candidates = WORD_GENERATION_MAX_QUEUE_CANDIDATES if queue_selection_mode else 1

            for candidate_index in range(max_queue_candidates):
                content: dict[str, Any] | None = None
                current_word_ids = []
                current_word_texts = []
                current_candidate_reserved = False
                word_reserve_status = WORD_RESERVE_STATUS_OK

                if queue_selection_mode:
                    stage = "reserve_words"
                    redis = Redis(connection_pool=pool)
                    try:
                        if request_context is None:
                            current_word_ids, word_reserve_status = await _pop_word_ids_from_queue(
                                redis,
                                user_id,
                                required_word_count,
                            )
                        else:
                            async with request_context.word_reserve_lock:
                                current_word_ids, word_reserve_status = await _pop_word_ids_from_queue(
                                    redis,
                                    user_id,
                                    required_word_count,
                                )
                    finally:
                        await redis.close()
                    current_candidate_reserved = bool(current_word_ids)
                    current_word_texts = await asyncio.to_thread(_fetch_word_texts_by_ids, current_word_ids)
                    if len(current_word_texts) < len(current_word_ids):
                        # Word rows may be removed/invalid. Keep only valid prefix by ordered lookup result.
                        current_word_ids = current_word_ids[: len(current_word_texts)]
                else:
                    # Backward-compatible path used by tests/mocks.
                    current_word_ids = [
                        int(item)
                        for item in list(result["word_ids"])
                        if _safe_int(item) is not None
                    ]
                    current_word_texts = [str(item) for item in list(result["word_texts"])]

                logger.debug(
                    "生成单题参数：用户ID=%s 题型=%s 候选序号=%s/%s 词ID=%s 词文本=%s",
                    user_id,
                    q_type,
                    candidate_index + 1,
                    max_queue_candidates,
                    current_word_ids,
                    current_word_texts,
                )

                if len(current_word_texts) < required_word_count:
                    if word_reserve_status == WORD_RESERVE_STATUS_REBUILDING:
                        logger.info(
                            "生成题目延后：词队列重建中暂不可读，用户ID=%s 题型=%s 期望数量=%s 实际数量=%s",
                            user_id,
                            q_type,
                            required_word_count,
                            len(current_word_texts),
                        )
                        stage = "fallback_word_queue_rebuilding"
                    else:
                        logger.warning(
                            "生成题目失败：可用单词不足，用户ID=%s 题型=%s 期望数量=%s 实际数量=%s",
                            user_id,
                            q_type,
                            required_word_count,
                            len(current_word_texts),
                        )
                        stage = "fallback_word_insufficient"
                    break

                if queue_selection_mode:
                    redis = Redis(connection_pool=pool)
                    try:
                        if await _is_word_generation_cooled_down(redis, user_id, q_type, current_word_texts):
                            logger.info(
                                "跳过冷却中的候选词：用户ID=%s 题型=%s 词=%s",
                                user_id,
                                q_type,
                                current_word_texts,
                            )
                            await _push_word_ids_to_queue_tail(redis, user_id, current_word_ids)
                            current_candidate_reserved = False
                            stage = "skip_cooled_down_word"
                            continue
                    finally:
                        await redis.close()

                stage = "generate_content"
                logger.debug(
                    "调用统一 Graph 生成：用户ID=%s 题型=%s 目标词=%s",
                    user_id,
                    q_type,
                    current_word_texts,
                )
                content = await generate_question_content(
                    user_id=user_id,
                    q_type=q_type,
                    word_texts=current_word_texts,
                )

                if not content:
                    logger.warning(
                        "生成题目失败：内容生成为空，用户ID=%s 题型=%s 词=%s",
                        user_id,
                        q_type,
                        current_word_texts,
                    )
                    if not queue_selection_mode:
                        stage = "fallback_content_empty"
                        break

                    redis = Redis(connection_pool=pool)
                    try:
                        failure_count = await _record_word_generation_failure(
                            redis,
                            user_id,
                            q_type,
                            current_word_texts,
                        )
                        if failure_count >= WORD_GENERATION_FAILURE_THRESHOLD:
                            await _mark_word_generation_cooldown(
                                redis,
                                user_id,
                                q_type,
                                current_word_texts,
                            )
                            current_candidate_reserved = False
                        else:
                            await _push_word_ids_to_queue_tail(redis, user_id, current_word_ids)
                            current_candidate_reserved = False
                    finally:
                        await redis.close()

                    stage = "retry_next_word_after_generation_failure"
                    continue

                logger.debug(
                    "生成内容完成：用户ID=%s 题型=%s content_keys=%s",
                    user_id,
                    q_type,
                    list(content.keys()),
                )

                # 3. 在线程池中执行同步的数据库写入操作
                stage = "save_generated"
                question = await asyncio.to_thread(_save_generated_question, q_type, content, current_word_ids)
                redis = Redis(connection_pool=pool)
                try:
                    await _mark_words_used_today(redis, user_id, current_word_ids)
                    await _clear_word_generation_failure(redis, user_id, q_type, current_word_texts)
                finally:
                    await redis.close()
                current_candidate_reserved = False
                logger.info("生成题目成功：用户ID=%s 题目ID=%s 类型=%s", user_id, question.id, q_type)
                break

            if question is None and stage in {
                "fallback_word_insufficient",
                "fallback_word_queue_rebuilding",
                "fallback_content_empty",
                "retry_next_word_after_generation_failure",
                "skip_cooled_down_word",
            }:
                used_fallback = True
                if stage == "retry_next_word_after_generation_failure":
                    stage = "fallback_after_generation_failures"
                elif stage == "skip_cooled_down_word":
                    stage = "fallback_after_cooldown_skip"
                elif stage == "fallback_word_queue_rebuilding":
                    stage = "fallback_after_queue_rebuilding"
                question = await _get_fallback_question(user_id, q_type, request_context=request_context)
    except Exception as e:
        logger.exception("生成题目失败：用户ID=%s 题型=%s 错误=%s", user_id, q_type, str(e))
        used_fallback = True
        stage = "fallback_after_exception"
        question = await _get_fallback_question(user_id, q_type, request_context=request_context)

    if current_candidate_reserved and current_word_ids:
        redis = Redis(connection_pool=pool)
        try:
            await _push_word_ids_back_to_queue(redis, user_id, current_word_ids)
        finally:
            await redis.close()

    duration_ms = (perf_counter() - start_ts) * 1000
    question_id = question.id if question else None
    logger.debug(
        "单题生成耗时：用户ID=%s 题型=%s 耗时=%.2fms 阶段=%s 使用兜底=%s 题目ID=%s",
        user_id,
        q_type,
        duration_ms,
        stage,
        used_fallback,
        question_id,
    )
    logger.info(
        "单题生成耗时：用户ID=%s 题型=%s 耗时=%.2fms 使用兜底=%s 题目ID=%s",
        user_id,
        q_type,
        duration_ms,
        used_fallback,
        question_id,
    )
    return question


def _question_conflicts_with_daily_word_keys(
    question: Question,
    daily_used_word_keys: set[str] | None,
) -> bool:
    if not daily_used_word_keys:
        return False
    question_word_keys = _question_word_keys_from_model(question)
    if not question_word_keys:
        return False
    return any(word_key in daily_used_word_keys for word_key in question_word_keys)


def _select_fallback_question(
    user_id: int,
    q_type: str,
    daily_used_word_keys: set[str] | None = None,
    excluded_question_ids: set[int] | None = None,
) -> Question | None:
    """
    兜底策略：
    1) 同题型中用户未作答过的题目
    2) 同题型中用户最久之前作答过的题目
    3) 同题型任意题目
    """
    with DBSession(engine) as session:
        logger.debug("开始查询兜底题：用户ID=%s 题型=%s", user_id, q_type)
        # 1. 未作答优先
        answered_exists = exists().where(
            and_(
                UserQuestionRecord.user_id == user_id,
                UserQuestionRecord.question_id == Question.id,
            )
        )
        candidate_strategies = [
            (
                "未作答",
                select(Question)
                .where(Question.type == q_type)
                .where(~answered_exists)
                .order_by(Question.id.asc()),
            ),
            (
                "最久未作答",
                select(Question)
                .join(UserQuestionRecord, UserQuestionRecord.question_id == Question.id)
                .where(Question.type == q_type)
                .where(UserQuestionRecord.user_id == user_id)
                .group_by(Question.id)
                .order_by(func.max(UserQuestionRecord.time).asc(), Question.id.asc()),
            ),
            (
                "任意题",
                select(Question).where(Question.type == q_type).order_by(Question.id.asc()),
            ),
        ]

        seen_question_ids: set[int] = set()
        for strategy_name, statement in candidate_strategies:
            for question in session.exec(statement):
                if question.id is None or question.id in seen_question_ids:
                    continue
                if excluded_question_ids and question.id in excluded_question_ids:
                    logger.debug(
                        "兜底题跳过：命中本请求预留题，用户ID=%s 题型=%s 题目ID=%s",
                        user_id,
                        q_type,
                        question.id,
                    )
                    continue
                seen_question_ids.add(question.id)

                if _question_conflicts_with_daily_word_keys(question, daily_used_word_keys):
                    logger.info(
                        "兜底题跳过：与当日已出词重复，用户ID=%s 题型=%s 题目ID=%s 词=%s",
                        user_id,
                        q_type,
                        question.id,
                        _question_word_keys_from_model(question),
                    )
                    continue

                logger.debug(
                    "兜底命中策略%s：用户ID=%s 题型=%s 题目ID=%s",
                    strategy_name,
                    user_id,
                    q_type,
                    question.id,
                )
                session.expunge(question)
                return question

        if daily_used_word_keys:
            logger.warning(
                "兜底题全部与当日已出词冲突：用户ID=%s 题型=%s 当日词数量=%s",
                user_id,
                q_type,
                len(daily_used_word_keys),
            )
        return None


async def _get_fallback_question(
    user_id: int,
    q_type: str,
    request_context: QuestionGenerationRequestContext | None = None,
) -> Question | None:
    logger.debug("触发兜底题查询：用户ID=%s 题型=%s", user_id, q_type)
    redis = Redis(connection_pool=pool)
    try:
        daily_used_word_keys = await _get_served_word_keys_today(redis, user_id)
    finally:
        await redis.close()

    if request_context is None:
        question = await asyncio.to_thread(_select_fallback_question, user_id, q_type, daily_used_word_keys)
    else:
        async with request_context.fallback_lock:
            excluded_question_ids = set(request_context.fallback_reserved_question_ids)
            question = await asyncio.to_thread(
                _select_fallback_question,
                user_id,
                q_type,
                daily_used_word_keys,
                excluded_question_ids,
            )
            if question and question.id is not None:
                request_context.fallback_reserved_question_ids.add(question.id)
                logger.debug(
                    "兜底题预留成功：用户ID=%s 题型=%s 题目ID=%s",
                    user_id,
                    q_type,
                    question.id,
                )
    if question:
        logger.warning(
            "使用历史题目兜底：用户ID=%s 题型=%s 题目ID=%s",
            user_id,
            q_type,
            question.id,
        )
    else:
        logger.error("兜底题目获取失败：用户ID=%s 题型=%s", user_id, q_type)
    return question

async def push_question_to_queue(redis: Redis, user_id: int, question: Question) -> bool:
    """
    将问题JSON推送到用户的Redis队列中。
    """
    try:
        await ensure_question_queue_day(redis, user_id)
        # serialize question to json
        data = json.dumps(jsonable_encoder(question))
        key = _question_queue_key(user_id)
        question_id, fingerprint = _question_identity_from_model(question)
        if not question_id or not fingerprint:
            logger.warning("题目入队跳过：关键标识缺失，用户ID=%s 题目ID=%s", user_id, question.id)
            return False

        id_set_key = _queue_id_set_key(user_id)
        fp_set_key = _queue_fp_set_key(user_id)
        id_added = await redis.sadd(id_set_key, question_id)
        if not id_added:
            logger.debug("题目入队去重：用户ID=%s 题目ID=%s 原因=ID重复", user_id, question_id)
            return False

        fp_added = await redis.sadd(fp_set_key, fingerprint)
        if not fp_added:
            await redis.srem(id_set_key, question_id)
            logger.debug("题目入队去重：用户ID=%s 题目ID=%s 原因=内容重复", user_id, question_id)
            return False

        logger.debug(
            "题目入队准备：用户ID=%s 题目ID=%s redis_key=%s payload_bytes=%s",
            user_id,
            question.id,
            key,
            len(data),
        )
        await redis.lpush(key, data)
        logger.info("题目入队成功：用户ID=%s 题目ID=%s", user_id, question.id)
        return True
    except Exception as e:
        question_id, fingerprint = _question_identity_from_model(question)
        if question_id:
            await redis.srem(_queue_id_set_key(user_id), question_id)
        if fingerprint:
            await redis.srem(_queue_fp_set_key(user_id), fingerprint)
        logger.exception("题目入队失败：用户ID=%s 题目ID=%s 错误=%s", user_id, question.id, str(e))
        return False

async def clear_question_queue(redis: Redis, user_id: int):
    """
    清空用户的题目队列。
    """
    try:
        key = _question_queue_key(user_id)
        word_queue_key = _word_queue_key(user_id)
        word_queue_lock_key = _word_queue_lock_key(user_id)
        word_queue_day_key = _word_queue_day_key(user_id)
        word_recent_key = _word_recent_set_key(user_id)
        logger.debug("清空题目队列：用户ID=%s redis_key=%s", user_id, key)
        await redis.delete(
            key,
            _queue_id_set_key(user_id),
            _queue_fp_set_key(user_id),
            _question_queue_day_key(user_id),
            word_queue_key,
            word_queue_lock_key,
            word_queue_day_key,
            word_recent_key,
        )
        logger.info("清空题目队列成功：用户ID=%s", user_id)
    except Exception as e:
        logger.exception("清空题目队列失败：用户ID=%s 错误=%s", user_id, str(e))

async def process_generated_questions(user_id: int, tasks: list[asyncio.Task], exclude_question_id: int | None = None):
    """
    处理生成的题目任务，将结果推入队列 (排除已返回的题目)
    """
    redis = Redis(connection_pool=pool)
    try:
        logger.debug(
            "处理生成题目任务开始：用户ID=%s 任务数=%s 排除题目ID=%s",
            user_id,
            len(tasks),
            exclude_question_id,
        )
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        queued_count = 0
        for q in results:
            if isinstance(q, Exception) or q is None:
                continue
                
            # 如果是已经返回给用户的题目，跳过入队
            if exclude_question_id and q.id == exclude_question_id:
                logger.debug("跳过已返回题目：用户ID=%s 题目ID=%s", user_id, q.id)
                continue
                
            pushed = await push_question_to_queue(redis, user_id, q)
            if pushed:
                queued_count += 1

        logger.info(
            "处理生成题目完成：用户ID=%s 总任务=%s 入队数量=%s 排除题目ID=%s",
            user_id,
            len(tasks),
            queued_count,
            exclude_question_id,
        )
    except Exception as e:
        logger.exception("处理生成题目失败：用户ID=%s 错误=%s", user_id, str(e))
    finally:
        await redis.close()

async def generate_questions_background_task(user_id: int, count: int):
    from app.services.traffic import admit, RELEASE_SCRIPT, _renew, LEASE_SECONDS
    from app.services.work_priority import background_work
    from contextlib import suppress
    import uuid

    redis = Redis(connection_pool=pool)
    lock_key = f"traffic:{{{user_id}}}:prefetch"
    owner = str(uuid.uuid4())
    renewal = None
    try:
        if not await redis.set(lock_key, owner, nx=True, ex=LEASE_SECONDS):
            return
        renewal = asyncio.create_task(_renew(redis, lock_key, owner))
        # One low-priority lookahead; leave interactive capacity unused.
        if not await admit(redis, user_id, background=True):
            return
        with background_work():
            question = await generate_single_question(user_id)
        if question:
            await push_question_to_queue(redis, user_id, question)
    except Exception:
        logger.exception("预生成暂缓：用户ID=%s", user_id)
    finally:
        if renewal is not None:
            renewal.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await renewal
            with suppress(Exception):
                await redis.eval(RELEASE_SCRIPT, 1, lock_key, owner)
        await redis.aclose()
