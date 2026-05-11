from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from app.db.database import SessionDep
from app.db.user import get_user_by_username, get_users_by_username, create_user
from app.api.api_responses import success_response, created_response, not_found_response, conflict_response
from app.models.user import UserCreate, UserLogin, User, UserRead
from app.utils.security import verify_password, encode_token
from app.api.dependencies import get_current_user
from app.utils.logger import get_logger
from datetime import datetime, timezone

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
    users = get_users_by_username(session, user_in.username)
    if not users:
        logger.warning("登录失败：用户不存在，用户名=%s", user_in.username)
        return not_found_response(message="用户不存在")

    if len(users) > 1:
        logger.error("登录检测到重复用户名：用户名=%s 数量=%s", user_in.username, len(users))

    user = None
    for candidate in users:
        if verify_password(user_in.password, candidate.password_hash):
            user = candidate
            break

    if user is None:
        logger.warning("登录失败：密码错误，用户名=%s", user_in.username)
        return not_found_response(message="用户名或密码错误")

    token = encode_token(user)
    user.last_login = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
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
