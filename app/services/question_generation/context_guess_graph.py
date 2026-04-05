from __future__ import annotations

import asyncio
import random
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.db.database import engine
from app.models.word import Word
from app.utils.LLM import MAX_RETRY_COUNT, generate_text, validate_question
from app.utils.logger import get_logger
from app.utils.word_forms import extract_target_surface_forms

from .common import (
    build_initial_state,
    normalize_errors as _normalize_errors,
    preview_text as _preview_text,
    run_graph_generation,
    to_optional_bool as _to_optional_bool,
)

logger = get_logger(__name__)

QUESTION_TYPE = "context_guess"


class ContextGuessGraphState(TypedDict, total=False):
    run_id: str
    user_id: int
    target_word: str
    story: str
    options: dict[str, str]
    correct_option: str
    explanation: str
    story_target_forms: list[str]
    review_status: str
    review_errors: list[str]
    retry_count: int
    max_retries: int
    final_content: dict[str, Any]
    story_agent_error: str
    options_agent_error: str
    correct_meaning: str
    distractors: list[str]
    correct_meaning_agent_error: str
    distractor_agent_error: str
    dictionary_meanings: list[str]
    dictionary_lookup_error: str


ReviewStatus = Literal["pass", "fail_story", "fail_options", "fail_both", "max_retries"]


def _is_option_explanatory_text(option_value: str) -> bool:
    """
    判断选项是否过于“解释句”而非“词典式释义”。

    目标是拦截类似“房子上的排气管状物”“用来……的东西”这类描述性表达。
    """
    text = option_value.strip()
    if not text:
        return True

    # 太长通常是描述句，不是义项短语
    if len(text) > 8:
        return True

    # 标点或句式痕迹
    if any(p in text for p in ("，", "。", "；", "：", ",", ".", ";", ":")):
        return True

    # 明显解释句触发词
    explanatory_markers = (
        "用来",
        "用于",
        "一种",
        "一个",
        "某种",
        "表示",
        "指的是",
        "的东西",
        "的物体",
        "状物",
        "样子",
    )
    if any(marker in text for marker in explanatory_markers):
        return True

    return False


def _validate_option_directness(options: dict[str, str]) -> list[str]:
    """校验选项是否足够直白，返回违规错误列表。"""
    errors: list[str] = []
    for key in ("A", "B", "C", "D"):
        option_value = str(options.get(key, "")).strip()
        if not option_value:
            continue
        if _is_option_explanatory_text(option_value):
            errors.append(f"选项 {key} 过于描述化，需改为直白词典义项：{option_value}")
    return errors


def _clean_meaning_fragment(fragment: str) -> str:
    """清洗词典义项片段，尽量转为可直接用于选项的短义项。"""
    text = fragment.strip()
    if not text:
        return ""

    # 去掉词性前缀：n. / vt. / adj. 等
    text = re.sub(r"^(n|v|vi|vt|adj|adv|prep|pron|num|int|conj|aux|abbr|pl)\.\s*", "", text, flags=re.IGNORECASE)
    # 去掉括号注释
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = text.strip(" ;；,，:：。.、/\\")
    return text.strip()


def _parse_ecdict_meanings(meaning_text: str) -> list[str]:
    """将 ECDICT 导入的 meaning 字段解析为候选中文义项。"""
    if not meaning_text:
        return []

    chunks = re.split(r"[;\n/；，,。]+", meaning_text)
    results: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        cleaned = _clean_meaning_fragment(chunk)
        if not cleaned:
            continue

        # 仅保留含中文字符的义项，避免英文噪声
        if not re.search(r"[\u4e00-\u9fff]", cleaned):
            continue

        # 优先短义项，过长项通常是解释句
        if len(cleaned) > 12:
            continue

        if cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)
    return results[:12]


def _lookup_dictionary_meanings_sync(target_word: str) -> list[str]:
    """同步查询数据库词典并提取候选义项。"""
    with DBSession(engine) as session:
        statement = (
            select(Word)
            .where(Word.text.ilike(target_word))
            .order_by(Word.id.asc())
        )
        word = session.exec(statement).first()
        if not word:
            return []

        meaning_text = word.meaning or ""
        return _parse_ecdict_meanings(meaning_text)


def _format_dictionary_hint(dictionary_meanings: list[str]) -> str:
    """格式化词典候选义项，用于注入 prompt。"""
    if not dictionary_meanings:
        return "（未命中本地词典，请仅基于语境生成）"
    top_items = dictionary_meanings[:8]
    return "、".join(top_items)


def _build_story_prompt(target_word: str) -> str:
    """构造 Story Agent 的提示词，约束其仅返回包含 story 字段的 JSON。"""
    return f"""
你是出题 Agent。请只输出 JSON。

任务：
基于目标单词 "{target_word}" 生成一段 40-60 词英文短文。

要求：
1. 文本有简单故事性与逻辑连贯性。
2. 词汇难度尽量为 CEFR A2（目标词除外）。
3. 目标词（或其语法变体）应自然出现在文本中。

输出格式（仅 JSON）：
{{
  "story": "..."
}}
"""


def _build_correct_meaning_prompt(target_word: str, story: str, dictionary_meanings: list[str]) -> str:
    """构造 Correct Meaning Agent 提示词：仅生成正确释义与解析。"""
    dictionary_hint = _format_dictionary_hint(dictionary_meanings)
    return f"""
你是“正确义项生成 Agent”。请只输出 JSON。

任务：
根据目标单词与短文，只生成该题正确选项对应的中文释义，以及解析。

目标单词：
{target_word}

短文：
{story}

本地词典候选义项（优先参考）：
{dictionary_hint}

要求：
1. correct_meaning 必须是“词典义项风格”的直白释义，优先单词或固定短语。
2. correct_meaning 尽量控制在 1-8 个中文字符。
3. 严禁解释句（如“房子上的排气管状物”“用来……的东西”“一种……”）。
4. 若本地词典命中，优先从候选义项中选择最贴合语境的一项；若未命中再自行生成。
5. explanation 使用中文，解释为什么该义项符合语境。

输出格式（仅 JSON）：
{{
  "correct_meaning": "...",
  "explanation": "..."
}}
"""


def _build_distractor_prompt(target_word: str, story: str, dictionary_meanings: list[str]) -> str:
    """构造 Distractor Agent 提示词：只生成 3 个干扰项。"""
    dictionary_hint = _format_dictionary_hint(dictionary_meanings)
    return f"""
你是“干扰项生成 Agent”。请只输出 JSON。

任务：
根据目标单词与短文，为词义猜测题生成 3 个中文干扰项。

目标单词：
{target_word}

短文：
{story}

本地词典候选义项（优先参考）：
{dictionary_hint}

要求：
1. 生成 3 个互不相同的干扰项（仅中文释义）。
2. 风格必须是词典义项（短词/短语），尽量 1-8 个字符。
3. 严禁解释句（如“用来……的东西”“一种……”）。
4. 若本地词典命中，优先从候选义项中挑选“非核心义项”作为干扰项。
5. 应尽量覆盖目标词常见混淆义，而不是同义改写。

输出格式（仅 JSON）：
{{
  "distractors": ["...", "...", "..."]
}}
"""


def _build_review_prompt(candidate_content: dict[str, Any]) -> str:
    """构造 Review Agent 的提示词，仅做语义细审。"""
    return f"""
你是审核 Agent。请只输出 JSON。

请对以下题目做“语义层面”的细审：
{candidate_content}

注意：
- 格式、字段完整性、选项数量、选项直白性等“硬规则”已由本地程序校验，请你只关注语义质量。

语义审核要点：
1. story 是否为 target_word 提供了足够且合理的语境线索。
2. 正确选项是否与 story 语义最匹配，且具有唯一性。
3. 干扰项是否具有迷惑性但整体语义上应判错。
4. explanation 是否与语境和正确项一致。

输出格式（仅 JSON）：
{{
  "is_valid": true,
  "story_ok": true,
  "options_ok": true,
  "errors": ["..."]
}}
"""


def _extract_options(options_raw: Any) -> dict[str, str]:
    """从模型输出中安全提取 A/B/C/D 四个选项并做字符串清洗。"""
    result: dict[str, str] = {}
    if not isinstance(options_raw, dict):
        return result

    for key in ("A", "B", "C", "D"):
        value = options_raw.get(key)
        if value is not None:
            result[key] = str(value).strip()
    return result


def _normalize_distractors(value: Any) -> list[str]:
    """将干扰项结果规范为去重后的字符串列表。"""
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        candidates = [value]
    else:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _merge_options(correct_meaning: str, distractors: list[str]) -> tuple[dict[str, str], str, list[str]]:
    """将正确义与干扰项合并为 A/B/C/D 选项。"""
    errors: list[str] = []
    correct = correct_meaning.strip()
    if not correct:
        errors.append("缺少正确义项 correct_meaning")

    normalized_distractors = _normalize_distractors(distractors)
    normalized_distractors = [d for d in normalized_distractors if d != correct]
    if len(normalized_distractors) < 3:
        errors.append(f"干扰项不足 3 个，当前={len(normalized_distractors)}")

    if errors:
        return {}, "", errors

    slots = ["A", "B", "C", "D"]
    correct_slot = random.choice(slots)
    options: dict[str, str] = {correct_slot: correct}

    distractor_iter = iter(normalized_distractors[:3])
    for slot in slots:
        if slot == correct_slot:
            continue
        options[slot] = next(distractor_iter)

    if len(set(options.values())) != 4:
        errors.append("合并后选项存在重复义项")
        return {}, "", errors
    return options, correct_slot, []


def _classify_review_failure(
    errors: list[str],
    story_ok: bool | None,
    options_ok: bool | None,
) -> ReviewStatus:
    """根据审核结果判断失败归因，用于决定图中的回退节点。"""
    if story_ok is False and options_ok is True:
        return "fail_story"
    if story_ok is True and options_ok is False:
        return "fail_options"
    if story_ok is False and options_ok is False:
        return "fail_both"

    story_keywords = ("story", "目标单词", "target_word", "语境", "故事")
    option_keywords = (
        "options",
        "选项",
        "correct_option",
        "correct_meaning",
        "distractor",
        "释义",
        "explanation",
        "干扰项",
    )

    story_hit = any(any(keyword in err for keyword in story_keywords) for err in errors)
    option_hit = any(any(keyword in err for keyword in option_keywords) for err in errors)

    if story_hit and not option_hit:
        return "fail_story"
    if option_hit and not story_hit:
        return "fail_options"
    return "fail_both"


async def _story_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """生成题干故事节点：调用 LLM 产出 story，并写回图状态。"""
    target_word = state["target_word"]
    logger.debug(
        "开始生成故事：用户ID=%s 目标词=%s 重试=%s/%s",
        state["user_id"],
        target_word,
        state.get("retry_count", 0),
        state.get("max_retries", MAX_RETRY_COUNT),
    )
    try:
        result = await generate_text(_build_story_prompt(target_word))
        story = str(result.get("story", "")).strip()
    except Exception as e:
        logger.warning(
            "生成故事失败：用户ID=%s 错误=%s",
            state["user_id"],
            str(e),
        )
        return {
            "story": "",
            "story_agent_error": f"story_agent失败: {e}",
        }
    logger.debug(
        "故事预览：%s",
        _preview_text(story),
    )

    logger.info(
        "故事生成完成：用户ID=%s 长度=%s",
        state["user_id"],
        len(story),
    )
    return {
        "story": story,
        "story_agent_error": "",
    }


async def _dictionary_lookup_tool(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """词典工具节点：查询本地 ECDICT（PostgreSQL）并提取候选义项。"""
    target_word = state["target_word"]
    logger.debug(
        "开始查询词典：用户ID=%s 目标词=%s",
        state["user_id"],
        target_word,
    )
    try:
        meanings = await asyncio.to_thread(_lookup_dictionary_meanings_sync, target_word)
        logger.info(
            "词典查询完成：用户ID=%s 命中义项数=%s",
            state["user_id"],
            len(meanings),
        )
        logger.debug(
            "词典候选义项：%s",
            meanings,
        )
        return {
            "dictionary_meanings": meanings,
            "dictionary_lookup_error": "",
        }
    except Exception as e:
        logger.warning(
            "词典查询失败：用户ID=%s 错误=%s",
            state["user_id"],
            str(e),
        )
        return {
            "dictionary_meanings": [],
            "dictionary_lookup_error": f"dictionary_lookup_tool失败: {e}",
        }


def _options_fanout(_: ContextGuessGraphState) -> ContextGuessGraphState:
    """选项分支扇出节点：清理旧状态并触发并发分支。"""
    return {
        "options": {},
        "correct_option": "",
        "explanation": "",
        "correct_meaning": "",
        "distractors": [],
        "options_agent_error": "",
        "correct_meaning_agent_error": "",
        "distractor_agent_error": "",
    }


async def _correct_meaning_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """正确义项节点：只生成正确释义与解析。"""
    target_word = state["target_word"]
    story = state.get("story", "")
    dictionary_meanings = list(state.get("dictionary_meanings", []))
    logger.debug(
        "开始生成正确义项：用户ID=%s 目标词=%s story长度=%s 词典候选=%s",
        state["user_id"],
        target_word,
        len(story),
        len(dictionary_meanings),
    )
    try:
        result = await generate_text(_build_correct_meaning_prompt(target_word, story, dictionary_meanings))
        correct_meaning = str(result.get("correct_meaning", "")).strip()
        explanation = str(result.get("explanation", "")).strip()
    except Exception as e:
        logger.warning(
            "生成正确义项失败：用户ID=%s 错误=%s",
            state["user_id"],
            str(e),
        )
        return {
            "correct_meaning": "",
            "explanation": "",
            "correct_meaning_agent_error": f"correct_meaning_agent失败: {e}",
        }

    logger.debug(
        "正确义项结果：义项=%s 解析预览=%s",
        correct_meaning,
        _preview_text(explanation),
    )
    return {
        "correct_meaning": correct_meaning,
        "explanation": explanation,
        "correct_meaning_agent_error": "",
    }


async def _distractor_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """干扰项节点：只生成 3 个候选干扰项。"""
    target_word = state["target_word"]
    story = state.get("story", "")
    dictionary_meanings = list(state.get("dictionary_meanings", []))
    logger.debug(
        "开始生成干扰项：用户ID=%s 目标词=%s story长度=%s 词典候选=%s",
        state["user_id"],
        target_word,
        len(story),
        len(dictionary_meanings),
    )
    try:
        result = await generate_text(_build_distractor_prompt(target_word, story, dictionary_meanings))
        distractors = _normalize_distractors(result.get("distractors"))
    except Exception as e:
        logger.warning(
            "生成干扰项失败：用户ID=%s 错误=%s",
            state["user_id"],
            str(e),
        )
        return {
            "distractors": [],
            "distractor_agent_error": f"distractor_agent失败: {e}",
        }

    logger.debug(
        "干扰项结果：%s",
        distractors,
    )
    return {
        "distractors": distractors,
        "distractor_agent_error": "",
    }


async def _options_merge_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """合并节点：将正确义与干扰项组合成最终 A/B/C/D 选项。"""
    logger.debug("开始合并选项：用户ID=%s", state["user_id"])

    correct_meaning = str(state.get("correct_meaning", "")).strip()
    distractors = _normalize_distractors(state.get("distractors", []))
    options, correct_option, merge_errors = _merge_options(correct_meaning, distractors)

    upstream_errors = [
        str(state.get("correct_meaning_agent_error", "")).strip(),
        str(state.get("distractor_agent_error", "")).strip(),
    ]
    all_errors = [err for err in [*upstream_errors, *merge_errors] if err]
    options_agent_error = "; ".join(all_errors)

    if all_errors:
        logger.warning(
            "合并选项失败：用户ID=%s 错误=%s",
            state["user_id"],
            all_errors,
        )
        return {
            "options": {},
            "correct_option": "",
            "options_agent_error": options_agent_error,
        }

    logger.info(
        "选项合并完成：用户ID=%s 选项数=%s 正确项=%s",
        state["user_id"],
        len(options),
        correct_option,
    )
    logger.debug(
        "最终选项：%s",
        options,
    )
    return {
        "options": options,
        "correct_option": correct_option,
        "options_agent_error": "",
    }


async def _review_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """审核节点：本地规则先挡错，只有本地通过才调用 LLM 做语义细审。"""
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", MAX_RETRY_COUNT))
    logger.debug(
        "开始审核题目：用户ID=%s 重试=%s/%s",
        state["user_id"],
        retry_count,
        max_retries,
    )

    candidate_content = {
        "target_word": state["target_word"],
        "story": state.get("story", ""),
        "options": state.get("options", {}),
        "correct_option": state.get("correct_option", ""),
        "explanation": state.get("explanation", ""),
    }
    story_agent_error = str(state.get("story_agent_error", "")).strip()
    correct_meaning_agent_error = str(state.get("correct_meaning_agent_error", "")).strip()
    distractor_agent_error = str(state.get("distractor_agent_error", "")).strip()
    options_agent_error = str(state.get("options_agent_error", "")).strip()
    dictionary_lookup_error = str(state.get("dictionary_lookup_error", "")).strip()
    option_directness_errors = _validate_option_directness(candidate_content.get("options", {}))

    deterministic_valid, deterministic_errors = validate_question(QUESTION_TYPE, candidate_content)
    local_errors: list[str] = []
    for err in [
        story_agent_error,
        correct_meaning_agent_error,
        distractor_agent_error,
        options_agent_error,
        *deterministic_errors,
        *option_directness_errors,
    ]:
        if err and err not in local_errors:
            local_errors.append(err)

    local_pass = len(local_errors) == 0 and deterministic_valid and not option_directness_errors

    llm_valid = False
    story_ok: bool | None = None
    options_ok: bool | None = None
    llm_errors: list[str] = []
    if local_pass:
        try:
            review_result = await generate_text(_build_review_prompt(candidate_content))
            llm_valid = _to_optional_bool(review_result.get("is_valid")) is True
            story_ok = _to_optional_bool(review_result.get("story_ok"))
            options_ok = _to_optional_bool(review_result.get("options_ok"))
            llm_errors = _normalize_errors(review_result.get("errors"))
        except Exception as e:
            llm_errors = [f"review_agent失败: {e}"]
            logger.warning(
                "语义审核失败：用户ID=%s 错误=%s",
                state["user_id"],
                str(e),
            )
    else:
        logger.debug("本地规则未通过，跳过语义审核：用户ID=%s", state["user_id"])
    logger.debug(
        "审核明细：用户ID=%s 本地通过=%s 规则通过=%s 语义通过=%s story_ok=%s options_ok=%s 词典候选=%s 词典错误=%s 本地错误=%s 语义错误=%s",
        state["user_id"],
        local_pass,
        deterministic_valid,
        llm_valid,
        story_ok,
        options_ok,
        len(state.get("dictionary_meanings", [])),
        dictionary_lookup_error,
        local_errors,
        llm_errors,
    )

    merged_errors = [*local_errors]
    for err in llm_errors:
        if err and err not in merged_errors:
            merged_errors.append(err)

    if story_ok is None and story_agent_error:
        story_ok = False
    if options_ok is None and (correct_meaning_agent_error or distractor_agent_error or options_agent_error):
        options_ok = False
    if option_directness_errors:
        options_ok = False

    is_valid = local_pass and llm_valid and len(llm_errors) == 0
    if is_valid:
        logger.info(
            "题目审核通过：用户ID=%s 重试次数=%s",
            state["user_id"],
            retry_count,
        )
        return {
            "review_status": "pass",
            "review_errors": [],
        }

    next_retry_count = retry_count + 1
    if next_retry_count >= max_retries:
        logger.warning(
            "题目审核失败达到上限：用户ID=%s 重试=%s 错误=%s",
            state["user_id"],
            next_retry_count,
            merged_errors,
        )
        return {
            "review_status": "max_retries",
            "review_errors": merged_errors,
            "retry_count": next_retry_count,
        }

    review_status = _classify_review_failure(merged_errors, story_ok, options_ok)
    logger.debug(
        "审核路由：用户ID=%s 状态=%s 下一次重试=%s/%s",
        state["user_id"],
        review_status,
        next_retry_count,
        max_retries,
    )
    logger.warning(
        "题目审核未通过：用户ID=%s 状态=%s 重试=%s/%s 错误=%s",
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


async def _formatter_agent(state: ContextGuessGraphState) -> ContextGuessGraphState:
    """格式化节点：将图中中间字段整理为前端可消费的最终 content。"""
    logger.debug(
        "开始格式化题目：用户ID=%s",
        state["user_id"],
    )
    story = str(state.get("story", ""))
    target_word = state["target_word"]
    story_target_forms = extract_target_surface_forms(story, target_word)
    final_content = {
        "target_word": target_word,
        "story": story,
        "story_target_forms": story_target_forms,
        "options": state.get("options", {}),
        "correct_option": state.get("correct_option", ""),
        "explanation": state.get("explanation", ""),
    }

    logger.info(
        "格式化题目完成：用户ID=%s",
        state["user_id"],
    )
    return {
        "story_target_forms": story_target_forms,
        "final_content": final_content,
    }


def _mark_failed(_: ContextGuessGraphState) -> ContextGuessGraphState:
    """失败终点占位节点：不产出内容，仅用于让图正常收敛到 END。"""
    logger.debug("题目图节点触发：节点=mark_failed")
    return {}


def _route_after_review(state: ContextGuessGraphState) -> ReviewStatus:
    """根据 review_status 返回条件边标签，驱动 LangGraph 路由。"""
    status = state.get("review_status", "max_retries")
    logger.debug(
        "图路由决策：用户ID=%s 状态=%s",
        state.get("user_id", "-"),
        status,
    )
    if status in {"pass", "fail_story", "fail_options", "fail_both", "max_retries"}:
        return status
    return "max_retries"


def _build_context_guess_graph():
    """构建并编译 context_guess 的多 Agent 状态图。"""
    logger.debug("开始构建题目图：type=%s", QUESTION_TYPE)
    graph = StateGraph(ContextGuessGraphState)
    graph.add_node("story_agent", _story_agent)
    graph.add_node("dictionary_lookup_tool", _dictionary_lookup_tool)
    graph.add_node("options_fanout", _options_fanout)
    graph.add_node("correct_meaning_agent", _correct_meaning_agent)
    graph.add_node("distractor_agent", _distractor_agent)
    graph.add_node("options_merge_agent", _options_merge_agent)
    graph.add_node("review_agent", _review_agent)
    graph.add_node("formatter_agent", _formatter_agent)
    graph.add_node("mark_failed", _mark_failed)

    graph.add_edge(START, "story_agent")
    graph.add_edge("story_agent", "dictionary_lookup_tool")
    graph.add_edge("dictionary_lookup_tool", "options_fanout")
    graph.add_edge("options_fanout", "correct_meaning_agent")
    graph.add_edge("options_fanout", "distractor_agent")
    graph.add_edge("correct_meaning_agent", "options_merge_agent")
    graph.add_edge("distractor_agent", "options_merge_agent")
    graph.add_edge("options_merge_agent", "review_agent")
    graph.add_conditional_edges(
        "review_agent",
        _route_after_review,
        {
            "pass": "formatter_agent",
            "fail_story": "story_agent",
            "fail_options": "options_fanout",
            "fail_both": "story_agent",
            "max_retries": "mark_failed",
        },
    )
    graph.add_edge("formatter_agent", END)
    graph.add_edge("mark_failed", END)
    logger.debug("题目图构建完成：type=%s nodes=%s", QUESTION_TYPE, 9)
    return graph.compile()


context_guess_graph = _build_context_guess_graph()


async def generate_context_guess_content(
    user_id: int,
    target_word: str,
    max_retries: int = MAX_RETRY_COUNT,
) -> dict[str, Any] | None:
    """图执行入口：初始化状态并运行图，成功返回 final_content，失败返回 None。"""
    initial_state: ContextGuessGraphState = build_initial_state(
        user_id=user_id,
        max_retries=max_retries,
        extra_state={"target_word": target_word},
    )
    return await run_graph_generation(
        graph=context_guess_graph,
        logger=logger,
        question_type=QUESTION_TYPE,
        user_id=user_id,
        initial_state=initial_state,
    )
