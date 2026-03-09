from fastapi import APIRouter
from app.utils.LLM import generate_text
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
from app.db.question import generate_questions_background_task, generate_single_question, QUEUE_KEY_PREFIX, process_generated_questions
from app.db.level import link_level_question
from fastapi import BackgroundTasks
import asyncio
import json
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/question", tags=["question"])
logger = get_logger(__name__)

@router.get("/get")
async def get_question(
    background_tasks: BackgroundTasks,
    user_in: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)
):
    key = f"{QUEUE_KEY_PREFIX}{user_in.id}"
    # 尝试从队列获取题目
    while True:
        data = await redis.rpop(key)
        if not data:
            break
        try:
            question_data = json.loads(data)
            background_tasks.add_task(generate_questions_background_task, user_in.id, 1)
            logger.info("获取题目：从队列命中，用户ID=%s", user_in.id)
            return success_response(data=question_data)
        except json.JSONDecodeError:
            logger.warning("获取题目：队列数据损坏，用户ID=%s", user_in.id)
            pass

    # 队列为空，启动4个生成任务
    tasks = [asyncio.create_task(generate_single_question(user_in.id)) for _ in range(5)]
    
    question_to_return = None
    
    # 获取第一个完成的任务结果
    for future in asyncio.as_completed(tasks):
        try:
            q = await future
            if q:
                question_to_return = q
                break
        except Exception:
            continue
            
    if not question_to_return:
        logger.error("获取题目失败：生成结果为空，用户ID=%s", user_in.id)
        return not_found_response(message="无法生成题目，请检查词库是否充足")
        
    # 其余的任务交给后台处理，并将结果推入队列
    background_tasks.add_task(process_generated_questions, user_in.id, tasks, question_to_return.id)
    logger.info("获取题目：实时生成成功，用户ID=%s 题目ID=%s", user_in.id, question_to_return.id)
        
    return success_response(data=jsonable_encoder(question_to_return))

@router.post("/check")
async def check_answer(question_check_in: QuestionCheck, user_in: User = Depends(get_current_user)):
    prompt = get_answer_check_prompt(question_check_in.target_word, question_check_in.chinese_sentence, question_check_in.user_input)
    if prompt is None:
        logger.warning("检查答案失败：提示词不存在，用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return not_found_response(message="提示词不存在")
    try:
        result = await generate_text(prompt)
        logger.info("检查答案成功：用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return success_response(message="检查完成", data=jsonable_encoder(result))
    except Exception as e:
        logger.exception("检查答案失败：服务异常，用户ID=%s 目标词=%s", user_in.id, question_check_in.target_word)
        return internal_server_error_response(message=f"检查失败: {str(e)}", details={"error": str(e)})
    
@router.post("/answer/{question_id}")
def answer_question(
    session: SessionDep,
    question_id: int,
    answer: QuestionAnswer,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        logger.warning("记录作答失败：题目不存在，用户ID=%s 题目ID=%s", user_in.id, question_id)
        return not_found_response(message="题目不存在")
    try:
        user_question_answer(session, user_in, question, answer.is_correct)
        # 绑定题目和关卡
        link_level_question(session, answer.level_id, question_id)
        logger.info(
            "记录作答：用户ID=%s 题目ID=%s 关卡ID=%s 是否正确=%s",
            user_in.id,
            question_id,
            answer.level_id,
            answer.is_correct,
        )
        return success_response(message="作答记录成功")
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
