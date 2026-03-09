import asyncio
import hashlib
import json
import random
from time import perf_counter
from typing import Any

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from sqlalchemy import and_, exists, func
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.db.challenge import get_current_floor
from app.db.database import Session
from app.db.database import engine
from app.db.redis import pool
from app.db.word import random_select_word_by_type
from app.models.question import Question
from app.models.question_word_link import QuestionWordLink
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord
from app.models.word import Word
from app.services.question_generation import generate_context_guess_content
from app.utils.LLM import generate_question_with_validation
from app.utils.config import get_question_type_weights, settings
from app.utils.logger import get_logger
from app.utils.prompt import get_question_prompt

logger = get_logger(__name__)


def _preview(value: Any, limit: int = 120) -> str:
    """用于 debug 日志的简短预览。"""
    text = str(value)
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."

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
LAST_QUESTION_ID_KEY_PREFIX = "questions:last:id:"
LAST_QUESTION_FP_KEY_PREFIX = "questions:last:fp:"
LAST_QUESTION_TTL_SECONDS = 60 * 30


def _queue_id_set_key(user_id: int) -> str:
    return f"{QUEUE_ID_SET_KEY_PREFIX}{user_id}"


def _queue_fp_set_key(user_id: int) -> str:
    return f"{QUEUE_FP_SET_KEY_PREFIX}{user_id}"


def _last_question_id_key(user_id: int) -> str:
    return f"{LAST_QUESTION_ID_KEY_PREFIX}{user_id}"


def _last_question_fp_key(user_id: int) -> str:
    return f"{LAST_QUESTION_FP_KEY_PREFIX}{user_id}"


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        words = random_select_word_by_type(session, user, word_count)
        word_ids = [w.id for w in words]
        word_texts = [w.text for w in words]
        logger.debug(
            "准备题目数据：用户ID=%s 题型=%s 目标词数量=%s 目标词=%s",
            user_id,
            q_type,
            len(word_texts),
            word_texts,
        )

        # 单词不足时也返回题型，供后续兜底策略使用
        if len(words) < word_count:
            return {
                "q_type": q_type,
                "word_ids": word_ids,
                "word_texts": word_texts,
                "prompt": None,
            }

        prompt = None
        if q_type != settings.QUESTION_TYPES[0]:  # 仅非 context_guess 仍走旧 prompt 方式
            prompt_input = word_texts if word_count > 1 else word_texts[0]
            prompt = get_question_prompt(q_type, prompt_input)
            logger.debug(
                "准备题目数据：用户ID=%s 题型=%s prompt长度=%s prompt预览=%s",
                user_id,
                q_type,
                len(prompt) if prompt else 0,
                _preview(prompt) if prompt else "-",
            )

        return {
            "q_type": q_type,
            "word_ids": word_ids,
            "word_texts": word_texts,
            "prompt": prompt,
        }

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

async def generate_single_question(user_id: int) -> Question | None:
    """
    为用户生成一个单独的问题。
    异步协调：同步DB读 -> 异步LLM -> 同步DB写
    """
    start_ts = perf_counter()
    q_type = settings.QUESTION_TYPES[0]
    question: Question | None = None
    used_fallback = False
    stage = "start"
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
            word_ids = list(result["word_ids"])
            word_texts = list(result["word_texts"])
            prompt = result["prompt"]
            logger.debug(
                "生成单题参数：用户ID=%s 题型=%s 词ID=%s 词文本=%s",
                user_id,
                q_type,
                word_ids,
                word_texts,
            )

            # 2. 根据题型调用不同生成引擎
            content: dict[str, Any] | None = None
            stage = "generate_content"
            if q_type == settings.QUESTION_TYPES[0]:  # context_guess
                if not word_texts:
                    logger.warning("生成题目失败：可用单词不足，用户ID=%s 题型=%s", user_id, q_type)
                    used_fallback = True
                    stage = "fallback_word_insufficient"
                    question = await _get_fallback_question(user_id, q_type)
                else:
                    logger.debug("调用 Graph 生成：用户ID=%s 题型=%s 目标词=%s", user_id, q_type, word_texts[0])
                    content = await generate_context_guess_content(user_id=user_id, target_word=word_texts[0])
            else:
                if not prompt:
                    logger.warning("生成题目失败：提示词为空，用户ID=%s 题型=%s", user_id, q_type)
                    used_fallback = True
                    stage = "fallback_prompt_empty"
                    question = await _get_fallback_question(user_id, q_type)
                else:
                    logger.debug("调用旧生成链路：用户ID=%s 题型=%s prompt长度=%s", user_id, q_type, len(prompt))
                    content = await generate_question_with_validation(prompt, q_type)

            if question is None:
                if not content:
                    logger.warning("生成题目失败：内容生成为空，用户ID=%s 题型=%s", user_id, q_type)
                    used_fallback = True
                    stage = "fallback_content_empty"
                    question = await _get_fallback_question(user_id, q_type)
                else:
                    logger.debug(
                        "生成内容完成：用户ID=%s 题型=%s content_keys=%s",
                        user_id,
                        q_type,
                        list(content.keys()),
                    )

                    # 3. 在线程池中执行同步的数据库写入操作
                    stage = "save_generated"
                    question = await asyncio.to_thread(_save_generated_question, q_type, content, word_ids)
                    logger.info("生成题目成功：用户ID=%s 题目ID=%s 类型=%s", user_id, question.id, q_type)
    except Exception as e:
        logger.exception("生成题目失败：用户ID=%s 题型=%s 错误=%s", user_id, q_type, str(e))
        used_fallback = True
        stage = "fallback_after_exception"
        question = await _get_fallback_question(user_id, q_type)

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


def _select_fallback_question(user_id: int, q_type: str) -> Question | None:
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
        statement = (
            select(Question)
            .where(Question.type == q_type)
            .where(~answered_exists)
            .order_by(Question.id.asc())
        )
        question = session.exec(statement).first()
        if question:
            logger.debug("兜底命中策略1（未作答）：用户ID=%s 题型=%s 题目ID=%s", user_id, q_type, question.id)
            session.expunge(question)
            return question

        # 2. 最久未作答（按最近一次作答时间最早排序）
        statement = (
            select(Question)
            .join(UserQuestionRecord, UserQuestionRecord.question_id == Question.id)
            .where(Question.type == q_type)
            .where(UserQuestionRecord.user_id == user_id)
            .group_by(Question.id)
            .order_by(func.max(UserQuestionRecord.time).asc(), Question.id.asc())
        )
        question = session.exec(statement).first()
        if question:
            logger.debug("兜底命中策略2（最久未作答）：用户ID=%s 题型=%s 题目ID=%s", user_id, q_type, question.id)
            session.expunge(question)
            return question

        # 3. 任意同题型题目
        statement = select(Question).where(Question.type == q_type).order_by(Question.id.asc())
        question = session.exec(statement).first()
        if question:
            logger.debug("兜底命中策略3（任意题）：用户ID=%s 题型=%s 题目ID=%s", user_id, q_type, question.id)
            session.expunge(question)
        return question


async def _get_fallback_question(user_id: int, q_type: str) -> Question | None:
    logger.debug("触发兜底题查询：用户ID=%s 题型=%s", user_id, q_type)
    question = await asyncio.to_thread(_select_fallback_question, user_id, q_type)
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
        # serialize question to json
        data = json.dumps(jsonable_encoder(question))
        key = f"{QUEUE_KEY_PREFIX}{user_id}"
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
        key = f"{QUEUE_KEY_PREFIX}{user_id}"
        logger.debug("清空题目队列：用户ID=%s redis_key=%s", user_id, key)
        await redis.delete(key, _queue_id_set_key(user_id), _queue_fp_set_key(user_id))
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
    """
    后台任务，用于生成'count'个问题并将其推送到Redis。
    """
    redis = Redis(connection_pool=pool)
    try:
        logger.debug("后台生成任务开始：用户ID=%s count=%s", user_id, count)
        tasks = [asyncio.create_task(generate_single_question(user_id)) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        queued_count = 0
        for q in results:
            if q:
                pushed = await push_question_to_queue(redis, user_id, q)
                if pushed:
                    queued_count += 1

        logger.info("后台生成题目完成：用户ID=%s 请求数量=%s 入队数量=%s", user_id, count, queued_count)
    except Exception as e:
        logger.exception("后台生成题目失败：用户ID=%s 错误=%s", user_id, str(e))
    finally:
        await redis.close()
