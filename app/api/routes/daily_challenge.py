from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis

from app.api.api_responses import conflict_response
from app.api.api_responses import internal_server_error_response
from app.api.api_responses import success_response
from app.api.dependencies import get_current_user
from app.db.daily_challenge import _build_daily_state
from app.db.daily_challenge import _now_utc
from app.db.daily_challenge import advance_daily_run_after_answer
from app.db.daily_challenge import create_daily_answer_record
from app.db.daily_challenge import create_daily_run
from app.db.daily_challenge import ensure_daily_question
from app.db.daily_challenge import get_active_daily_run
from app.db.daily_challenge import get_current_daily_question_for_run
from app.db.daily_challenge import get_daily_leaderboard
from app.db.daily_challenge import get_daily_overview
from app.db.daily_challenge import get_daily_run_for_day
from app.db.daily_challenge import get_existing_daily_answer
from app.db.daily_challenge import get_or_create_daily_day
from app.db.daily_challenge import judge_daily_answer
from app.db.daily_challenge import schedule_daily_question_prewarm
from app.db.database import SessionDep
from app.db.redis import get_redis
from app.models.daily_challenge import DailyChallengeAnswerSubmit
from app.models.daily_challenge import DailyChallengeDay
from app.models.daily_challenge import DailyChallengeRunStatus
from app.models.user import User
from app.utils.config import settings
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/daily-challenge", tags=["daily-challenge"])
logger = get_logger(__name__)


@router.get("/overview")
async def get_overview(session: SessionDep, current_user: User = Depends(get_current_user)):
    overview = get_daily_overview(session, current_user, _now_utc())
    logger.info("获取每日挑战概览：用户ID=%s 状态=%s", current_user.id, overview.user_status)
    return success_response(data=jsonable_encoder(overview))


@router.get("/leaderboard")
async def get_leaderboard(session: SessionDep, current_user: User = Depends(get_current_user)):
    day = get_or_create_daily_day(session, _now_utc())
    entries, current_user_entry = get_daily_leaderboard(
        session,
        day.id,
        current_user.id,
        settings.DAILY_CHALLENGE_LEADERBOARD_LIMIT,
    )
    payload = {
        "day_key": day.day_key,
        "items": entries,
        "current_user_rank": current_user_entry.rank if current_user_entry else None,
        "current_user_entry": current_user_entry,
    }
    logger.info("获取每日挑战排行榜：用户ID=%s 数量=%s", current_user.id, len(entries))
    return success_response(data=jsonable_encoder(payload))


@router.post("/start")
async def start_daily_challenge(
    session: SessionDep,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    active_run = get_active_daily_run(session, current_user.id)
    if active_run is not None:
        day = session.get(DailyChallengeDay, active_run.day_id)
        if day is None:
            logger.error("恢复每日挑战失败：挑战日不存在，用户ID=%s run_id=%s", current_user.id, active_run.id)
            return internal_server_error_response(message="当前每日挑战数据不存在")

        floor_question, question = get_current_daily_question_for_run(session, active_run)
        if floor_question is None or question is None:
            floor_question, question = await ensure_daily_question(
                session,
                redis,
                day,
                active_run.current_floor,
                active_run.current_question_index,
            )

        if floor_question is None or question is None:
            active_run.status = DailyChallengeRunStatus.COMPLETED_EXHAUSTED
            active_run.ended_at = _now_utc()
            session.add(active_run)
            session.commit()
            session.refresh(active_run)
            logger.warning(
                "恢复每日挑战结束：题库耗尽，用户ID=%s run_id=%s",
                current_user.id,
                active_run.id,
            )
            return success_response(data=jsonable_encoder(_build_daily_state(day, active_run)))

        logger.info("恢复每日挑战：用户ID=%s run_id=%s", current_user.id, active_run.id)
        schedule_daily_question_prewarm(
            day_id=day.id,
            floor=active_run.current_floor,
            question_index=active_run.current_question_index,
            enemy_hp=active_run.current_enemy_hp,
        )
        return success_response(
            data=jsonable_encoder(_build_daily_state(day, active_run, floor_question, question))
        )

    day = get_or_create_daily_day(session, _now_utc())
    today_run = get_daily_run_for_day(session, day.id, current_user.id)
    if today_run is not None and today_run.status != DailyChallengeRunStatus.IN_PROGRESS:
        logger.warning("每日挑战开启失败：今日已结束，用户ID=%s run_id=%s", current_user.id, today_run.id)
        return conflict_response(message="你今天的每日挑战已经结束，请明天再来")

    run = today_run or create_daily_run(session, day, current_user.id, _now_utc())
    floor_question, question = await ensure_daily_question(
        session,
        redis,
        day,
        run.current_floor,
        run.current_question_index,
    )

    if floor_question is None or question is None:
        run.status = DailyChallengeRunStatus.COMPLETED_EXHAUSTED
        run.ended_at = _now_utc()
        session.add(run)
        session.commit()
        session.refresh(run)
        logger.warning("每日挑战开启结束：题库耗尽，用户ID=%s run_id=%s", current_user.id, run.id)
        return success_response(data=jsonable_encoder(_build_daily_state(day, run)))

    logger.info("开始每日挑战：用户ID=%s run_id=%s day=%s", current_user.id, run.id, day.day_key)
    schedule_daily_question_prewarm(
        day_id=day.id,
        floor=run.current_floor,
        question_index=run.current_question_index,
        enemy_hp=run.current_enemy_hp,
    )
    return success_response(data=jsonable_encoder(_build_daily_state(day, run, floor_question, question)))


@router.post("/answer")
async def answer_daily_challenge(
    submission: DailyChallengeAnswerSubmit,
    session: SessionDep,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    run = get_active_daily_run(session, current_user.id)
    if run is None:
        logger.warning("每日挑战作答失败：无进行中挑战，用户ID=%s", current_user.id)
        return conflict_response(message="当前没有可继续的每日挑战")

    day = session.get(DailyChallengeDay, run.day_id)
    if day is None:
        logger.error("每日挑战作答失败：挑战日不存在，用户ID=%s run_id=%s", current_user.id, run.id)
        return internal_server_error_response(message="当前每日挑战数据不存在")

    floor_question, question = get_current_daily_question_for_run(session, run)
    if floor_question is None or question is None:
        logger.error("每日挑战作答失败：当前题目不存在，用户ID=%s run_id=%s", current_user.id, run.id)
        return internal_server_error_response(message="当前每日挑战题目不存在")

    if submission.question_id != question.id:
        logger.warning(
            "每日挑战作答失败：题目不匹配，用户ID=%s run_id=%s expect=%s actual=%s",
            current_user.id,
            run.id,
            question.id,
            submission.question_id,
        )
        return conflict_response(message="当前题目已变化，请刷新后重试")

    existing_answer = get_existing_daily_answer(session, run.id, question.id)
    if existing_answer is not None:
        logger.warning("每日挑战作答失败：重复提交，用户ID=%s run_id=%s question_id=%s", current_user.id, run.id, question.id)
        return conflict_response(message="这道题已经提交过了")

    judged = await judge_daily_answer(question, submission)
    answered_at = _now_utc()
    create_daily_answer_record(session, run, floor_question, judged, answered_at)
    next_state = await advance_daily_run_after_answer(session, redis, day, run, judged, answered_at)
    logger.info(
        "每日挑战作答：用户ID=%s run_id=%s floor=%s question_index=%s correct=%s next_status=%s",
        current_user.id,
        run.id,
        floor_question.floor,
        floor_question.question_index,
        judged.is_correct,
        next_state.status,
    )
    return success_response(data=jsonable_encoder(next_state))
