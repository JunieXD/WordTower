from fastapi import APIRouter
from app.db.database import SessionDep
from app.models.library import Library
from app.api.dependencies import get_current_user
from app.db.library import get_library
from app.models.user import User
from app.api.api_responses import success_response
from fastapi import Depends

router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("/get_libraries", response_model=list[Library])
async def get_libraries(session: SessionDep, user: User = Depends(get_current_user)):
    return success_response(data=get_library(session, user.username))
