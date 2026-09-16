from fastapi import APIRouter, Request
from app.utils.LLM import generate_text, precheck_translation_answer
from app.db.database import SessionDep
from app.models.question import QuestionCheck
from app.models.user import User
from app.api.dependencies import get_current_user
from fastapi import Depends
from app.utils.prompt import get_answer_check_prompt
from app.api.api_responses import success_response, not_found_response, internal_server_error_response
from fastapi.encoders import jsonable_encoder
from app.models.question import Question, QuestionAnswer, QuestionReport, QuestionRating
from app.db.user import user_question_answer, user_question_report, user_question_rating
from redis.asyncio import Redis
from app.db.redis import get_redis
from sqlmodel import Session, select
from app.db.question import (
    QuestionGenerationRequestContext,
    QUEUE_KEY_PREFIX,
    ensure_question_queue_day,
    generate_questions_background_task,
    generate_single_question,
    is_recent_duplicate_payload,
    is_same_day_word_duplicate_payload,
    mark_question_served_payload,
    mark_question_served_question,
    remove_question_from_queue_indexes,
)
from app.db.level import link_level_question
from app.models.question_word_link import QuestionWordLink
from app.models.word import Word
from app.services.spaced_repetition import estimate_word_next_review_days
from fastapi import BackgroundTasks
import json
from app.utils.logger import get_logger
from app.utils.question_payload import ensure_story_target_forms_in_payload, serialize_question_for_client
from app.services.traffic import admit, user_action

router = APIRouter(prefix="/api/question", tags=["question"])
logger = get_logger(__name__)
async def _try_get_question_from_queue(
    redis: Redis,
    user_id: int,
    background_tasks: BackgroundTasks,
) -> dict | None:
    key = f"{QUEUE_KEY_PREFIX}{user_id}"
    deferred_duplicate_question_data = None
    while True:
        data = await redis.rpop(key)
        if not data:
            break
        try:
            question_data = json.loads(data)
            if not isinstance(question_data, dict):
                logger.warning("获取题目：队列数据结构异常，用户ID=%s 类型=%s", user_id, type(question_data).__name__)
                continue
            await remove_question_from_queue_indexes(redis, user_id, question_data)

            is_duplicate = await is_recent_duplicate_payload(redis, user_id, question_data)
            if is_duplicate:
                if deferred_duplicate_question_data is None:
                    deferred_duplicate_question_data = question_data
                logger.info(
                    "获取题目：队列命中但与上一题重复，先跳过，用户ID=%s 题目ID=%s",
                    user_id,
                    question_data.get("id"),
                )
                continue

            if await is_same_day_word_duplicate_payload(redis, user_id, question_data):
                logger.info(
                    "获取题目：队列命中但与当日已出词重复，丢弃并继续，用户ID=%s 题目ID=%s",
                    user_id,
                    question_data.get("id"),
                )
                continue

            await mark_question_served_payload(redis, user_id, question_data)
            background_tasks.add_task(generate_questions_background_task, user_id, 1)
            logger.info("获取题目：从队列命中，用户ID=%s", user_id)
            return question_data
        except json.JSONDecodeError:
            logger.warning("获取题目：队列数据损坏，用户ID=%s", user_id)
            continue

    if deferred_duplicate_question_data is not None:
        await mark_question_served_payload(redis, user_id, deferred_duplicate_question_data)
        background_tasks.add_task(generate_questions_background_task, user_id, 1)
        logger.info(
            "获取题目：队列仅存在重复题，回退返回，用户ID=%s 题目ID=%s",
            user_id,
            deferred_duplicate_question_data.get("id"),
        )
        return deferred_duplicate_question_data
    return None


def _build_context_guess_review_hint(session: Session, user: User, question: Question) -> dict | None:
    if question.type != "context_guess" or question.id is None:
        return None

    statement = (
        select(Word)
        .join(QuestionWordLink, QuestionWordLink.word_id == Word.id)
        .where(QuestionWordLink.question_id == question.id)
        .order_by(Word.id.asc())
    )
    word = session.exec(statement).first()
    if word is None:
        return None

    next_review_days = estimate_word_next_review_days(session, user, word)
    return {
        "target_word": word.text,
        "next_review_days": round(next_review_days, 2),
    }

@router.get("/get")
@user_action("question-get")
async def get_question(
    request: Request,
    background_tasks: BackgroundTasks,
    user_in: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    await ensure_question_queue_day(redis, user_in.id)
    queued = await _try_get_question_from_queue(redis, user_in.id, background_tasks)
    if queued is not None:
        return success_response(data=ensure_story_target_forms_in_payload(queued))

    # One interactive question first: do not launch five speculative LLM graphs.
    await admit(redis, user_in.id)
    question = await generate_single_question(user_in.id, request_context=QuestionGenerationRequestContext())
    if question is None:
        return not_found_response(message="暂时没有可用题目，请稍后重试或检查词库")
    await mark_question_served_question(redis, user_in.id, question)
    background_tasks.add_task(generate_questions_background_task, user_in.id, 1)
    return success_response(data=serialize_question_for_client(question))

@router.post("/check")
@user_action("question-check", identity=lambda args, fingerprint: fingerprint)
async def check_answer(request: Request, question_check_in: QuestionCheck,
                       user_in: User = Depends(get_current_user), redis: Redis = Depends(get_redis)):
    precheck_result = precheck_translation_answer(
        question_check_in.target_word,
        question_check_in.chinese_sentence,
        question_check_in.user_input,
    )
    if precheck_result is not None:
        logger.info(
            "检查答案命中本地预检：用户ID=%s 目标词=%s is_correct=%s score=%s",
            user_in.id,
            question_check_in.target_word,
            precheck_result["is_correct"],
            precheck_result["score"],
        )
        return success_response(message="检查完成", data=jsonable_encoder(precheck_result))

    prompt = get_answer_check_prompt(question_check_in.target_word, question_check_in.chinese_sentence, question_check_in.user_input)
    if prompt is None:
        logger.warning("检查答案失败：提示词不存在，用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return not_found_response(message="提示词不存在")
    await admit(redis, user_in.id)
    try:
        result = await generate_text(prompt)
        logger.info("检查答案成功：用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return success_response(message="检查完成", data=jsonable_encoder(result))
    except Exception as e:
        logger.exception("检查答案失败：服务异常，用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return internal_server_error_response(message=f"检查失败: {str(e)}", details={"error": str(e)})
    
@router.post("/answer/{question_id}")
@user_action("question-answer", identity=lambda args, _: f"{args['answer'].level_id}:{args['question_id']}")
async def answer_question(
    request: Request,
    session: SessionDep,
    question_id: int,
    answer: QuestionAnswer,
    user_in: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    question = session.get(Question, question_id)
    if not question:
        logger.warning("记录作答失败：题目不存在，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return not_found_response(message="题目不存在")
    try:
        user_question_answer(session, user_in, question, answer.is_correct, answer.answer_detail)
        # 绑定题目和关卡
        link_level_question(session, answer.level_id, question_id)
        review_hint = None
        if question.type == "context_guess":
            try:
                review_hint = _build_context_guess_review_hint(session, user_in, question)
            except Exception:
                logger.exception(
                    "计算复习提示失败：用户ID=%s 题目ID=%s",
                    user_in.id,
                    question_id,
                )
        logger.info(
            "记录作答：用户ID=%s 题目ID=%s 关卡ID=%s 是否正确=%s",
            user_in.id,
            question_id,
            answer.level_id,
            answer.is_correct,
        )
        return success_response(message="作答记录成功", data=review_hint)
    except Exception as e:
        logger.exception("记录作答失败：服务异常，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return internal_server_error_response(message=f"作答记录失败: {str(e)}", details={"error": str(e)})
    
@router.post("/report/{question_id}")
def report_question(
    session: SessionDep,
    question_id: int,
    report: QuestionReport,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        logger.warning("题目举报失败：题目不存在，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return not_found_response(message="题目不存在")
    try:
        user_question_report(session, user_in, question, report.report)
        logger.info("题目举报：用户ID=%s 题目ID=%s 举报内容=%s", user_in.id, question_id, report.report)
        return success_response(message="报告成功")
    except Exception as e:
        logger.exception("题目举报失败：服务异常，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return internal_server_error_response(message=f"报告失败: {str(e)}", details={"error": str(e)})
    
@router.post("/rating/{question_id}")
def rating_question(
    session: SessionDep,
    question_id: int,
    rating: QuestionRating,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        logger.warning("题目评分失败：题目不存在，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return not_found_response(message="题目不存在")
    try:
        user_question_rating(session, user_in, question, rating.rating)
        logger.info("题目评分：用户ID=%s 题目ID=%s 分数=%s", user_in.id, question_id, rating.rating)
        return success_response(message="评分成功")
    except Exception as e:
        logger.exception("题目评分失败：服务异常，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return internal_server_error_response(message=f"评分失败: {str(e)}", details={"error": str(e)})
