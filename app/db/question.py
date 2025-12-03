from app.db.database import Session
from app.models.question import Question
from app.db.user import insert_user_word_record
from app.models.question_word_link import QuestionWordLink
from app.models.word import Word
from app.utils.prompt import get_question_prompt
from app.utils.LLM import generate_text
from app.utils.config import settings, get_question_type_weights
from app.models.user import User
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

def answer_question_(session: Session, question: Question, user: User, is_correct: bool) -> None:
    words = get_question_words(session, question)
    for word in words:
        insert_user_word_record(session, user, word, is_correct)