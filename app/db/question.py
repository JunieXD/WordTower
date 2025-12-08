from app.db.database import Session
from app.models.question import Question
from app.models.question_word_link import QuestionWordLink
from app.models.word import Word
from app.utils.prompt import get_question_prompt
from app.utils.LLM import generate_text
from app.utils.config import settings, get_question_type_weights
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord
from app.models.level_question_link import LevelQuestionLink
from app.db.level import get_current_level
from sqlmodel import select
import random

def create_question_(session: Session, question: Question) -> Question:
    session.add(question)
    session.commit()
    session.refresh(question)
    return question

def insert_question_word_link(session: Session, question: Question, word: Word) -> None:
    question_word_link = QuestionWordLink(question_id=question.id, word_id=word.id)
    session.add(question_word_link)
    session.commit()

async def generate_question_(session: Session, type: str, target_words: list[Word]) -> Question | None:
    if type not in settings.QUESTION_TYPES:
        return None
    prompt = get_question_prompt(type, [word.text for word in target_words])
    if prompt is None:
        return None

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            question = Question(type=type, content=await generate_text(prompt))
            question = create_question_(session, question)
            return question
        except Exception:
            if attempt == max_retries:
                return None
            continue

def random_select_question_type(floor: int) -> str:
    weights = get_question_type_weights(floor)
    return random.choices(settings.QUESTION_TYPES, weights=weights)[0]

def get_question_words(session: Session, question: Question) -> list[Word]:
    statement = select(Word).join(QuestionWordLink).where(QuestionWordLink.question_id == question.id)
    return session.exec(statement).all()


def get_unanswered_question_for_current_level(session: Session, user: User) -> Question | None:
    """获取用户当前关卡中尚未作答的一道题目。如果不存在则返回 None。"""

    level = get_current_level(session, user)
    if not level:
        return None

    # 查询当前关卡下的所有题目
    statement = (
        select(Question)
        .join(LevelQuestionLink, LevelQuestionLink.question_id == Question.id)
        .where(LevelQuestionLink.level_id == level.id)
    )
    questions = session.exec(statement).all()
    if not questions:
        return None

    question_ids = [q.id for q in questions if q.id is not None]
    if not question_ids:
        return None

    # 查询用户已经作答过的题目
    answered_stmt = (
        select(UserQuestionRecord)
        .where(UserQuestionRecord.user_id == user.id)
        .where(UserQuestionRecord.question_id.in_(question_ids))
    )
    answered_records = session.exec(answered_stmt).all()
    answered_ids = {record.question_id for record in answered_records}

    # 返回第一道未作答的题目
    for question in questions:
        if question.id not in answered_ids:
            return question

    return None