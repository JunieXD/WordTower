from sqlmodel import Session, select, func
from app.models.word import Word
from app.models.user import User
from app.models.user_library_select import UserLibrarySelect
from app.models.library_word_link import LibraryWordLink
from app.services.spaced_repetition import select_words_with_srs_priority

def _clean_word_filters() -> tuple:
    return (
        Word.text.notlike("% %"),
        Word.text.notlike("%.%"),
        Word.text.notlike("%'%"),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_word_top_10(session: Session, q: str | None) -> list[Word]:
    """按匹配优先级搜索单词：精确匹配 > 前缀匹配 > 包含匹配。"""
    if q is None:
        return []
    query = q.strip().lower()
    if not query:
        return []

    limit = 10
    query_escaped = _escape_like(query)
    prefix_pattern = f"{query_escaped}%"
    contains_pattern = f"%{query_escaped}%"

    filters = _clean_word_filters()
    result: list[Word] = []
    seen_ids: set[int] = set()

    def append_unique(items: list[Word]) -> None:
        for item in items:
            if item.id is None or item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            result.append(item)
            if len(result) >= limit:
                return

    exact_statement = (
        select(Word)
        .where(*filters)
        .where(func.lower(Word.text) == query)
        .order_by(func.length(Word.text), Word.text)
        .limit(limit)
    )
    append_unique(session.exec(exact_statement).all())
    if len(result) >= limit:
        return result

    prefix_statement = (
        select(Word)
        .where(*filters)
        .where(func.lower(Word.text).like(prefix_pattern, escape="\\"))
        .where(func.lower(Word.text) != query)
        .order_by(func.length(Word.text), Word.text)
        .limit(limit)
    )
    append_unique(session.exec(prefix_statement).all())
    if len(result) >= limit:
        return result

    # 单字符查询只做精确/前缀匹配，避免高并发下的 contains 全表压力。
    if len(query) == 1:
        return result

    contains_statement = (
        select(Word)
        .where(*filters)
        .where(Word.text.ilike(contains_pattern, escape="\\"))
        .where(func.lower(Word.text) != query)
        .where(~func.lower(Word.text).like(prefix_pattern, escape="\\"))
        .order_by(func.length(Word.text), Word.text)
        .limit(limit)
    )
    append_unique(session.exec(contains_statement).all())
    return result

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

def get_user_selected_words(session: Session, user: User) -> list[Word]:
    """获取用户选择的所有单词（去重）"""
    statement = (
        select(Word)
        .join(LibraryWordLink, Word.id == LibraryWordLink.word_id)
        .join(UserLibrarySelect, LibraryWordLink.library_id == UserLibrarySelect.library_id)
        .where(UserLibrarySelect.user_id == user.id)
        .distinct()
    )
    return session.exec(statement).all()

def random_select_word_by_type(session: Session, user: User, num: int) -> list[Word]:
    all_words = get_user_selected_words(session, user)
    if num > len(all_words):
        return []
    return select_words_with_srs_priority(session, user, all_words, num)

def get_word_by_text(session: Session, text: str) -> Word | None:
    statement = select(Word).where(Word.text == text)
    return session.exec(statement).one_or_none()

def get_user_selected_words_count(session: Session, user: User) -> int:
    """获取用户选择的词库包含的单词总数（去重）"""
    statement = (
        select(func.count(func.distinct(Word.id)))
        .select_from(Word)
        .join(LibraryWordLink, Word.id == LibraryWordLink.word_id)
        .join(UserLibrarySelect, LibraryWordLink.library_id == UserLibrarySelect.library_id)
        .where(UserLibrarySelect.user_id == user.id)
    )
    return session.exec(statement).one()
