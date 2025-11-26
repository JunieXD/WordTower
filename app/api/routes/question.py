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
from app.db.word import random_select_word_by_type
from app.utils.config import settings

router = APIRouter(prefix="/api/question", tags=["question"])

@router.post("/generate/{floor}")
async def generate_question(session: SessionDep, floor: int, user: User = Depends(get_current_user)):
    type = random_select_question_type(floor)
    words = random_select_word_by_type(session, user, 1 if type != settings.QUESTION_TYPES[1] else 4)
    if not words:
        return not_found_response(message="没有找到足够的单词")
    question = await generate_question_(session, type, words)
    if not question:
        return internal_server_error_response(message="题目生成失败")
    return success_response(message="题目生成成功", data=jsonable_encoder(question))

@router.post("/check")
async def check_answer(session: SessionDep, question_check: QuestionCheck, user_in: User = Depends(get_current_user)):
    prompt = get_answer_check_prompt(question_check.target_word, question_check.chinese_sentence, question_check.user_input)
    if prompt is None:
        return not_found_response(message="提示词不存在")
    try:
        result = await generate_text(prompt)
        return success_response(message="检查完成", data=jsonable_encoder(result))
    except Exception as e:
        return internal_server_error_response(message=f"检查失败: {str(e)}", details={"error": str(e)})
    