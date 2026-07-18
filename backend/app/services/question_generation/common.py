from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.utils.LLM import MAX_RETRY_COUNT


def preview_text(text: str, limit: int = 120) -> str:
    """截断长文本用于 debug 日志，避免终端刷屏。"""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def normalize_errors(value: Any) -> list[str]:
    """将错误信息统一规范为 list[str]，便于后续合并与日志输出。"""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def to_optional_bool(value: Any) -> bool | None:
    """将模型返回值尽量解析为布尔值，无法识别时返回 None。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def build_initial_state(
    user_id: int,
    max_retries: int = MAX_RETRY_COUNT,
    extra_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造题目图统一初始状态。"""
    state: dict[str, Any] = {
        "run_id": uuid4().hex[:12],
        "user_id": user_id,
        "retry_count": 0,
        "max_retries": max_retries,
    }
    if extra_state:
        state.update(extra_state)
    return state


async def run_graph_generation(
    *,
    graph: Any,
    logger: Any,
    question_type: str,
    user_id: int,
    initial_state: dict[str, Any],
    final_key: str = "final_content",
) -> dict[str, Any] | None:
    """执行统一题目图并读取 final_content。"""
    logger.info(
        "开始生成题目：用户ID=%s 题型=%s 最大重试=%s",
        user_id,
        question_type,
        initial_state.get("max_retries", MAX_RETRY_COUNT),
    )
    logger.debug("题目图初始状态：%s", initial_state)
    try:
        result = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.exception(
            "题目图执行异常：用户ID=%s 题型=%s 错误=%s",
            user_id,
            question_type,
            str(e),
        )
        return None

    logger.debug("题目图结束状态：result_keys=%s", list(result.keys()))
    final_content = result.get(final_key)

    if isinstance(final_content, dict):
        logger.info(
            "题目生成成功：用户ID=%s 题型=%s",
            user_id,
            question_type,
        )
        return final_content

    logger.warning(
        "题目生成失败：用户ID=%s 题型=%s 最终状态=%s 错误=%s",
        user_id,
        question_type,
        result.get("review_status", "unknown"),
        result.get("review_errors", []),
    )
    return None
