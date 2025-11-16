from fastapi import APIRouter
from app.db.database import SessionDep
from app.models.library import Library
from app.api.dependencies import get_current_user
from app.db.library import get_library, create_library_ 
from app.models.user import User
from app.api.api_responses import success_response
from fastapi import Depends
from app.models.library import Library


router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("/get_libraries", response_model=list[Library])
async def get_libraries(session: SessionDep, user: User = Depends(get_current_user)):
    return success_response(data=get_library(session, user.username))

@router.post("/create_library")
async def create_library(session: SessionDep, library_in: Library, user: User = Depends(get_current_user)):
    create_library_(session, library_in)
    return success_response(message="创建词库成功！")