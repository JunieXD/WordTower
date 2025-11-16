from sqlmodel import Session
from app.models import Word, WordCreate

def create_word(session: Session, word_in: WordCreate) -> Word:
