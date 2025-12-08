from fastapi import APIRouter
from app.utils.LLM import generate_text
from app.db.database import SessionDep
from app.db.question import generate_question_
from app.models.question import QuestionCheck
from app.models.user import User
from app.api.dependencies import get_current_user
from fastapi import Depends
from app.utils.prompt import get_answer_check_prompt
from app.api.api_responses import success_response, not_found_response, internal_server_error_response
from fastapi.encoders import jsonable_encoder
from app.db.question import random_select_question_type
from app.db.challenge import get_current_floor
from app.db.word import random_select_word_by_type
from app.utils.config import settings
from app.models.question import Question, QuestionAnswer, QuestionReport, QuestionRating
from app.db.level import insert_level_question_link, get_current_level
from app.api.dependencies import get_current_user
from app.db.question import insert_question_word_link
from app.db.question import get_unanswered_question_for_current_level
from app.db.user import user_question_answer, user_question_report, user_question_rating

router = APIRouter(prefix="/api/question", tags=["question"])

@router.post("/generate")
async def generate_question(session: SessionDep, user: User = Depends(get_current_user)):
    floor = get_current_floor(session, user)
    if not floor:
        return not_found_response(message="没有进行中的挑战")
    type = random_select_question_type(floor)
    words = random_select_word_by_type(session, user, 1 if type != settings.QUESTION_TYPES[1] else 4)
    if not words:
        return not_found_response(message="没有找到足够的单词")
    question = await generate_question_(session, type, words)
    if not question:
        return internal_server_error_response(message="题目生成失败")
    level = get_current_level(session, user)
    if not level:
        return internal_server_error_response(message="当前楼层不存在")
    insert_level_question_link(session, level, question)
    for word in words:
        insert_question_word_link(session, question, word)
    question_data = Question.model_validate(question, from_attributes=True).model_dump()
    return success_response(message="题目生成成功", data=jsonable_encoder(question_data))

@router.get("/unanswered")
async def get_unanswered_question(session: SessionDep, user: User = Depends(get_current_user)):
    """返回当前用户在当前挑战关卡中已生成但尚未作答的一道题目。"""

    question = get_unanswered_question_for_current_level(session, user)
    if not question:
        return not_found_response(message="没有未作答的题目")
    question_data = Question.model_validate(question, from_attributes=True).model_dump()
    return success_response(message="获取成功", data=jsonable_encoder(question_data))

@router.post("/check")
async def check_answer(question_check_in: QuestionCheck, user_in: User = Depends(get_current_user)):
    prompt = get_answer_check_prompt(question_check_in.target_word, question_check_in.chinese_sentence, question_check_in.user_input)
    if prompt is None:
        return not_found_response(message="提示词不存在")
    try:
        result = await generate_text(prompt)
        return success_response(message="检查完成", data=jsonable_encoder(result))
    except Exception as e:
        return internal_server_error_response(message=f"检查失败: {str(e)}", details={"error": str(e)})
    
@router.post("/answer/{question_id}")
async def answer_question(
    session: SessionDep,
    question_id: int,
    answer: QuestionAnswer,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        return not_found_response(message="题目不存在")
    try:
        user_question_answer(session, user_in, question, answer.is_correct)
        return success_response(message="作答记录成功")
    except Exception as e:
        return internal_server_error_response(message=f"作答记录失败: {str(e)}", details={"error": str(e)})
    
@router.post("/report/{question_id}")
async def report_question(
    session: SessionDep,
    question_id: int,
    report: QuestionReport,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        return not_found_response(message="题目不存在")
    try:
        user_question_report(session, user_in, question, report.report)
        return success_response(message="报告成功")
    except Exception as e:
        return internal_server_error_response(message=f"报告失败: {str(e)}", details={"error": str(e)})
    
@router.post("/rating/{question_id}")
async def rating_question(
    session: SessionDep,
    question_id: int,
    rating: QuestionRating,
    user_in: User = Depends(get_current_user),
):
    question = session.get(Question, question_id)
    if not question:
        return not_found_response(message="题目不存在")
    try:
        user_question_rating(session, user_in, question, rating.rating)
        return success_response(message="评分成功")
    except Exception as e:
        return internal_server_error_response(message=f"评分失败: {str(e)}", details={"error": str(e)})