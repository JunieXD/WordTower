from __future__ import annotations

import random
import re
from collections import Counter
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.utils.LLM import MAX_RETRY_COUNT, generate_text, validate_question
from app.utils.logger import get_logger

from .common import build_initial_state, normalize_errors, preview_text, run_graph_generation, to_optional_bool

logger = get_logger(__name__)

QUESTION_TYPE = "cloze_test"
BLANK_TOKEN_PATTERN = re.compile(r"\[\[BLANK_(\d+):([^\]]+)\]\]")


class ClozeTestGraphState(TypedDict, total=False):
    run_id: str
    user_id: int
    target_words: list[str]
    draft_text: str
    resolved_draft_text: str
    chinese_translation: str
    cloze_text: str
    shuffled_options: list[str]
    correct_sequence: list[str]
    review_status: str
    review_errors: list[str]
    retry_count: int
    max_retries: int
    final_content: dict[str, Any] | None
    draft_agent_error: str
    translation_agent_error: str
    formatter_error: str


ReviewStatus = Literal["pass", "fail_draft", "max_retries"]


def _normalize_word(word: str) -> str:
    return " ".join(word.strip().lower().split())


def _resolve_draft_text(draft_text: str) -> str:
    return BLANK_TOKEN_PATTERN.sub(lambda match: match.group(2).strip(), draft_text)


def _shuffle_options(words: list[str]) -> list[str]:
    shuffled = list(words)
    random.shuffle(shuffled)
    return shuffled


def _build_draft_prompt(target_words: list[str]) -> str:
    word_list = ", ".join(target_words)
    marker_examples = "\n".join(
        f'- 第 {index} 个空写成 `[[BLANK_{index}:{word}]]`'
        for index, word in enumerate(target_words, start=1)
    )
    return f"""
你是“完形填空草稿 Agent”。请只输出 JSON。

任务：
使用以下所有目标单词写一段 150-200 词的英文短文，并把目标单词替换成带标记的空格 token：
{word_list}

硬性要求：
1. 每个目标单词必须使用一次且仅一次，不能遗漏，也不能重复。
2. token 格式必须严格为 `[[BLANK_n:word]]`。
3. token 编号必须按文章出现顺序从 1 连续递增。
4. token 中的 word 必须保留目标单词原样，不要变形。
5. 文章必须连贯自然，除目标词外尽量使用 CEFR A2 水平词汇。
6. 每个空格周围都要有足够线索，让该空在目标词集合中具备唯一答案。

格式示例：
{marker_examples}

输出格式（仅 JSON）：
{{
  "draft_text": "..."
}}
"""


def _build_translation_prompt(resolved_draft_text: str) -> str:
    return f"""
你是“完形填空翻译 Agent”。请只输出 JSON。

任务：
把下面这段完整英文短文翻译成自然流畅的中文。

英文短文：
{resolved_draft_text}

要求：
1. 译文必须完整，不要遗漏信息。
2. 不要保留任何占位符、括号或英文 token。
3. 中文表达自然、现代，不要逐词硬译。

输出格式（仅 JSON）：
{{
  "chinese_translation": "..."
}}
"""


def _build_review_prompt(
    candidate_content: dict[str, Any],
    resolved_draft_text: str,
    target_words: list[str],
) -> str:
    return f"""
你是审核 Agent。请只输出 JSON。

请对以下完形填空题做“语义层面”的细审：

target_words:
{target_words}

resolved_draft_text:
{resolved_draft_text}

candidate_content:
{candidate_content}

注意：
- 字段完整性、占位符数量、编号顺序、选项集合一致性等硬规则已由本地程序校验。
- 你只需要关注语义质量和出题质量。

审核要点：
1. 英文短文是否连贯、自然。
2. 每个空格是否有足够的上下文线索，且在给定目标词集合中只有一个合理答案。
3. 中文翻译是否忠实反映英文原文。

输出格式（仅 JSON）：
{{
  "is_valid": true,
  "draft_ok": true,
  "translation_ok": true,
  "errors": ["..."]
}}
"""


def _build_formatted_content(
    draft_text: str,
    target_words: list[str],
) -> tuple[dict[str, Any] | None, str, list[str]]:
    errors: list[str] = []
    stripped = draft_text.strip()
    if not stripped:
        return None, "", ["draft_text 为空"]

    matches = list(BLANK_TOKEN_PATTERN.finditer(stripped))
    resolved_draft_text = _resolve_draft_text(stripped)
    if not matches:
        return None, resolved_draft_text, ["draft_text 中未找到任何 BLANK 标记"]

    numbers = [int(match.group(1)) for match in matches]
    if numbers != list(range(1, len(matches) + 1)):
        errors.append("BLANK 编号必须按出现顺序从 1 连续递增")

    correct_sequence = [match.group(2).strip() for match in matches]
    if any(not word for word in correct_sequence):
        errors.append("存在空的 BLANK 单词内容")

    if len(matches) != len(target_words):
        errors.append(
            f"BLANK 数量与目标词数量不一致，期望={len(target_words)} 实际={len(matches)}"
        )

    expected_counter = Counter(_normalize_word(word) for word in target_words)
    actual_counter = Counter(_normalize_word(word) for word in correct_sequence)
    if actual_counter != expected_counter:
        errors.append(
            f"BLANK 中使用的单词集合与 target_words 不一致，期望={target_words} 实际={correct_sequence}"
        )

    cloze_text = BLANK_TOKEN_PATTERN.sub(
        lambda match: f"____[{match.group(1)}]____",
        stripped,
    )
    if "[[BLANK_" in cloze_text:
        errors.append("cloze_text 格式化后仍残留 BLANK 标记")

    if errors:
        return None, resolved_draft_text, errors

    return (
        {
            "cloze_text": cloze_text,
            "shuffled_options": _shuffle_options(correct_sequence),
            "correct_sequence": correct_sequence,
            "chinese_translation": "",
        },
        resolved_draft_text,
        [],
    )


async def _draft_agent(state: ClozeTestGraphState) -> ClozeTestGraphState:
    target_words = list(state.get("target_words", []))
    logger.debug(
        "开始生成完形填空草稿：用户ID=%s 目标词=%s 重试=%s/%s",
        state["user_id"],
        target_words,
        state.get("retry_count", 0),
        state.get("max_retries", MAX_RETRY_COUNT),
    )
    try:
        result = await generate_text(_build_draft_prompt(target_words))
        draft_text = str(result.get("draft_text", "")).strip()
    except Exception as e:
        logger.warning("生成完形填空草稿失败：用户ID=%s 错误=%s", state["user_id"], str(e))
        return {
            "draft_text": "",
            "draft_agent_error": f"draft_agent失败: {e}",
        }

    logger.info("完形填空草稿生成完成：用户ID=%s 长度=%s", state["user_id"], len(draft_text))
    logger.debug("完形填空草稿预览：%s", preview_text(draft_text))
    return {
        "draft_text": draft_text,
        "draft_agent_error": "",
    }


async def _translation_agent(state: ClozeTestGraphState) -> ClozeTestGraphState:
    draft_text = str(state.get("draft_text", "")).strip()
    if not draft_text:
        return {
            "chinese_translation": "",
            "translation_agent_error": "translation_agent失败: draft_text 为空",
        }

    resolved_draft_text = _resolve_draft_text(draft_text)
    logger.debug(
        "开始生成完形填空译文：用户ID=%s 英文长度=%s",
        state["user_id"],
        len(resolved_draft_text),
    )
    try:
        result = await generate_text(_build_translation_prompt(resolved_draft_text))
        chinese_translation = str(result.get("chinese_translation", "")).strip()
    except Exception as e:
        logger.warning("生成完形填空译文失败：用户ID=%s 错误=%s", state["user_id"], str(e))
        return {
            "chinese_translation": "",
            "resolved_draft_text": resolved_draft_text,
            "translation_agent_error": f"translation_agent失败: {e}",
        }

    logger.info("完形填空译文生成完成：用户ID=%s 长度=%s", state["user_id"], len(chinese_translation))
    logger.debug("完形填空译文预览：%s", preview_text(chinese_translation))
    return {
        "chinese_translation": chinese_translation,
        "resolved_draft_text": resolved_draft_text,
        "translation_agent_error": "",
    }


async def _formatter_agent(state: ClozeTestGraphState) -> ClozeTestGraphState:
    logger.debug("开始格式化完形填空题目：用户ID=%s", state["user_id"])
    formatted_content, resolved_draft_text, errors = _build_formatted_content(
        str(state.get("draft_text", "")),
        list(state.get("target_words", [])),
    )

    if errors or formatted_content is None:
        logger.warning("格式化完形填空题目失败：用户ID=%s 错误=%s", state["user_id"], errors)
        return {
            "cloze_text": "",
            "correct_sequence": [],
            "shuffled_options": [],
            "resolved_draft_text": resolved_draft_text,
            "formatter_error": "; ".join(errors),
            "final_content": None,
        }

    formatted_content["chinese_translation"] = str(state.get("chinese_translation", "")).strip()
    logger.info("格式化完形填空题目完成：用户ID=%s 空格数=%s", state["user_id"], len(formatted_content["correct_sequence"]))
    return {
        "cloze_text": str(formatted_content["cloze_text"]),
        "correct_sequence": list(formatted_content["correct_sequence"]),
        "shuffled_options": list(formatted_content["shuffled_options"]),
        "resolved_draft_text": resolved_draft_text,
        "formatter_error": "",
        "final_content": formatted_content,
    }


async def _review_agent(state: ClozeTestGraphState) -> ClozeTestGraphState:
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", MAX_RETRY_COUNT))
    logger.debug(
        "开始审核完形填空题目：用户ID=%s 重试=%s/%s",
        state["user_id"],
        retry_count,
        max_retries,
    )

    candidate_content = {
        "cloze_text": state.get("cloze_text", ""),
        "shuffled_options": state.get("shuffled_options", []),
        "correct_sequence": state.get("correct_sequence", []),
        "chinese_translation": state.get("chinese_translation", ""),
    }

    local_errors: list[str] = []
    for err in [
        str(state.get("draft_agent_error", "")).strip(),
        str(state.get("translation_agent_error", "")).strip(),
        str(state.get("formatter_error", "")).strip(),
    ]:
        if err and err not in local_errors:
            local_errors.append(err)

    chinese_translation = str(state.get("chinese_translation", "")).strip()
    if not chinese_translation:
        local_errors.append("chinese_translation 为空")
    if "[[BLANK_" in chinese_translation or "____[" in chinese_translation:
        local_errors.append("chinese_translation 不应包含占位符或 BLANK 标记")

    deterministic_valid, deterministic_errors = validate_question(QUESTION_TYPE, candidate_content)
    for err in deterministic_errors:
        if err not in local_errors:
            local_errors.append(err)

    local_pass = len(local_errors) == 0 and deterministic_valid
    llm_valid = False
    draft_ok: bool | None = None
    translation_ok: bool | None = None
    llm_errors: list[str] = []
    if local_pass:
        try:
            review_result = await generate_text(
                _build_review_prompt(
                    candidate_content,
                    str(state.get("resolved_draft_text", "")),
                    list(state.get("target_words", [])),
                )
            )
            llm_valid = to_optional_bool(review_result.get("is_valid")) is True
            draft_ok = to_optional_bool(review_result.get("draft_ok"))
            translation_ok = to_optional_bool(review_result.get("translation_ok"))
            llm_errors = normalize_errors(review_result.get("errors"))
        except Exception as e:
            llm_errors = [f"review_agent失败: {e}"]
            logger.warning("完形填空语义审核失败：用户ID=%s 错误=%s", state["user_id"], str(e))
    else:
        logger.debug("完形填空本地规则未通过，跳过语义审核：用户ID=%s", state["user_id"])

    logger.debug(
        "完形填空审核明细：用户ID=%s 本地通过=%s 规则通过=%s 语义通过=%s draft_ok=%s translation_ok=%s 本地错误=%s 语义错误=%s",
        state["user_id"],
        local_pass,
        deterministic_valid,
        llm_valid,
        draft_ok,
        translation_ok,
        local_errors,
        llm_errors,
    )

    merged_errors = [*local_errors]
    for err in llm_errors:
        if err not in merged_errors:
            merged_errors.append(err)

    is_valid = local_pass and llm_valid and len(llm_errors) == 0
    if is_valid:
        logger.info("完形填空题目审核通过：用户ID=%s 重试次数=%s", state["user_id"], retry_count)
        return {
            "review_status": "pass",
            "review_errors": [],
        }

    next_retry_count = retry_count + 1
    if next_retry_count >= max_retries:
        logger.warning(
            "完形填空题目审核失败达到上限：用户ID=%s 重试=%s 错误=%s",
            state["user_id"],
            next_retry_count,
            merged_errors,
        )
        return {
            "review_status": "max_retries",
            "review_errors": merged_errors,
            "retry_count": next_retry_count,
            "final_content": None,
        }

    logger.warning(
        "完形填空题目审核未通过：用户ID=%s 重试=%s/%s 错误=%s",
        state["user_id"],
        next_retry_count,
        max_retries,
        merged_errors,
    )
    return {
        "review_status": "fail_draft",
        "review_errors": merged_errors,
        "retry_count": next_retry_count,
        "final_content": None,
    }


def _mark_failed(_: ClozeTestGraphState) -> ClozeTestGraphState:
    logger.debug("完形填空题目图节点触发：节点=mark_failed")
    return {}


def _route_after_review(state: ClozeTestGraphState) -> ReviewStatus:
    status = state.get("review_status", "max_retries")
    logger.debug("完形填空图路由决策：用户ID=%s 状态=%s", state.get("user_id", "-"), status)
    if status in {"pass", "fail_draft", "max_retries"}:
        return status
    return "max_retries"


def _build_cloze_test_graph():
    logger.debug("开始构建题目图：type=%s", QUESTION_TYPE)
    graph = StateGraph(ClozeTestGraphState)
    graph.add_node("draft_agent", _draft_agent)
    graph.add_node("translation_agent", _translation_agent)
    graph.add_node("formatter_agent", _formatter_agent)
    graph.add_node("review_agent", _review_agent)
    graph.add_node("mark_failed", _mark_failed)

    graph.add_edge(START, "draft_agent")
    graph.add_edge("draft_agent", "translation_agent")
    graph.add_edge("translation_agent", "formatter_agent")
    graph.add_edge("formatter_agent", "review_agent")
    graph.add_conditional_edges(
        "review_agent",
        _route_after_review,
        {
            "pass": END,
            "fail_draft": "draft_agent",
            "max_retries": "mark_failed",
        },
    )
    graph.add_edge("mark_failed", END)
    logger.debug("题目图构建完成：type=%s nodes=%s", QUESTION_TYPE, 5)
    return graph.compile()


cloze_test_graph = _build_cloze_test_graph()


async def generate_cloze_test_content(
    user_id: int,
    target_words: list[str],
    max_retries: int = MAX_RETRY_COUNT,
) -> dict[str, Any] | None:
    if not target_words:
        logger.warning("完形填空题目生成失败：用户ID=%s 原因=目标词为空", user_id)
        return None

    initial_state: ClozeTestGraphState = build_initial_state(
        user_id=user_id,
        max_retries=max_retries,
        extra_state={"target_words": list(target_words)},
    )
    return await run_graph_generation(
        graph=cloze_test_graph,
        logger=logger,
        question_type=QUESTION_TYPE,
        user_id=user_id,
        initial_state=initial_state,
    )
