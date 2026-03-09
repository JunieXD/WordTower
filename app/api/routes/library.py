from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from app.db.database import SessionDep
from app.models.library import Library, LibraryVisibility, LibraryWithWordsId, LibraryDetail
from app.api.dependencies import get_current_user
from app.db.library import (
    get_libraries_,
    get_user_selected_libraries_,
    create_library_,
    remove_library_,
    get_library_by_id,
    toggle_user_library_select_,
    get_library_details_,
    update_library_details_,
    update_user_library_select_priority_,
)
from app.models.user import User
from app.api.api_responses import success_response, forbidden_response, not_found_response
from fastapi import Depends
from app.db.word import get_words_by_ids, get_user_selected_words_count
from app.models.user_library_select import UpdatePriorityRequest
from app.db.question import clear_question_queue
from app.db.redis import get_redis
from redis.asyncio import Redis
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/library", tags=["library"])
logger = get_logger(__name__)

@router.get("/get_libraries")
async def get_libraries(session: SessionDep, user_in: User = Depends(get_current_user)):
    logger.info("获取词库列表：用户ID=%s", user_in.id)
    return success_response(data=jsonable_encoder(get_libraries_(session, user_in)))

@router.get("/get_selected_libraries")
async def get_selected_libraries(session: SessionDep, user_in: User = Depends(get_current_user)):
    logger.info("获取已选词库：用户ID=%s", user_in.id)
    return success_response(data=jsonable_encoder(get_user_selected_libraries_(session, user_in)))

@router.get("/get_selected_words_count")
async def get_selected_words_count(session: SessionDep, user_in: User = Depends(get_current_user)):
    """获取用户选择的词库包含的单词总数（去重）"""
    count = get_user_selected_words_count(session, user_in)
    logger.info("获取已选词数量：用户ID=%s 数量=%s", user_in.id, count)
    return success_response(data={"count": count})

@router.post("/create_library")
async def create_library(session: SessionDep, library_in: Library, user_in: User = Depends(get_current_user)):
    library_in.creator_id = user_in.id
    library_in.visibility = LibraryVisibility.PRIVATE
    create_library_(session, library_in)
    logger.info("创建词库：用户ID=%s 词库名=%s", user_in.id, library_in.name)
    return success_response(message=f"创建词库{library_in.name}成功！")

@router.delete("/remove_library/{library_id}")
async def remove_library(session: SessionDep, library_id: int, user_in: User = Depends(get_current_user)):
    library = get_library_by_id(session, library_id)
    if library is None:
        logger.warning("删除词库失败：词库不存在，用户ID=%s 词库ID=%s", user_in.id, library_id)
        return not_found_response(message="词库不存在！")
    if library.creator_id != user_in.id:
        logger.warning("删除词库失败：无权限，用户ID=%s 词库ID=%s", user_in.id, library_id)
        return forbidden_response(message="无权限删除词库！")
    remove_library_(session, library)
    logger.info("删除词库：用户ID=%s 词库ID=%s 词库名=%s", user_in.id, library.id, library.name)
    return success_response(message=f"删除词库{library.name}成功！")

@router.post("/toggle_user_library_select/{library_id}")
async def toggle_user_library_select(session: SessionDep, library_id: int, user_in: User = Depends(get_current_user), redis: Redis = Depends(get_redis)):
    library = get_library_by_id(session, library_id)
    if library is None:
        logger.warning("切换词库选择失败：词库不存在，用户ID=%s 词库ID=%s", user_in.id, library_id)
        return not_found_response(message="词库不存在！")
    selected = toggle_user_library_select_(session, user_in, library)
    # 切换词库后清空用户的题目队列
    await clear_question_queue(redis, user_in.id)
    logger.info("切换词库选择：用户ID=%s 词库ID=%s 选中=%s", user_in.id, library.id, selected)
    return success_response(message=f"词库{library.name}{'成功选中' if selected else '取消选中'}！")

@router.put("/batch_update_library_priorities")
async def batch_update_library_priorities(
    session: SessionDep, 
    priorities: UpdatePriorityRequest,
    user_in: User = Depends(get_current_user)
):
    updated_count = 0
    for item in priorities.priorities:
        library = get_library_by_id(session, item.library_id)
        if library:
            update_user_library_select_priority_(session, user_in, library, item.priority)
            updated_count += 1
    logger.info(
        "批量更新词库优先级：用户ID=%s 实际更新=%s 请求数量=%s",
        user_in.id,
        updated_count,
        len(priorities.priorities),
    )
    return success_response(message="词库优先级更新成功！")

@router.get("/get_library_details/{library_id}")
async def get_library_details(session: SessionDep, library_id: int, user_in: User = Depends(get_current_user)):
    library = get_library_by_id(session, library_id)
    if library is None:
        logger.warning("获取词库详情失败：词库不存在，用户ID=%s 词库ID=%s", user_in.id, library_id)
        return not_found_response(message="词库不存在！")
    logger.info("获取词库详情：用户ID=%s 词库ID=%s", user_in.id, library_id)
    return success_response(data=jsonable_encoder(get_library_details_(session, library_id)))

@router.put("/update_library/{library_id}")
async def update_library(session: SessionDep, library_id: int, library_in: LibraryWithWordsId, user_in: User = Depends(get_current_user)):
    library_in.id = library_id
    if get_library_by_id(session, library_id) is None:
        logger.warning("更新词库失败：词库不存在，用户ID=%s 词库ID=%s", user_in.id, library_id)
        return not_found_response(message="词库不存在！")
    
    # 构建 LibraryDetail 对象
    library_detail = LibraryDetail.model_validate(library_in, from_attributes=True)
    library_detail.words = get_words_by_ids(session, library_in.words_id)
    
    update_library_details_(session, library_detail)
    logger.info(
        "更新词库：用户ID=%s 词库ID=%s 词库名=%s 单词数=%s",
        user_in.id,
        library_id,
        library_in.name,
        len(library_in.words_id),
    )
    return success_response(message=f"更新词库{library_in.name}成功！")
