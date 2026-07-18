from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_current_user
from app.db.database import SessionDep
from app.models.user import User
from app.api.api_responses import success_response
from app.db.word import batch_recognize_, search_word_top_10
from fastapi.encoders import jsonable_encoder
from app.models.word import BatchRecognizeRequest
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/word", tags=["word"])
logger = get_logger(__name__)


@router.get("/search")
def search(
    session: SessionDep,
    q: str | None = Query(default=None, max_length=64),
    user_in: User = Depends(get_current_user),
):
    query = (q or "").strip()
    logger.info("单词搜索：用户ID=%s 查询=%s", user_in.id, query)
    if not query:
        return success_response(data=[])
    return success_response(data=jsonable_encoder(search_word_top_10(session, query)))


@router.post("/batch_recognize")
async def batch_recognize(session: SessionDep, words: BatchRecognizeRequest, user_in: User = Depends(get_current_user)):
    recognized = batch_recognize_(session, words.words)
    res = {
        "recognizedCount": len(recognized),
        "unrecognizedCount": len(words.words) - len(recognized),
        "recognizedWords": [jsonable_encoder(w) for w in recognized],
        "unrecognizedWords": [word for word in words.words if word not in [w.text for w in recognized]],
    }
    logger.info(
        "批量识别单词：用户ID=%s 总数=%s 已识别=%s 未识别=%s",
        user_in.id,
        len(words.words),
        len(recognized),
        len(words.words) - len(recognized),
    )
    return success_response(data=jsonable_encoder(res))
