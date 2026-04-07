from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.question import generate_question_content
from app.db.database import engine
from app.db.redis import pool
from app.models.daily_challenge import (
    DailyChallengeAnswer,
    DailyChallengeAnswerResultRead,
    DailyChallengeAnswerSubmit,
    DailyChallengeDay,
    DailyChallengeFloorQuestion,
    DailyChallengeLeaderboardEntryRead,
    DailyChallengeOverviewRead,
    DailyChallengeQuestionRead,
    DailyChallengeRun,
    DailyChallengeRunStatus,
    DailyChallengeStateRead,
    DailyChallengeUsedWord,
)
from app.models.question import Question
from app.models.question_word_link import QuestionWordLink
from app.models.user import User
from app.models.word import Word
from app.utils.LLM import generate_text, precheck_translation_answer
from app.utils.config import (
    get_daily_question_type_weights,
    get_daily_tag_weights,
    settings,
)
from app.utils.logger import get_logger
from app.utils.prompt import get_answer_check_prompt

logger = get_logger(__name__)

DAILY_LOCK_POLL_INTERVAL_SECONDS = 0.25
DAILY_LOCK_MAX_WAIT_SECONDS = 20
DAY_GENERATION_LOCK_TTL_SECONDS = 120


@dataclass
class JudgedAnswer:
    is_correct: bool
    stored_answer_detail: dict[str, Any]
    answer_result: DailyChallengeAnswerResultRead


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_daily_timezone():
    try:
        return ZoneInfo(settings.DAILY_CHALLENGE_TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning(
            "每日挑战时区 %s 不可用，回退到 UTC+8 固定时区",
            settings.DAILY_CHALLENGE_TIMEZONE,
        )
        return timezone(timedelta(hours=8))


def get_daily_challenge_window(now_utc: datetime | None = None) -> tuple[str, datetime, datetime]:
    current_utc = now_utc or _now_utc()
    tz = _get_daily_timezone()
    local_now = current_utc.astimezone(tz)
    reset_at = time(settings.DAILY_CHALLENGE_RESET_HOUR, 0)

    if local_now.timetz().replace(tzinfo=None) < reset_at:
        day_date = local_now.date() - timedelta(days=1)
    else:
        day_date = local_now.date()

    opens_local = datetime.combine(day_date, reset_at, tz)
    closes_local = opens_local + timedelta(days=1)
    return day_date.isoformat(), opens_local.astimezone(timezone.utc), closes_local.astimezone(timezone.utc)


def get_or_create_daily_day(session: Session, now_utc: datetime | None = None) -> DailyChallengeDay:
    day_key, opens_at, closes_at = get_daily_challenge_window(now_utc)
    statement = select(DailyChallengeDay).where(DailyChallengeDay.day_key == day_key)
    day = session.exec(statement).first()
    if day:
        return day

    config_snapshot = {
        "player_max_hp": settings.DAILY_CHALLENGE_PLAYER_MAX_HP,
        "player_attack": settings.DAILY_CHALLENGE_PLAYER_ATTACK,
        "enemy_hp": settings.DAILY_CHALLENGE_ENEMY_HP,
        "enemy_attack": settings.DAILY_CHALLENGE_ENEMY_ATTACK,
        "heal_every_floors": settings.DAILY_CHALLENGE_HEAL_EVERY_FLOORS,
        "heal_amount": settings.DAILY_CHALLENGE_HEAL_AMOUNT,
        "source_tags": settings.DAILY_CHALLENGE_SOURCE_TAGS,
        "tag_weights": settings.DAILY_CHALLENGE_TAG_WEIGHTS,
    }

    day = DailyChallengeDay(
        day_key=day_key,
        opens_at=opens_at,
        closes_at=closes_at,
        source_tags=list(settings.DAILY_CHALLENGE_SOURCE_TAGS),
        config_snapshot=config_snapshot,
        created_at=now_utc or _now_utc(),
    )
    session.add(day)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        day = session.exec(statement).first()
        if day is None:
            raise
    else:
        session.refresh(day)
    return day


def get_active_daily_run(session: Session, user_id: int) -> DailyChallengeRun | None:
    statement = (
        select(DailyChallengeRun)
        .where(DailyChallengeRun.user_id == user_id)
        .where(DailyChallengeRun.status == DailyChallengeRunStatus.IN_PROGRESS)
        .order_by(DailyChallengeRun.started_at.desc())
    )
    return session.exec(statement).first()


def get_daily_run_for_day(session: Session, day_id: int, user_id: int) -> DailyChallengeRun | None:
    statement = (
        select(DailyChallengeRun)
        .where(DailyChallengeRun.day_id == day_id)
        .where(DailyChallengeRun.user_id == user_id)
    )
    return session.exec(statement).first()


def create_daily_run(session: Session, day: DailyChallengeDay, user_id: int, now_utc: datetime | None = None) -> DailyChallengeRun:
    current_time = now_utc or _now_utc()
    run = DailyChallengeRun(
        day_id=day.id,
        user_id=user_id,
        status=DailyChallengeRunStatus.IN_PROGRESS,
        current_floor=1,
        current_question_index=1,
        current_hp=settings.DAILY_CHALLENGE_PLAYER_MAX_HP,
        current_enemy_hp=settings.DAILY_CHALLENGE_ENEMY_HP,
        best_floor=1,
        best_floor_reached_at=current_time,
        started_at=current_time,
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = get_daily_run_for_day(session, day.id, user_id)
        if existing is None:
            raise
        return existing
    session.refresh(run)
    return run


def _tag_match_condition(tag: str):
    return or_(
        Word.tags == tag,
        Word.tags.like(f"{tag} %"),
        Word.tags.like(f"% {tag}"),
        Word.tags.like(f"% {tag} %"),
    )


def _get_used_word_ids_for_day(session: Session, day_id: int) -> set[int]:
    statement = select(DailyChallengeUsedWord.word_id).where(DailyChallengeUsedWord.day_id == day_id)
    return set(session.exec(statement).all())


def _pick_word_for_tag(
    session: Session,
    tag: str,
    excluded_word_ids: set[int],
) -> Word | None:
    statement = select(Word).where(_tag_match_condition(tag))
    if excluded_word_ids:
        statement = statement.where(~Word.id.in_(excluded_word_ids))
    statement = statement.order_by(func.random())
    return session.exec(statement.limit(1)).first()


def _pick_daily_words(
    session: Session,
    day_id: int,
    floor: int,
    count: int,
) -> list[Word]:
    selected_words: list[Word] = []
    excluded_word_ids = _get_used_word_ids_for_day(session, day_id)
    tag_weights = get_daily_tag_weights(floor)

    for _ in range(count):
        available_candidates: list[tuple[str, int, Word]] = []
        for tag in settings.DAILY_CHALLENGE_SOURCE_TAGS:
            weight = int(tag_weights.get(tag, 0))
            if weight <= 0:
                continue
            candidate = _pick_word_for_tag(session, tag, excluded_word_ids)
            if candidate is not None:
                available_candidates.append((tag, weight, candidate))

        if not available_candidates:
            return selected_words

        tags = [item[0] for item in available_candidates]
        weights = [item[1] for item in available_candidates]
        chosen_tag = random.choices(tags, weights=weights)[0]
        chosen_word = next(item[2] for item in available_candidates if item[0] == chosen_tag)
        selected_words.append(chosen_word)
        excluded_word_ids.add(chosen_word.id)

    return selected_words


def _build_daily_lock_key(day_key: str, floor: int, question_index: int) -> str:
    return f"daily:{day_key}:floor:{floor}:question:{question_index}:lock"


def _build_daily_prewarm_positions(
    floor: int,
    question_index: int,
    enemy_hp: int,
    count: int,
) -> list[tuple[int, int]]:
    if count <= 0:
        return []

    positions: list[tuple[int, int]] = []
    simulated_floor = floor
    simulated_question_index = question_index
    simulated_enemy_hp = enemy_hp

    for _ in range(count):
        simulated_enemy_hp -= settings.DAILY_CHALLENGE_PLAYER_ATTACK
        if simulated_enemy_hp <= 0:
            simulated_floor += 1
            simulated_question_index = 1
            simulated_enemy_hp = settings.DAILY_CHALLENGE_ENEMY_HP
        else:
            simulated_question_index += 1
        positions.append((simulated_floor, simulated_question_index))

    return positions


def _get_daily_floor_question(
    session: Session,
    day_id: int,
    floor: int,
    question_index: int,
) -> DailyChallengeFloorQuestion | None:
    statement = (
        select(DailyChallengeFloorQuestion)
        .where(DailyChallengeFloorQuestion.day_id == day_id)
        .where(DailyChallengeFloorQuestion.floor == floor)
        .where(DailyChallengeFloorQuestion.question_index == question_index)
    )
    return session.exec(statement).first()


def _save_daily_generated_question(
    session: Session,
    day: DailyChallengeDay,
    floor: int,
    question_index: int,
    q_type: str,
    content: dict[str, Any],
    words: list[Word],
    now_utc: datetime,
) -> tuple[DailyChallengeFloorQuestion, Question]:
    question = Question(type=q_type, content=content)
    session.add(question)
    session.flush()

    for word in words:
        session.add(QuestionWordLink(question_id=question.id, word_id=word.id))
        session.add(
            DailyChallengeUsedWord(
                day_id=day.id,
                floor=floor,
                question_index=question_index,
                word_id=word.id,
                created_at=now_utc,
            )
        )

    floor_question = DailyChallengeFloorQuestion(
        day_id=day.id,
        floor=floor,
        question_index=question_index,
        question_id=question.id,
        question_type=q_type,
        word_ids=[word.id for word in words],
        created_at=now_utc,
    )
    session.add(floor_question)
    session.commit()
    session.refresh(floor_question)
    session.refresh(question)
    return floor_question, question


async def ensure_daily_question(
    session: Session,
    redis: Redis,
    day: DailyChallengeDay,
    floor: int,
    question_index: int,
) -> tuple[DailyChallengeFloorQuestion | None, Question | None]:
    existing = _get_daily_floor_question(session, day.id, floor, question_index)
    if existing:
        return existing, session.get(Question, existing.question_id)

    lock_key = _build_daily_lock_key(day.day_key, floor, question_index)
    token = str(uuid.uuid4())
    acquired = await redis.set(lock_key, token, ex=DAY_GENERATION_LOCK_TTL_SECONDS, nx=True)

    if not acquired:
        wait_steps = int(DAILY_LOCK_MAX_WAIT_SECONDS / DAILY_LOCK_POLL_INTERVAL_SECONDS)
        for _ in range(wait_steps):
            await asyncio.sleep(DAILY_LOCK_POLL_INTERVAL_SECONDS)
            session.expire_all()
            existing = _get_daily_floor_question(session, day.id, floor, question_index)
            if existing:
                return existing, session.get(Question, existing.question_id)
        acquired = await redis.set(lock_key, token, ex=DAY_GENERATION_LOCK_TTL_SECONDS, nx=True)
        if not acquired:
            session.expire_all()
            existing = _get_daily_floor_question(session, day.id, floor, question_index)
            if existing:
                return existing, session.get(Question, existing.question_id)
            raise RuntimeError("每日挑战题目生成锁获取失败")

    try:
        session.expire_all()
        existing = _get_daily_floor_question(session, day.id, floor, question_index)
        if existing:
            return existing, session.get(Question, existing.question_id)

        q_type = random.choices(settings.QUESTION_TYPES, weights=get_daily_question_type_weights(floor))[0]
        required_word_count = 4 if q_type == "cloze_test" else 1
        words = _pick_daily_words(session, day.id, floor, required_word_count)
        if len(words) < required_word_count:
            logger.warning(
                "每日挑战题目生成停止：词池耗尽，day=%s floor=%s question_index=%s type=%s",
                day.day_key,
                floor,
                question_index,
                q_type,
            )
            return None, None

        content = await generate_question_content(
            user_id=0,
            q_type=q_type,
            word_texts=[word.text for word in words],
        )
        if not content:
            logger.error(
                "每日挑战题目生成失败：内容为空，day=%s floor=%s question_index=%s type=%s",
                day.day_key,
                floor,
                question_index,
                q_type,
            )
            return None, None

        current_time = _now_utc()
        floor_question, question = _save_daily_generated_question(
            session=session,
            day=day,
            floor=floor,
            question_index=question_index,
            q_type=q_type,
            content=content,
            words=words,
            now_utc=current_time,
        )
        logger.info(
            "每日挑战题目生成成功：day=%s floor=%s question_index=%s question_id=%s",
            day.day_key,
            floor,
            question_index,
            question.id,
        )
        return floor_question, question
    finally:
        current_value = await redis.get(lock_key)
        if current_value == token:
            await redis.delete(lock_key)


async def prewarm_daily_questions(
    day_id: int,
    floor: int,
    question_index: int,
    enemy_hp: int,
    count: int | None = None,
) -> None:
    prewarm_count = count if count is not None else settings.DAILY_CHALLENGE_PREWARM_COUNT
    if prewarm_count <= 0:
        return

    redis = Redis(connection_pool=pool)
    try:
        with Session(engine) as session:
            day = session.get(DailyChallengeDay, day_id)
            if day is None:
                logger.warning("每日挑战共享预热跳过：挑战日不存在，day_id=%s", day_id)
                return

            positions = _build_daily_prewarm_positions(floor, question_index, enemy_hp, prewarm_count)
            if not positions:
                return

            for target_floor, target_question_index in positions:
                try:
                    await ensure_daily_question(session, redis, day, target_floor, target_question_index)
                except Exception:
                    logger.exception(
                        "每日挑战共享预热失败：day=%s floor=%s question_index=%s",
                        day.day_key,
                        target_floor,
                        target_question_index,
                    )
                    break
    finally:
        await redis.close()


def schedule_daily_question_prewarm(
    day_id: int,
    floor: int,
    question_index: int,
    enemy_hp: int,
    count: int | None = None,
) -> None:
    prewarm_count = count if count is not None else settings.DAILY_CHALLENGE_PREWARM_COUNT
    if prewarm_count <= 0:
        return

    asyncio.create_task(
        prewarm_daily_questions(
            day_id=day_id,
            floor=floor,
            question_index=question_index,
            enemy_hp=enemy_hp,
            count=prewarm_count,
        )
    )


def _sanitize_question_content(question: Question) -> dict[str, Any]:
    content = question.content or {}
    if question.type == "context_guess":
        return {
            "target_word": content.get("target_word"),
            "story": content.get("story"),
            "story_target_forms": content.get("story_target_forms"),
            "options": content.get("options"),
            "correct_option": content.get("correct_option"),
            "explanation": content.get("explanation"),
        }
    if question.type == "cloze_test":
        return {
            "cloze_text": content.get("cloze_text"),
            "shuffled_options": content.get("shuffled_options"),
            "correct_sequence": content.get("correct_sequence"),
            "chinese_translation": content.get("chinese_translation"),
        }
    if question.type == "keyword_translation":
        return {
            "target_word": content.get("target_word"),
            "chinese_sentence": content.get("chinese_sentence"),
        }
    return jsonable_encoder(content)


def _build_question_read(
    floor_question: DailyChallengeFloorQuestion | None,
    question: Question | None,
) -> DailyChallengeQuestionRead | None:
    if floor_question is None or question is None:
        return None
    return DailyChallengeQuestionRead(
        question_id=question.id,
        floor=floor_question.floor,
        question_index=floor_question.question_index,
        type=question.type or "",
        content=_sanitize_question_content(question),
    )


def _build_daily_state(
    day: DailyChallengeDay,
    run: DailyChallengeRun,
    floor_question: DailyChallengeFloorQuestion | None = None,
    question: Question | None = None,
    answer_result: DailyChallengeAnswerResultRead | None = None,
) -> DailyChallengeStateRead:
    return DailyChallengeStateRead(
        run_id=run.id,
        day_key=day.day_key,
        status=run.status.value if isinstance(run.status, DailyChallengeRunStatus) else str(run.status),
        current_floor=run.current_floor,
        current_question_index=run.current_question_index,
        current_hp=run.current_hp,
        current_enemy_hp=run.current_enemy_hp,
        player_max_hp=settings.DAILY_CHALLENGE_PLAYER_MAX_HP,
        player_attack=settings.DAILY_CHALLENGE_PLAYER_ATTACK,
        enemy_max_hp=settings.DAILY_CHALLENGE_ENEMY_HP,
        enemy_attack=settings.DAILY_CHALLENGE_ENEMY_ATTACK,
        heal_every_floors=settings.DAILY_CHALLENGE_HEAL_EVERY_FLOORS,
        heal_amount=settings.DAILY_CHALLENGE_HEAL_AMOUNT,
        best_floor=run.best_floor,
        best_floor_reached_at=run.best_floor_reached_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
        question=_build_question_read(floor_question, question),
        answer_result=answer_result,
    )


def get_current_daily_question_for_run(
    session: Session,
    run: DailyChallengeRun,
) -> tuple[DailyChallengeFloorQuestion | None, Question | None]:
    floor_question = _get_daily_floor_question(session, run.day_id, run.current_floor, run.current_question_index)
    if floor_question is None:
        return None, None
    question = session.get(Question, floor_question.question_id)
    return floor_question, question


def _build_daily_run_entry(
    rank: int,
    run: DailyChallengeRun,
    user: User,
    current_user_id: int,
) -> DailyChallengeLeaderboardEntryRead:
    return DailyChallengeLeaderboardEntryRead(
        rank=rank,
        user_id=user.id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        best_floor=run.best_floor,
        best_floor_reached_at=run.best_floor_reached_at,
        started_at=run.started_at,
        status=run.status.value if isinstance(run.status, DailyChallengeRunStatus) else str(run.status),
        is_current_user=user.id == current_user_id,
    )


def get_daily_leaderboard(
    session: Session,
    day_id: int,
    current_user_id: int,
    limit: int | None = None,
) -> tuple[list[DailyChallengeLeaderboardEntryRead], DailyChallengeLeaderboardEntryRead | None]:
    statement = select(DailyChallengeRun, User).join(User, DailyChallengeRun.user_id == User.id).where(DailyChallengeRun.day_id == day_id)
    rows = list(session.exec(statement).all())
    rows.sort(
        key=lambda item: (
            -item[0].best_floor,
            item[0].best_floor_reached_at,
            item[0].started_at,
            item[0].user_id,
        )
    )

    entries: list[DailyChallengeLeaderboardEntryRead] = []
    current_user_entry: DailyChallengeLeaderboardEntryRead | None = None
    for index, (run, user) in enumerate(rows, start=1):
        entry = _build_daily_run_entry(index, run, user, current_user_id)
        if index <= (limit or settings.DAILY_CHALLENGE_LEADERBOARD_LIMIT):
            entries.append(entry)
        if user.id == current_user_id:
            current_user_entry = entry

    return entries, current_user_entry


def get_daily_overview(
    session: Session,
    user: User,
    now_utc: datetime | None = None,
) -> DailyChallengeOverviewRead:
    current_time = now_utc or _now_utc()
    day = get_or_create_daily_day(session, current_time)
    active_run = get_active_daily_run(session, user.id)
    today_run = get_daily_run_for_day(session, day.id, user.id)
    leaderboard, current_user_entry = get_daily_leaderboard(
        session,
        day.id,
        user.id,
        settings.DAILY_CHALLENGE_LEADERBOARD_LIMIT,
    )

    if active_run is not None:
        active_day = session.get(DailyChallengeDay, active_run.day_id)
        floor_question, question = get_current_daily_question_for_run(session, active_run)
        active_state = _build_daily_state(active_day, active_run, floor_question, question)
        user_status = "in_progress"
    elif today_run is None:
        active_state = None
        user_status = "not_started"
    else:
        active_state = None
        user_status = "ended"

    return DailyChallengeOverviewRead(
        day_key=day.day_key,
        opens_at=day.opens_at,
        closes_at=day.closes_at,
        seconds_until_reset=max(0, int((day.closes_at - current_time).total_seconds())),
        user_status=user_status,
        today_best_floor=today_run.best_floor if today_run else None,
        active_run=active_state,
        leaderboard=leaderboard,
        current_user_rank=current_user_entry.rank if current_user_entry else None,
        current_user_entry=current_user_entry,
    )


def _judge_context_guess(question: Question, submission: DailyChallengeAnswerSubmit) -> JudgedAnswer:
    if submission.is_correct is not None:
        answer_detail = submission.answer_detail or {}
        return JudgedAnswer(
            is_correct=bool(submission.is_correct),
            stored_answer_detail=dict(answer_detail),
            answer_result=DailyChallengeAnswerResultRead(
                is_correct=bool(submission.is_correct),
                detail=dict(answer_detail),
            ),
        )

    content = question.content or {}
    selected_option = (submission.selected_option or "").strip().upper()
    correct_option = str(content.get("correct_option") or "").strip().upper()
    options = content.get("options") or {}
    is_correct = selected_option == correct_option
    return JudgedAnswer(
        is_correct=is_correct,
        stored_answer_detail={
            "selected_option": selected_option,
            "selected_text": options.get(selected_option, ""),
        },
        answer_result=DailyChallengeAnswerResultRead(
            is_correct=is_correct,
            detail={
                "selected_option": selected_option,
                "selected_text": options.get(selected_option, ""),
                "correct_option": correct_option,
                "correct_text": options.get(correct_option, ""),
                "explanation": content.get("explanation", ""),
            },
        ),
    )


def _judge_cloze_test(question: Question, submission: DailyChallengeAnswerSubmit) -> JudgedAnswer:
    if submission.is_correct is not None:
        answer_detail = submission.answer_detail or {}
        return JudgedAnswer(
            is_correct=bool(submission.is_correct),
            stored_answer_detail=dict(answer_detail),
            answer_result=DailyChallengeAnswerResultRead(
                is_correct=bool(submission.is_correct),
                detail=dict(answer_detail),
            ),
        )

    content = question.content or {}
    selected_sequence = submission.selected_sequence or []
    correct_sequence = content.get("correct_sequence") or []
    is_correct = selected_sequence == correct_sequence
    return JudgedAnswer(
        is_correct=is_correct,
        stored_answer_detail={
            "selected_sequence": selected_sequence,
        },
        answer_result=DailyChallengeAnswerResultRead(
            is_correct=is_correct,
            detail={
                "selected_sequence": selected_sequence,
                "correct_sequence": correct_sequence,
                "chinese_translation": content.get("chinese_translation", ""),
            },
        ),
    )


async def _judge_keyword_translation(question: Question, submission: DailyChallengeAnswerSubmit) -> JudgedAnswer:
    content = question.content or {}
    target_word = str(content.get("target_word") or "")
    chinese_sentence = str(content.get("chinese_sentence") or "")
    user_input = (submission.user_input or "").strip()

    precheck_result = precheck_translation_answer(target_word, chinese_sentence, user_input)
    if precheck_result is not None:
        result = precheck_result
    else:
        prompt = get_answer_check_prompt(target_word, chinese_sentence, user_input)
        result = await generate_text(prompt)

    is_correct = bool(result.get("is_correct"))
    answer_detail = {
        "user_input": user_input,
        "score": int(result.get("score", 0)),
        "feedback": result.get("feedback", ""),
        "better_translation": result.get("better_translation", ""),
    }
    return JudgedAnswer(
        is_correct=is_correct,
        stored_answer_detail=answer_detail,
        answer_result=DailyChallengeAnswerResultRead(
            is_correct=is_correct,
            detail={
                **answer_detail,
                "reference_answer": content.get("reference_answer", ""),
            },
        ),
    )


async def judge_daily_answer(question: Question, submission: DailyChallengeAnswerSubmit) -> JudgedAnswer:
    if question.type == "context_guess":
        return _judge_context_guess(question, submission)
    if question.type == "cloze_test":
        return _judge_cloze_test(question, submission)
    if question.type == "keyword_translation":
        return await _judge_keyword_translation(question, submission)
    raise ValueError(f"不支持的每日挑战题型: {question.type}")


def create_daily_answer_record(
    session: Session,
    run: DailyChallengeRun,
    floor_question: DailyChallengeFloorQuestion,
    judged: JudgedAnswer,
    answered_at: datetime,
) -> DailyChallengeAnswer:
    record = DailyChallengeAnswer(
        run_id=run.id,
        floor=run.current_floor,
        question_index=run.current_question_index,
        question_id=floor_question.question_id,
        answer_detail=judged.stored_answer_detail,
        is_correct=judged.is_correct,
        answered_at=answered_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_existing_daily_answer(
    session: Session,
    run_id: int,
    question_id: int,
) -> DailyChallengeAnswer | None:
    statement = (
        select(DailyChallengeAnswer)
        .where(DailyChallengeAnswer.run_id == run_id)
        .where(DailyChallengeAnswer.question_id == question_id)
    )
    return session.exec(statement).first()


async def advance_daily_run_after_answer(
    session: Session,
    redis: Redis,
    day: DailyChallengeDay,
    run: DailyChallengeRun,
    judged: JudgedAnswer,
    answered_at: datetime,
) -> DailyChallengeStateRead:
    if judged.is_correct:
        run.current_enemy_hp = max(0, run.current_enemy_hp - settings.DAILY_CHALLENGE_PLAYER_ATTACK)
        if run.current_enemy_hp <= 0:
            completed_floor = run.current_floor
            next_floor = completed_floor + 1
            next_hp = run.current_hp
            if (
                settings.DAILY_CHALLENGE_HEAL_EVERY_FLOORS > 0
                and completed_floor % settings.DAILY_CHALLENGE_HEAL_EVERY_FLOORS == 0
            ):
                next_hp = min(
                    settings.DAILY_CHALLENGE_PLAYER_MAX_HP,
                    next_hp + settings.DAILY_CHALLENGE_HEAL_AMOUNT,
                )

            next_floor_question, next_question = await ensure_daily_question(
                session,
                redis,
                day,
                next_floor,
                1,
            )
            if next_floor_question is None or next_question is None:
                run.status = DailyChallengeRunStatus.COMPLETED_EXHAUSTED
                run.ended_at = answered_at
                session.add(run)
                session.commit()
                session.refresh(run)
                return _build_daily_state(day, run, answer_result=judged.answer_result)

            run.current_floor = next_floor
            run.current_question_index = 1
            run.current_enemy_hp = settings.DAILY_CHALLENGE_ENEMY_HP
            run.current_hp = next_hp
            run.best_floor = max(run.best_floor, next_floor)
            if run.best_floor == next_floor:
                run.best_floor_reached_at = answered_at
            session.add(run)
            session.commit()
            session.refresh(run)
            schedule_daily_question_prewarm(
                day_id=day.id,
                floor=run.current_floor,
                question_index=run.current_question_index,
                enemy_hp=run.current_enemy_hp,
            )
            return _build_daily_state(day, run, next_floor_question, next_question, judged.answer_result)

        next_question_index = run.current_question_index + 1
        next_floor_question, next_question = await ensure_daily_question(
            session,
            redis,
            day,
            run.current_floor,
            next_question_index,
        )
        if next_floor_question is None or next_question is None:
            run.status = DailyChallengeRunStatus.COMPLETED_EXHAUSTED
            run.ended_at = answered_at
            session.add(run)
            session.commit()
            session.refresh(run)
            return _build_daily_state(day, run, answer_result=judged.answer_result)

        run.current_question_index = next_question_index
        session.add(run)
        session.commit()
        session.refresh(run)
        schedule_daily_question_prewarm(
            day_id=day.id,
            floor=run.current_floor,
            question_index=run.current_question_index,
            enemy_hp=run.current_enemy_hp,
        )
        return _build_daily_state(day, run, next_floor_question, next_question, judged.answer_result)

    run.current_hp = max(0, run.current_hp - settings.DAILY_CHALLENGE_ENEMY_ATTACK)
    if run.current_hp <= 0:
        run.status = DailyChallengeRunStatus.DEAD
        run.ended_at = answered_at
        session.add(run)
        session.commit()
        session.refresh(run)
        return _build_daily_state(day, run, answer_result=judged.answer_result)

    next_question_index = run.current_question_index + 1
    next_floor_question, next_question = await ensure_daily_question(
        session,
        redis,
        day,
        run.current_floor,
        next_question_index,
    )
    if next_floor_question is None or next_question is None:
        run.status = DailyChallengeRunStatus.COMPLETED_EXHAUSTED
        run.ended_at = answered_at
        session.add(run)
        session.commit()
        session.refresh(run)
        return _build_daily_state(day, run, answer_result=judged.answer_result)

    run.current_question_index = next_question_index
    session.add(run)
    session.commit()
    session.refresh(run)
    schedule_daily_question_prewarm(
        day_id=day.id,
        floor=run.current_floor,
        question_index=run.current_question_index,
        enemy_hp=run.current_enemy_hp,
    )
    return _build_daily_state(day, run, next_floor_question, next_question, judged.answer_result)
