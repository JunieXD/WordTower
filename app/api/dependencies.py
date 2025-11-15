from fastapi import Depends, Request, HTTPException, status
from app.utils.security import decode_token
from app.models.user import User
from app.db.user import get_user_by_username
from app.db.database import SessionDep

def get_current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权，请先登录"
        )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        user = get_user_by_username(session, username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌验证失败"
        )