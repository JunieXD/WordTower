from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.utils.LLM import MAX_RETRY_COUNT
from app.utils.logger import get_logger

from .cloze_test_graph import generate_cloze_test_content
from .context_guess_graph import generate_context_guess_content
from .keyword_translation_graph import generate_keyword_translation_content

logger = get_logger(__name__)

QuestionGenerator = Callable[[int, list[str], int], Awaitable[dict[str, Any] | None]]


async def _generate_context_guess(
    user_id: int,
    word_texts: list[str],
    max_retries: int,
) -> dict[str, Any] | None:
    if not word_texts:
        return None
    return await generate_context_guess_content(
        user_id=user_id,
        target_word=word_texts[0],
        max_retries=max_retries,
    )


GENERATOR_REGISTRY: dict[str, QuestionGenerator] = {
    "context_guess": _generate_context_guess,
    "cloze_test": generate_cloze_test_content,
    "keyword_translation": generate_keyword_translation_content,
}


async def generate_question_content(
    user_id: int,
    q_type: str,
    word_texts: list[str],
    max_retries: int = MAX_RETRY_COUNT,
) -> dict[str, Any] | None:
    """统一题目生成调度入口。"""
    generator = GENERATOR_REGISTRY.get(q_type)
    if generator is None:
        logger.error("统一出题调度失败：未注册的题型=%s 用户ID=%s", q_type, user_id)
        return None

    logger.debug(
        "统一出题调度开始：用户ID=%s 题型=%s 目标词=%s 最大重试=%s",
        user_id,
        q_type,
        word_texts,
        max_retries,
    )
    return await generator(user_id, word_texts, max_retries)
