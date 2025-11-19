from sqlmodel import Session, select, func, case
from app.models.word import Word


def search_word_top_10(session: Session, q: str) -> list[Word]:
    """按匹配度排序搜索单词"""
    # 使用 case 语句按匹配优先级排序
    # 1. 完全匹配 (priority=3)
    # 2. 开头匹配 (priority=2)
    # 3. 包含匹配 (priority=1)
    priority = case(
        (func.lower(Word.text) == func.lower(q), 3),
        (func.lower(Word.text).startswith(func.lower(q)), 2),
        else_=1
    )
    
    statement = (
        select(Word)
        .where(Word.text.ilike(f"%{q}%"))
        .where(~Word.text.contains(" "))
        .where(~Word.text.contains("."))
        .where(~Word.text.contains("'"))
        .order_by(priority.desc(), func.length(Word.text), Word.text)
        .limit(10)
    )
    return session.exec(statement).all()

def get_word_by_id(session: Session, word_id: int) -> Word | None:
    statement = select(Word).where(Word.id == word_id)
    return session.exec(statement).one_or_none()
    
def get_words_by_ids(session: Session, word_ids: list[int]) -> list[Word]:
    statement = select(Word).where(Word.id.in_(word_ids))
    return session.exec(statement).all()

def batch_recognize_(session: Session, words: list[str]) -> list[Word]:
    if not words:
        return []
    statement = select(Word).where(Word.text.in_(words))
    return session.exec(statement).all()
