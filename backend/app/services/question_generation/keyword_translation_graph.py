from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.utils.LLM import MAX_RETRY_COUNT, generate_text, validate_question
from app.utils.logger import get_logger

from .common import build_initial_state, normalize_errors, preview_text, run_graph_generation, to_optional_bool

logger = get_logger(__name__)

QUESTION_TYPE = "keyword_translation"
CHINESE_PUNCTUATION_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》…,.!?;:\s]")


class KeywordTranslationGraphState(TypedDict, total=False):
    run_id: str
    user_id: int
    target_word: str
    chinese_sentence: str
    reference_answer: str
    review_status: str
    review_errors: list[str]
    retry_count: int
    max_retries: int
    final_content: dict[str, Any]
    sentence_agent_error: str
    reference_agent_error: str


ReviewStatus = Literal["pass", "fail_sentence", "fail_reference", "fail_both", "max_retries"]


def _count_sentence_chars(text: str) -> int:
    normalized = CHINESE_PUNCTUATION_RE.sub("", text)
    return len(normalized)


def _build_sentence_prompt(target_word: str) -> str:
    return f"""
你是“关键词翻译中文句生成 Agent”。请只输出 JSON。

任务：
围绕目标单词 "{target_word}" 生成一个自然、现代的中文句子，供用户翻译成英文。

要求：
1. 中文句子长度控制在 10-20 个字。
2. 语义必须清晰指向目标单词的核心含义。
3. 句子要自然、生活化，不要生硬解释词义。
4. 不要包含英文，不要出现 target_word 原词。

输出格式（仅 JSON）：
{{
  "chinese_sentence": "..."
}}
"""


def _build_reference_prompt(target_word: str, chinese_sentence: str) -> str:
    return f"""
你是“关键词翻译参考答案 Agent”。请只输出 JSON。

任务：
根据目标单词与中文原句，生成一个标准英文翻译。

目标单词：
{target_word}

中文原句：
{chinese_sentence}

要求：
1. reference_answer 必须使用目标单词 "{target_word}" 或其合法语法变体。
2. 译文语法自然、语义准确，不要多余解释。
3. 尽量使用简单常见的英语表达。

输出格式（仅 JSON）：
{{
  "reference_answer": "..."
}}
"""


def _build_review_prompt(candidate_content: dict[str, Any]) -> str:
    return f"""
你是审核 Agent。请只输出 JSON。

请对以下关键词翻译题做“语义层面”的细审：
{candidate_content}

注意：
- 中文句长度、是否含英文、reference_answer 是否包含目标词等硬规则已由本地程序校验。
- 你只关注语义质量与出题自然度。

审核要点：
1. chinese_sentence 是否自然，且语义清晰指向 target_word。
2. reference_answer 是否准确翻译了中文句子，并且目标词用法自然。

输出格式（仅 JSON）：
{{
  "is_valid": true,
  "sentence_ok": true,
  "reference_ok": true,
  "errors": ["..."]
}}
"""


def _classify_review_failure(
    errors: list[str],
    sentence_ok: bool | None,
    reference_ok: bool | None,
) -> ReviewStatus:
    if sentence_ok is False and reference_ok is True:
        return "fail_sentence"
    if sentence_ok is True and reference_ok is False:
        return "fail_reference"
    if sentence_ok is False and reference_ok is False:
        return "fail_both"

    sentence_keywords = ("sentence", "句子", "中文", "chinese_sentence")
    reference_keywords = ("reference", "reference_answer", "target_word", "译文", "目标词")

    sentence_hit = any(any(keyword in err for keyword in sentence_keywords) for err in errors)
    reference_hit = any(any(keyword in err for keyword in reference_keywords) for err in errors)

    if sentence_hit and not reference_hit:
        return "fail_sentence"
    if reference_hit and not sentence_hit:
        return "fail_reference"
    return "fail_both"


async def _sentence_agent(state: KeywordTranslationGraphState) -> KeywordTranslationGraphState:
    target_word = state["target_word"]
    logger.debug(
        "开始生成关键词翻译中文句：用户ID=%s 目标词=%s 重试=%s/%s",
        state["user_id"],
        target_word,
        state.get("retry_count", 0),
        state.get("max_retries", MAX_RETRY_COUNT),
    )
    try:
        result = await generate_text(_build_sentence_prompt(target_word))
        chinese_sentence = str(result.get("chinese_sentence", "")).strip()
    except Exception as e:
        logger.warning("生成关键词翻译中文句失败：用户ID=%s 错误=%s", state["user_id"], str(e))
        return {
            "chinese_sentence": "",
            "sentence_agent_error": f"sentence_agent失败: {e}",
        }

    logger.info("关键词翻译中文句生成完成：用户ID=%s 长度=%s", state["user_id"], len(chinese_sentence))
    logger.debug("关键词翻译中文句预览：%s", preview_text(chinese_sentence))
    return {
        "chinese_sentence": chinese_sentence,
        "sentence_agent_error": "",
    }


async def _reference_agent(state: KeywordTranslationGraphState) -> KeywordTranslationGraphState:
    target_word = state["target_word"]
    chinese_sentence = str(state.get("chinese_sentence", "")).strip()
    if not chinese_sentence:
        return {
            "reference_answer": "",
            "reference_agent_error": "reference_agent失败: chinese_sentence 为空",
        }

    logger.debug(
        "开始生成关键词翻译参考答案：用户ID=%s 目标词=%s 中文句长度=%s",
        state["user_id"],
        target_word,
        len(chinese_sentence),
    )
    try:
        result = await generate_text(_build_reference_prompt(target_word, chinese_sentence))
        reference_answer = str(result.get("reference_answer", "")).strip()
    except Exception as e:
        logger.warning("生成关键词翻译参考答案失败：用户ID=%s 错误=%s", state["user_id"], str(e))
        return {
            "reference_answer": "",
            "reference_agent_error": f"reference_agent失败: {e}",
        }

    logger.info("关键词翻译参考答案生成完成：用户ID=%s 长度=%s", state["user_id"], len(reference_answer))
    logger.debug("关键词翻译参考答案预览：%s", preview_text(reference_answer))
    return {
        "reference_answer": reference_answer,
        "reference_agent_error": "",
    }


async def _review_agent(state: KeywordTranslationGraphState) -> KeywordTranslationGraphState:
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", MAX_RETRY_COUNT))
    logger.debug(
        "开始审核关键词翻译题目：用户ID=%s 重试=%s/%s",
        state["user_id"],
        retry_count,
        max_retries,
    )

    candidate_content = {
        "target_word": state["target_word"],
        "chinese_sentence": state.get("chinese_sentence", ""),
        "reference_answer": state.get("reference_answer", ""),
    }

    sentence_local_errors: list[str] = []
    reference_local_errors: list[str] = []
    sentence_agent_error = str(state.get("sentence_agent_error", "")).strip()
    reference_agent_error = str(state.get("reference_agent_error", "")).strip()
    if sentence_agent_error:
        sentence_local_errors.append(sentence_agent_error)
    if reference_agent_error:
        reference_local_errors.append(reference_agent_error)

    chinese_sentence = str(state.get("chinese_sentence", "")).strip()
    if not chinese_sentence:
        sentence_local_errors.append("chinese_sentence 为空")
    else:
        sentence_length = _count_sentence_chars(chinese_sentence)
        if sentence_length < 10 or sentence_length > 20:
            sentence_local_errors.append(f"chinese_sentence 长度应为 10-20 字，当前={sentence_length}")
        if re.search(r"[A-Za-z]", chinese_sentence):
            sentence_local_errors.append("chinese_sentence 不应包含英文")

    deterministic_valid, deterministic_errors = validate_question(QUESTION_TYPE, candidate_content)
    for err in deterministic_errors:
        if err not in reference_local_errors:
            reference_local_errors.append(err)

    local_errors: list[str] = []
    for err in [*sentence_local_errors, *reference_local_errors]:
        if err not in local_errors:
            local_errors.append(err)

    local_pass = len(local_errors) == 0 and deterministic_valid
    llm_valid = False
    sentence_ok: bool | None = None
    reference_ok: bool | None = None
    llm_errors: list[str] = []
    if local_pass:
        try:
            review_result = await generate_text(_build_review_prompt(candidate_content))
            llm_valid = to_optional_bool(review_result.get("is_valid")) is True
            sentence_ok = to_optional_bool(review_result.get("sentence_ok"))
            reference_ok = to_optional_bool(review_result.get("reference_ok"))
            llm_errors = normalize_errors(review_result.get("errors"))
        except Exception as e:
            llm_errors = [f"review_agent失败: {e}"]
            logger.warning("关键词翻译语义审核失败：用户ID=%s 错误=%s", state["user_id"], str(e))
    else:
        logger.debug("关键词翻译本地规则未通过，跳过语义审核：用户ID=%s", state["user_id"])

    logger.debug(
        "关键词翻译审核明细：用户ID=%s 本地通过=%s 规则通过=%s 语义通过=%s sentence_ok=%s reference_ok=%s 本地错误=%s 语义错误=%s",
        state["user_id"],
        local_pass,
        deterministic_valid,
        llm_valid,
        sentence_ok,
        reference_ok,
        local_errors,
        llm_errors,
    )

    merged_errors = [*local_errors]
    for err in llm_errors:
        if err not in merged_errors:
            merged_errors.append(err)

    if sentence_ok is None and sentence_local_errors:
        sentence_ok = False
    if reference_ok is None and reference_local_errors:
        reference_ok = False

    is_valid = local_pass and llm_valid and len(llm_errors) == 0
    if is_valid:
        logger.info("关键词翻译题目审核通过：用户ID=%s 重试次数=%s", state["user_id"], retry_count)
        return {
            "review_status": "pass",
            "review_errors": [],
        }

    next_retry_count = retry_count + 1
    if next_retry_count >= max_retries:
        logger.warning(
            "关键词翻译题目审核失败达到上限：用户ID=%s 重试=%s 错误=%s",
            state["user_id"],
            next_retry_count,
            merged_errors,
        )
        return {
            "review_status": "max_retries",
            "review_errors": merged_errors,
            "retry_count": next_retry_count,
        }

    review_status = _classify_review_failure(merged_errors, sentence_ok, reference_ok)
    logger.warning(
        "关键词翻译题目审核未通过：用户ID=%s 状态=%s 重试=%s/%s 错误=%s",
        state["user_id"],
        review_status,
        next_retry_count,
        max_retries,
        merged_errors,
    )
    return {
        "review_status": review_status,
        "review_errors": merged_errors,
        "retry_count": next_retry_count,
    }


async def _formatter_agent(state: KeywordTranslationGraphState) -> KeywordTranslationGraphState:
    logger.debug("开始格式化关键词翻译题目：用户ID=%s", state["user_id"])
    final_content = {
        "target_word": state["target_word"],
        "chinese_sentence": state.get("chinese_sentence", ""),
        "reference_answer": state.get("reference_answer", ""),
    }
    logger.info("格式化关键词翻译题目完成：用户ID=%s", state["user_id"])
    return {"final_content": final_content}


def _mark_failed(_: KeywordTranslationGraphState) -> KeywordTranslationGraphState:
    logger.debug("关键词翻译题目图节点触发：节点=mark_failed")
    return {}


def _route_after_review(state: KeywordTranslationGraphState) -> ReviewStatus:
    status = state.get("review_status", "max_retries")
    logger.debug("关键词翻译图路由决策：用户ID=%s 状态=%s", state.get("user_id", "-"), status)
    if status in {"pass", "fail_sentence", "fail_reference", "fail_both", "max_retries"}:
        return status
    return "max_retries"


def _build_keyword_translation_graph():
    logger.debug("开始构建题目图：type=%s", QUESTION_TYPE)
    graph = StateGraph(KeywordTranslationGraphState)
    graph.add_node("sentence_agent", _sentence_agent)
    graph.add_node("reference_agent", _reference_agent)
    graph.add_node("review_agent", _review_agent)
    graph.add_node("formatter_agent", _formatter_agent)
    graph.add_node("mark_failed", _mark_failed)

    graph.add_edge(START, "sentence_agent")
    graph.add_edge("sentence_agent", "reference_agent")
    graph.add_edge("reference_agent", "review_agent")
    graph.add_conditional_edges(
        "review_agent",
        _route_after_review,
        {
            "pass": "formatter_agent",
            "fail_sentence": "sentence_agent",
            "fail_reference": "reference_agent",
            "fail_both": "sentence_agent",
            "max_retries": "mark_failed",
        },
    )
    graph.add_edge("formatter_agent", END)
    graph.add_edge("mark_failed", END)
    logger.debug("题目图构建完成：type=%s nodes=%s", QUESTION_TYPE, 5)
    return graph.compile()


keyword_translation_graph = _build_keyword_translation_graph()


async def generate_keyword_translation_content(
    user_id: int,
    target_words: list[str],
    max_retries: int = MAX_RETRY_COUNT,
) -> dict[str, Any] | None:
    target_word = target_words[0] if target_words else ""
    if not target_word:
        logger.warning("关键词翻译题目生成失败：用户ID=%s 原因=目标词为空", user_id)
        return None

    initial_state: KeywordTranslationGraphState = build_initial_state(
        user_id=user_id,
        max_retries=max_retries,
        extra_state={"target_word": target_word},
    )
    return await run_graph_generation(
        graph=keyword_translation_graph,
        logger=logger,
        question_type=QUESTION_TYPE,
        user_id=user_id,
        initial_state=initial_state,
    )
