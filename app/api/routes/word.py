from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_current_user
from app.db.database import SessionDep
from app.models.user import User
from app.api.api_responses import success_response, not_found_response, forbidden_response
from typing import Union
from app.db.word import search_word_top_10, batch_recognize_
from fastapi.encoders import jsonable_encoder
from app.models.word import BatchRecognizeRequest

router = APIRouter(prefix="/api/word", tags=["word"])

@router.get("/search")
async def search(session: SessionDep, q: Union[str, None] = Query(default=None), user_in: User = Depends(get_current_user)):
    return success_response(data=jsonable_encoder(search_word_top_10(session, q)))

@router.post("/batch_recognize")
async def batch_recognize(session: SessionDep, words: BatchRecognizeRequest, user_in: User = Depends(get_current_user)):
    recognized = batch_recognize_(session, words.words)
    res = {
        "recognizedCount": len(recognized),
        "unrecognizedCount": len(words.words) - len(recognized),
        "recognizedWords": [jsonable_encoder(w) for w in recognized],
        "unrecognizedWords": [word for word in words.words if word not in [w.text for w in recognized]],
    }
    return success_response(data=jsonable_encoder(res))