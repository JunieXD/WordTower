from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder

from app.api.api_responses import not_found_response, success_response
from app.api.dependencies import get_current_user
from app.db.database import SessionDep
from app.db.history import get_history_run_detail, list_history_runs
from app.models.user import User
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/history", tags=["history"])
logger = get_logger(__name__)


@router.get("/runs")
async def get_history_runs(session: SessionDep, current_user: User = Depends(get_current_user)):
    runs = list_history_runs(session, current_user)
    logger.info("获取历史记录列表：用户ID=%s 数量=%s", current_user.id, len(runs))
    return success_response(data=jsonable_encoder(runs))


@router.get("/runs/{run_ref}")
async def get_history_run(run_ref: str, session: SessionDep, current_user: User = Depends(get_current_user)):
    detail = get_history_run_detail(session, current_user, run_ref)
    if detail is None:
        logger.warning("获取历史记录详情失败：用户ID=%s 记录=%s", current_user.id, run_ref)
        return not_found_response(message="历史记录不存在")

    logger.info("获取历史记录详情：用户ID=%s 记录=%s 题目数=%s", current_user.id, run_ref, len(detail.questions))
    return success_response(data=jsonable_encoder(detail))
