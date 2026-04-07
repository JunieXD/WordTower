from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder

from app.models.question import Question
from app.utils.word_forms import extract_target_surface_forms


def ensure_story_target_forms_in_payload(question_payload: dict[str, Any]) -> dict[str, Any]:
    """为旧的 context_guess 题目响应补齐 story_target_forms。"""
    if question_payload.get("type") != "context_guess":
        return question_payload

    content = question_payload.get("content")
    if not isinstance(content, dict):
        return question_payload

    existing_forms = content.get("story_target_forms")
    if isinstance(existing_forms, list) and len(existing_forms) > 0:
        return question_payload

    target_word = str(content.get("target_word") or "").strip()
    story = str(content.get("story") or "").strip()
    if not target_word or not story:
        return question_payload

    enriched_payload = dict(question_payload)
    enriched_content = dict(content)
    enriched_content["story_target_forms"] = extract_target_surface_forms(story, target_word)
    enriched_payload["content"] = enriched_content
    return enriched_payload


def serialize_question_for_client(question: Question) -> dict[str, Any]:
    """序列化题目给前端，并兼容补齐旧题缺失字段。"""
    return ensure_story_target_forms_in_payload(jsonable_encoder(question))
