from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from app.db.database import SessionDep
from app.db.user import get_user_by_username, create_user, set_user_last_login
from app.api.api_responses import success_response, created_response, not_found_response, conflict_response
from app.models.user import UserCreate, UserLogin, User, UserRead
from app.utils.security import verify_password, encode_token
from app.api.dependencies import get_current_user
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)

@router.post("/register")
async def register(session: SessionDep, user_in: UserCreate):
    if get_user_by_username(session, user_in.username):
        logger.warning("注册失败：用户已存在，用户名=%s", user_in.username)
        return conflict_response(message="用户已存在")
    create_user(session, user_in)
    logger.info("注册成功：用户名=%s", user_in.username)
    return created_response(message="注册成功")

@router.post("/login")
async def login(session: SessionDep, user_in: UserLogin):
    user = get_user_by_username(session, user_in.username)
    if user is None:
        logger.warning("登录失败：用户不存在，用户名=%s", user_in.username)
        return not_found_response(message="用户不存在")
    if not verify_password(user_in.password, user.password_hash):
        logger.warning("登录失败：密码错误，用户名=%s", user_in.username)
        return not_found_response(message="用户名或密码错误")
    token = encode_token(user)
    set_user_last_login(session, user.username)
    logger.info("登录成功：用户ID=%s 用户名=%s", user.id, user.username)
    return success_response(message="登录成功", cookie=token)

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    logger.info("登出成功：用户ID=%s 用户名=%s", current_user.id, current_user.username)
    return success_response(message="登出成功", delete_cookie=True)

@router.get("/profile")
async def profile(current_user: User = Depends(get_current_user)):
    user_read = UserRead.model_validate(current_user, from_attributes=True)
    logger.info("获取用户资料：用户ID=%s 用户名=%s", current_user.id, current_user.username)
    return success_response(data=jsonable_encoder(user_read))
