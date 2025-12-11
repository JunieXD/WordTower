from app.db.database import Session
from app.models.question import Question
from app.models.question_word_link import QuestionWordLink
from app.models.word import Word
from app.utils.prompt import get_question_prompt
from app.utils.LLM import generate_question_with_validation, QuestionValidationError
from app.utils.config import settings, get_question_type_weights
from sqlmodel import select
import random
import json
import asyncio
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis, from_url
from app.db.database import engine
from app.models.user import User
from app.db.word import random_select_word_by_type
from app.db.challenge import get_current_floor
from sqlmodel import Session as DBSession
from app.models.word import Word
from app.db.redis import pool

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

def _prepare_generation_data(user_id: int):
    """
    同步函数：准备生成题目所需的数据（在线程池中运行）
    """
    with DBSession(engine) as session:
        user = session.get(User, user_id)
        if not user:
            return None
            
        floor = get_current_floor(session, user) or 1
        weights = get_question_type_weights(floor)
        q_type = random.choices(settings.QUESTION_TYPES, weights=weights)[0]
        
        word_count = 4 if q_type == "cloze_test" else 1
        words = random_select_word_by_type(session, user, word_count)
        
        if len(words) < word_count:
            return None
        
        if word_count > 1:
            prompt_input = [w.text for w in words]
        else:
            prompt_input = words[0].text
        
        prompt = get_question_prompt(q_type, prompt_input)
        if not prompt:
            return None
            
        # 返回必要的数据，word对象需要转换为ID列表以跨Session传递
        return q_type, [w.id for w in words], prompt

def _save_generated_question(type: str, content: dict, word_ids: list[int]) -> Question:
    """
    同步函数：保存生成的题目（在线程池中运行）
    """
    with DBSession(engine) as session:
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
        return question

async def generate_single_question(user_id: int) -> Question | None:
    """
    为用户生成一个单独的问题。
    异步协调：同步DB读 -> 异步LLM -> 同步DB写
    """
    try:
        # 1. 在线程池中执行同步的数据库读取操作
        result = await asyncio.to_thread(_prepare_generation_data, user_id)
        if not result:
            return None
            
        q_type, word_ids, prompt = result
        
        # 2. 异步调用 LLM 并验证生成的题目 (I/O bound)
        content = await generate_question_with_validation(prompt, q_type)
        
        # 3. 在线程池中执行同步的数据库写入操作
        question = await asyncio.to_thread(_save_generated_question, q_type, content, word_ids)
        
        return question
    except Exception as e:
        print(f"Error generating question for user {user_id}: {e}")
        return None

async def push_question_to_queue(redis: Redis, user_id: int, question: Question):
    """
    将问题JSON推送到用户的Redis队列中。
    """
    try:
        # serialize question to json
        data = json.dumps(jsonable_encoder(question))
        key = f"{QUEUE_KEY_PREFIX}{user_id}"
        await redis.lpush(key, data)
    except Exception as e:
        print(e)

async def clear_question_queue(redis: Redis, user_id: int):
    """
    清空用户的题目队列。
    """
    try:
        key = f"{QUEUE_KEY_PREFIX}{user_id}"
        await redis.delete(key)
    except Exception as e:
        print(e)

async def process_generated_questions(user_id: int, tasks: list[asyncio.Task], exclude_question_id: int | None = None):
    """
    处理生成的题目任务，将结果推入队列 (排除已返回的题目)
    """
    redis = Redis(connection_pool=pool)
    try:
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for q in results:
            if isinstance(q, Exception) or q is None:
                continue
                
            # 如果是已经返回给用户的题目，跳过入队
            if exclude_question_id and q.id == exclude_question_id:
                continue
                
            await push_question_to_queue(redis, user_id, q)
    except Exception as e:
        print(e)
    finally:
        await redis.close()

async def generate_questions_background_task(user_id: int, count: int):
    """
    后台任务，用于生成'count'个问题并将其推送到Redis。
    """
    redis = Redis(connection_pool=pool)
    try:
        tasks = [asyncio.create_task(generate_single_question(user_id)) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        
        for q in results:
            if q:
                await push_question_to_queue(redis, user_id, q)
    except Exception as e:
        print(e)
    finally:
        await redis.close()