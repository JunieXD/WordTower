from fastapi import APIRouter, Depends
from app.db.database import SessionDep
from app.db.user import get_user_by_username, create_user, set_user_last_login
from app.api.api_responses import success_response, created_response, not_found_response, conflict_response
from app.models.user import UserCreate, UserRead, UserLogin, User
from app.utils.security import verify_password, encode_token
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register")
async def register(session: SessionDep, user_in: UserCreate):
    user = create_user(session, user_in)
    if user is None:
        return conflict_response(message="用户已存在")
    return created_response(message="注册成功")

@router.post("/login")
async def login(session: SessionDep, user_in: UserLogin):
    user = get_user_by_username(session, user_in.username)
    if user is None:
        return not_found_response(message="用户不存在")
    if not verify_password(user_in.password, user.password_hash):
        return not_found_response(message="用户名或密码错误")
    token = encode_token(user)
    set_user_last_login(session, user.username)
    return success_response(message="登录成功", cookie=token)

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return success_response(message="登出成功", delete_cookie=True)

@router.get("/profile", response_model=UserRead)
async def profile(current_user: User = Depends(get_current_user)):
    return current_user