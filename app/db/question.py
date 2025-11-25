from app.db.database import Session
from app.models.question import Question
from app.utils.prompt import get_question_prompt
from app.utils.LLM import generate_text
from app.utils.config import settings, get_question_type_weights
import random

def create_question_(session: Session, question: Question) -> Question:
    session.add(question)
    session.commit()
    session.refresh(question)
    return question

async def generate_question_(session: Session, type: str, target_word: str | list[str]) -> Question | None:
    if type not in settings.QUESTION_TYPES:
        return None
    prompt = get_question_prompt(type, target_word)
    if prompt is None:
        return None
    try:
        question = Question(type=type, content=await generate_text(prompt))
        question = create_question_(session, question)
        return question
    except Exception:
        return None

def random_select_question_type(floor: int) -> str:
    weights = get_question_type_weights(floor)
    return random.choices(settings.QUESTION_TYPES, weights=weights)[0]