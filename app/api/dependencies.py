from fastapi import Request, HTTPException, status
from app.utils.security import decode_token
from app.models.user import User
from app.db.user import get_user_by_username
from app.db.database import SessionDep
from app.utils.logger import get_logger, set_user_context

logger = get_logger(__name__)

def get_current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get("token")
    if not token:
        logger.warning("鉴权失败：缺少 token，路径=%s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权，请先登录"
        )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if not username:
            logger.warning("鉴权失败：token 载荷无效，路径=%s", request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        user = get_user_by_username(session, username)
        if user is None:
            logger.warning("鉴权失败：用户不存在，用户名=%s 路径=%s", username, request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        set_user_context(user.username)
        return user
    except HTTPException:
        raise
    except Exception:
        logger.exception("鉴权失败：token 校验异常，路径=%s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌验证失败"
        )
