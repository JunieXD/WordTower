from app.models.library import Library, LibraryWithSelectAndPriority, LibraryVisibility, LibraryDetail
from app.models.user_library_select import UserLibrarySelect
from sqlmodel import select
from app.db.database import Session
from app.models.user import User
from app.models.word import Word
from app.models.library_word_link import LibraryWordLink
from datetime import datetime, timezone

def get_library_by_id(session: Session, library_id: int) -> Library | None:
    statement = select(Library).where((Library.id == library_id))
    return session.exec(statement).one_or_none()

def get_libraries_(session: Session, user: User) -> list[LibraryWithSelectAndPriority]:
    # 查询所有用户可以访问的词库（公开的或用户自己创建的）
    statement = select(Library).where(
        (Library.visibility == LibraryVisibility.PUBLIC) | (Library.creator_id == user.id)
    )
    libraries = session.exec(statement).all()
    
    # 获取用户选择的所有词库及其优先级
    select_statement = select(UserLibrarySelect).where(UserLibrarySelect.user_id == user.id)
    user_selections = session.exec(select_statement).all()
    
    # 构建词库ID到优先级的映射
    library_priority_map = {sel.library_id: sel.priority for sel in user_selections}
    selected_library_ids = set(library_priority_map.keys())
    
    # 构建返回结果，包含 selected 和 priority 字段
    result = []
    for library in libraries:
        library_with_select = LibraryWithSelectAndPriority.model_validate(library, from_attributes=True)
        library_with_select.selected = library.id in selected_library_ids
        library_with_select.priority = library_priority_map.get(library.id)
        result.append(library_with_select)
    
    return result

def get_user_selected_libraries_(session: Session, user: User) -> list[LibraryWithSelectAndPriority]:
    """获取用户已选择的所有词库"""
    libraries = get_libraries_(session, user)
    return [library for library in libraries if library.selected]

def create_library_(session: Session, library: Library) -> None:
    session.add(library)
    session.commit()

def remove_library_(session: Session, library: Library) -> None:
    session.exec(LibraryWordLink.__table__.delete().where(LibraryWordLink.library_id == library.id))
    session.exec(UserLibrarySelect.__table__.delete().where(UserLibrarySelect.library_id == library.id))
    session.delete(library)
    session.commit()

def toggle_user_library_select_(session: Session, user: User, library: Library) -> bool:
    statement = select(UserLibrarySelect).where((UserLibrarySelect.user_id == user.id) & (UserLibrarySelect.library_id == library.id))
    record = session.exec(statement).one_or_none()
    if record is None:
        session.add(UserLibrarySelect(user_id=user.id, library_id=library.id, priority=0))
        session.commit()
        return True
    else:
        session.delete(record)
        session.commit()
        return False

def update_user_library_select_priority_(session: Session, user: User, library: Library, priority: int) -> None:
    statement = select(UserLibrarySelect).where((UserLibrarySelect.user_id == user.id) & (UserLibrarySelect.library_id == library.id))
    record = session.exec(statement).one_or_none()
    if record is not None:
        record.priority = priority
        session.add(record)
        session.commit()

def get_library_details_(session: Session, library_id: int) -> LibraryDetail:
    # 获取词库基本信息
    library = get_library_by_id(session, library_id)
    if not library:
        return None
    
    # 获取词库中的单词
    word_statement = select(LibraryWordLink.word_id).where(LibraryWordLink.library_id == library_id)
    words_id = session.exec(word_statement).all()
    words = session.exec(select(Word).where(Word.id.in_(words_id))).all() if words_id else []
    
    # 构建返回结果
    library_detail = LibraryDetail.model_validate(library, from_attributes=True)
    library_detail.words = words
    return library_detail

def update_library_details_(session: Session, library: LibraryDetail) -> None:
    db_library = get_library_by_id(session, library.id)
    if db_library:
        # 清除现有的词库-单词关联
        session.exec(LibraryWordLink.__table__.delete().where(LibraryWordLink.library_id == library.id))
        
        # 添加新的词库-单词关联
        new_links = [LibraryWordLink(library_id=library.id, word_id=word.id) for word in library.words]
        session.add_all(new_links)
        
        # 更新词库信息
        db_library.name = library.name
        db_library.description = library.description
        db_library.visibility = library.visibility
        db_library.word_count = len(library.words)
        db_library.updated_at = datetime.now(timezone.utc)
        session.add(db_library)
        
        session.commit()