from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from app.db.database import SessionDep
from app.models.library import Library, LibraryVisibility
from app.api.dependencies import get_current_user
from app.db.library import get_library, create_library_, remove_library_, get_library_by_name
from app.models.user import User
from app.api.api_responses import success_response, conflict_response, not_found_response
from fastapi import Depends


router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("/get_libraries", response_model=list[Library])
async def get_libraries(session: SessionDep, user: User = Depends(get_current_user)):
    return success_response(data=jsonable_encoder(get_library(session, user.username)))

@router.post("/create_library")
async def create_library(session: SessionDep, library_in: Library, user: User = Depends(get_current_user)):
    library_in.creator_id = user.id
    library_in.visibility = LibraryVisibility.PRIVATE
    if get_library_by_name(session, library_in.name, user.username) is not None:
        return conflict_response(message="词库已存在！")
    create_library_(session, library_in)
    return success_response(message="创建词库成功！")

@router.post("/remove_library")
async def remove_library(session: SessionDep, library_name: Library, user: User = Depends(get_current_user)):
    if get_library_by_name(session, library_name.name, user.username) is None:
        return not_found_response(message="词库不存在！")
    remove_library_(session, get_library_by_name(session, library_name.name, user.username))
    return success_response(message="删除词库成功！")