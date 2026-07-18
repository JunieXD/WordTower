from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.db.database import engine
from app.db.redis import pool
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def ready() -> JSONResponse:
    redis = Redis(connection_pool=pool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        await redis.ping()
    except Exception:
        logger.warning("健康检查失败：基础设施不可用", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    finally:
        await redis.aclose()

    return JSONResponse(status_code=200, content={"status": "ok"})
