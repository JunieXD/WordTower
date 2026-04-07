import time
from fastapi import FastAPI, Request
from app.api.routes import auth
from app.api.routes import library, word, upgrade, question, combat, social, history, daily_challenge
from fastapi.middleware.cors import CORSMiddleware
from app.utils.cors import origins
from app.utils.security import decode_token
from app.db.social_presence import touch_user_presence
from app.utils.logger import (
    clear_request_context,
    get_logger,
    set_request_context,
    setup_logging,
)

setup_logging()
logger = get_logger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,             # 允许跨域请求的来源列表
    allow_credentials=True,            # 允许携带认证信息（如 Cookies/Authorization 头部）
    allow_methods=["*"],               # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],               # 允许所有请求头部
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    user_label = "未登录"
    token = request.cookies.get("token")
    username = None
    if token:
        payload = decode_token(token)
        if payload and payload.get("sub"):
            username = payload.get("sub")
            user_label = username

    context_token = set_request_context(user_label)
    client_ip = request.client.host if request.client else "-"
    start = time.perf_counter()

    try:
        if username:
            try:
                await touch_user_presence(username, request.url.path)
            except Exception:
                logger.warning("刷新社交在线态失败：用户名=%s 路径=%s", username, request.url.path)
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "HTTP请求异常 方法=%s 路径=%s 状态码=%s 客户端IP=%s 耗时=%.2fms",
            request.method,
            request.url.path,
            500,
            client_ip,
            duration_ms,
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "HTTP请求 方法=%s 路径=%s 状态码=%s 客户端IP=%s 耗时=%.2fms",
            request.method,
            request.url.path,
            response.status_code,
            client_ip,
            duration_ms,
        )
        return response
    finally:
        clear_request_context(context_token)


@app.on_event("startup")
async def on_startup():
    logger.info("服务启动：WordTower 后端已启动")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("服务停止：WordTower 后端已停止")


app.include_router(auth.router)
app.include_router(library.router)
app.include_router(upgrade.router)
app.include_router(word.router)
app.include_router(question.router)
app.include_router(combat.router)
app.include_router(social.router)
app.include_router(history.router)
app.include_router(daily_challenge.router)
