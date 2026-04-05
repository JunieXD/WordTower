from app.utils.config import settings
from openai import AsyncOpenAI
import json
import re
from typing import Dict, Any, List, Tuple
from app.utils.logger import get_logger
from app.utils.word_forms import text_contains_target_form

client = AsyncOpenAI(api_key=settings.ARK_API_KEY, base_url=settings.ARK_API_BASE_URL)
logger = get_logger(__name__)

# 最大重试次数
MAX_RETRY_COUNT = 3
MAX_JSON_PARSE_RETRY_COUNT = 2
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")


def _preview_text(text: str, limit: int = 160) -> str:
    """截断长文本用于 debug 输出。"""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _try_parse_first_json_object(content: str) -> Dict[str, Any]:
    """
    尝试从文本中解析第一个 JSON 对象。

    允许模型在 JSON 后附带多余文本（会忽略尾随内容）。
    """
    decoder = json.JSONDecoder()

    # 1) 直接从开头解析
    obj, end = decoder.raw_decode(content)
    if not isinstance(obj, dict):
        raise ValueError(f"LLM 返回的 JSON 顶层必须是对象，当前为: {type(obj).__name__}")

    trailing = content[end:].strip()
    if trailing:
        logger.warning("LLM 返回含尾随文本，已忽略：%s", _preview_text(trailing))
    return obj


def _normalize_smart_quotes(content: str) -> str:
    """将常见的智能引号转换为标准引号，便于后续 JSON 修复。"""
    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
    }
    normalized = content
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _strip_json_comments(content: str) -> str:
    """移除 JSON 中夹带的 // 和 /* */ 注释，避免干扰解析。"""
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(content)

    while index < length:
        char = content[index]
        next_char = content[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and content[index] not in "\r\n":
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (content[index] == "*" and content[index + 1] == "/"):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def _escape_control_chars_in_strings(content: str) -> str:
    """修复字符串值里的原始换行、回车和制表符。"""
    result: list[str] = []
    in_string = False
    escape = False

    for char in content:
        if in_string:
            if escape:
                result.append(char)
                escape = False
                continue

            if char == "\\":
                result.append(char)
                escape = True
                continue

            if char == '"':
                result.append(char)
                in_string = False
                continue

            if char == "\n":
                result.append("\\n")
                continue
            if char == "\r":
                result.append("\\r")
                continue
            if char == "\t":
                result.append("\\t")
                continue

            result.append(char)
            continue

        result.append(char)
        if char == '"':
            in_string = True

    return "".join(result)


def _repair_unescaped_quotes_in_json(content: str) -> str:
    """
    修复 JSON 字符串值中未转义的双引号。

    常见于模型输出：
    "feedback": "这里提到 "so far" 不合适"
    """
    repaired: list[str] = []
    in_string = False
    escape = False
    length = len(content)
    index = 0

    while index < length:
        char = content[index]
        if not in_string:
            repaired.append(char)
            if char == '"':
                in_string = True
            index += 1
            continue

        if escape:
            repaired.append(char)
            escape = False
            index += 1
            continue

        if char == "\\":
            repaired.append(char)
            escape = True
            index += 1
            continue

        if char == '"':
            lookahead = index + 1
            while lookahead < length and content[lookahead] in " \t\r\n":
                lookahead += 1
            next_char = content[lookahead] if lookahead < length else ""

            # 合法 JSON 中，字符串结束后的下一个有效字符通常是这些分隔符。
            if next_char in {",", "}", "]", ":"} or next_char == "":
                repaired.append(char)
                in_string = False
            else:
                repaired.append('\\"')
            index += 1
            continue

        repaired.append(char)
        index += 1

    return "".join(repaired)


def _remove_trailing_commas(content: str) -> str:
    """移除对象或数组结尾前多余的逗号。"""
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(content)

    while index < length:
        char = content[index]

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < length and content[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and content[lookahead] in "}]":
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)


def _normalize_python_literals(content: str) -> str:
    """将 True/False/None 等 Python 字面量替换为 JSON 字面量。"""
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(content)

    while index < length:
        char = content[index]

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if content.startswith("True", index):
            prev_char = content[index - 1] if index > 0 else ""
            next_char = content[index + 4] if index + 4 < length else ""
            if not (prev_char.isalnum() or prev_char == "_") and not (next_char.isalnum() or next_char == "_"):
                result.append("true")
                index += 4
                continue

        if content.startswith("False", index):
            prev_char = content[index - 1] if index > 0 else ""
            next_char = content[index + 5] if index + 5 < length else ""
            if not (prev_char.isalnum() or prev_char == "_") and not (next_char.isalnum() or next_char == "_"):
                result.append("false")
                index += 5
                continue

        if content.startswith("None", index):
            prev_char = content[index - 1] if index > 0 else ""
            next_char = content[index + 4] if index + 4 < length else ""
            if not (prev_char.isalnum() or prev_char == "_") and not (next_char.isalnum() or next_char == "_"):
                result.append("null")
                index += 4
                continue

        result.append(char)
        index += 1

    return "".join(result)


def _repair_json_like_content(content: str) -> str:
    """对常见的类 JSON 输出做防御性修复。"""
    repaired = _normalize_smart_quotes(content)
    repaired = _strip_json_comments(repaired)
    repaired = _escape_control_chars_in_strings(repaired)
    repaired = _repair_unescaped_quotes_in_json(repaired)
    repaired = _remove_trailing_commas(repaired)
    repaired = _normalize_python_literals(repaired)
    return repaired
def answer_contains_target_word_variant(target_word: str, user_input: str) -> bool:
    """检查用户答案中是否包含目标词或其常见词形。"""
    return text_contains_target_form(user_input, target_word)


def _normalize_text_for_comparison(text: str) -> str:
    """用于比较两段文本是否本质相同。"""
    lowered = text.strip().lower()
    return re.sub(r"[\s，。！？；：、“”‘’（）()【】《》…,.!?;:'\"-]+", "", lowered)


def precheck_translation_answer(
    target_word: str,
    chinese_sentence: str,
    user_input: str,
) -> Dict[str, Any] | None:
    """
    对翻译题答案做本地硬规则预检。

    明显无效的答案直接判错，避免 LLM 误判。
    """
    normalized_input = user_input.strip()
    if not normalized_input:
        return {
            "is_correct": False,
            "score": 0,
            "feedback": "你还没有提交英文翻译，请先写出完整的英文句子。",
            "better_translation": "",
        }

    if _normalize_text_for_comparison(normalized_input) == _normalize_text_for_comparison(chinese_sentence):
        return {
            "is_correct": False,
            "score": 0,
            "feedback": "你提交的是原中文句子，没有把题目翻译成英文。请直接写英文译文。",
            "better_translation": "",
        }

    if CHINESE_CHAR_RE.search(normalized_input):
        return {
            "is_correct": False,
            "score": 0,
            "feedback": "你的答案里包含中文。翻译题需要直接提交完整的英文句子，不要夹带中文。",
            "better_translation": "",
        }

    if not LATIN_CHAR_RE.search(normalized_input):
        return {
            "is_correct": False,
            "score": 0,
            "feedback": "你的答案里没有有效的英文内容。请直接写出完整的英文翻译。",
            "better_translation": "",
        }

    if not answer_contains_target_word_variant(target_word, normalized_input):
        return {
            "is_correct": False,
            "score": 20,
            "feedback": f"这是一次尝试，但你没有使用目标单词 {target_word} 或它的正确变形，所以这题不能判对。",
            "better_translation": "",
        }

    return None


def validate_context_guess(content: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证 context_guess 类型题目
    规则：
    1. story 中必须包含 target_word
    2. correct_option 必须是 A/B/C/D 中的一个
    3. options 中不能有两个选项内容完全相同
    """
    errors = []
    
    # 检查必要字段是否存在
    required_fields = ["target_word", "story", "options", "correct_option", "explanation"]
    for field in required_fields:
        if field not in content:
            errors.append(f"缺少必要字段: {field}")
    
    if errors:
        return False, errors
    
    target_word = content.get("target_word", "")
    story = content.get("story", "")
    options = content.get("options", {})
    correct_option = content.get("correct_option", "")
    
    # 1. 检查 story 中是否包含 target_word 或其词形变化
    if not text_contains_target_form(story, target_word):
        errors.append(f"story 中未包含目标单词 '{target_word}' 或其词形变化")
    
    # 2. 检查 correct_option 是否是 A/B/C/D
    valid_options = ["A", "B", "C", "D"]
    if correct_option not in valid_options:
        errors.append(f"correct_option 必须是 A/B/C/D 中的一个，当前值: '{correct_option}'")
    
    # 3. 检查 options 是否有 A/B/C/D 四个选项
    for opt in valid_options:
        if opt not in options:
            errors.append(f"options 中缺少选项 {opt}")
    
    # 4. 检查是否有重复的选项内容
    option_values = list(options.values())
    seen = set()
    for value in option_values:
        if value in seen:
            errors.append(f"存在重复的选项内容: '{value}'")
            break
        seen.add(value)
    
    return len(errors) == 0, errors


def validate_cloze_test(content: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证 cloze_test 类型题目
    规则：
    1. cloze_text 必须包含正确数量的占位符 ____[n]____
    2. shuffled_options 和 correct_sequence 长度必须一致
    3. correct_sequence 中的所有单词必须存在于 shuffled_options 中
    """
    errors = []
    
    # 检查必要字段是否存在
    required_fields = ["cloze_text", "shuffled_options", "correct_sequence", "chinese_translation"]
    for field in required_fields:
        if field not in content:
            errors.append(f"缺少必要字段: {field}")
    
    if errors:
        return False, errors
    
    cloze_text = content.get("cloze_text", "")
    shuffled_options = content.get("shuffled_options", [])
    correct_sequence = content.get("correct_sequence", [])
    
    # 1. 检查占位符数量
    placeholders = re.findall(r"____\[(\d+)\]____", cloze_text)
    placeholder_count = len(placeholders)
    
    if placeholder_count != len(correct_sequence):
        errors.append(f"占位符数量 ({placeholder_count}) 与 correct_sequence 长度 ({len(correct_sequence)}) 不匹配")
    
    # 2. 检查 shuffled_options 和 correct_sequence 长度是否一致
    if len(shuffled_options) != len(correct_sequence):
        errors.append(f"shuffled_options 长度 ({len(shuffled_options)}) 与 correct_sequence 长度 ({len(correct_sequence)}) 不匹配")
    
    # 3. 检查 correct_sequence 中的单词是否都在 shuffled_options 中
    shuffled_options_set = {str(word).strip().lower() for word in shuffled_options}
    for word in correct_sequence:
        if str(word).strip().lower() not in shuffled_options_set:
            errors.append(f"correct_sequence 中的单词 '{word}' 不在 shuffled_options 中")
    
    # 4. 检查占位符编号是否正确 (从1开始连续)
    placeholder_nums = sorted([int(p) for p in placeholders])
    expected_nums = list(range(1, len(placeholders) + 1))
    if placeholder_nums != expected_nums:
        errors.append(f"占位符编号不正确，期望: {expected_nums}，实际: {placeholder_nums}")
    
    return len(errors) == 0, errors


def validate_keyword_translation(content: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证 keyword_translation 类型题目
    规则：
    1. reference_answer 必须包含 target_word
    """
    errors = []
    
    # 检查必要字段是否存在
    required_fields = ["target_word", "chinese_sentence", "reference_answer"]
    for field in required_fields:
        if field not in content:
            errors.append(f"缺少必要字段: {field}")
    
    if errors:
        return False, errors
    
    target_word = content.get("target_word", "")
    reference_answer = content.get("reference_answer", "").lower()
    
    if not text_contains_target_form(reference_answer, target_word):
        errors.append(f"reference_answer 中未包含目标单词 '{target_word}' 或其词形变化")
    
    return len(errors) == 0, errors


def validate_question(question_type: str, content: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    根据题目类型验证内容
    返回: (是否通过, 错误列表)
    """
    if question_type == settings.QUESTION_TYPES[0]:  # context_guess
        return validate_context_guess(content)
    elif question_type == settings.QUESTION_TYPES[1]:  # cloze_test
        return validate_cloze_test(content)
    elif question_type == settings.QUESTION_TYPES[2]:  # keyword_translation
        return validate_keyword_translation(content)
    else:
        return True, []  # 未知类型，跳过验证


def _parse_json_response(content: str) -> Dict[str, Any]:
    """解析并清理 LLM 返回的 JSON 内容"""
    # 清理可能的 markdown 代码块标记
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]  # 移除 ```json
    elif content.startswith("```"):
        content = content[3:]  # 移除 ```
    
    if content.endswith("```"):
        content = content[:-3]  # 移除结尾的 ```
    
    content = content.strip()

    # 移除模型返回中的思考内容，例如
    # <think> ... </think> {"your": "json"}
    content = re.sub(r"<think>[\s\S]*?</think>\s*", "", content)
    logger.debug("LLM 原始内容清洗后预览：%s", _preview_text(content))

    try:
        parsed = _try_parse_first_json_object(content)
        logger.debug(
            "LLM JSON 解析成功：顶层键=%s",
            list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__,
        )
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        # 2) 若开头不是 JSON，尝试从第一个 '{' 开始解析
        first_brace = content.find("{")
        if first_brace > 0:
            candidate = content[first_brace:]
            try:
                parsed = _try_parse_first_json_object(candidate)
                logger.warning("LLM 返回前缀存在非 JSON 文本，已自动跳过前缀")
                logger.debug("LLM JSON 解析成功（跳过前缀）：顶层键=%s", list(parsed.keys()))
                return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        repaired_content = _repair_json_like_content(content)
        if repaired_content != content:
            try:
                parsed = _try_parse_first_json_object(repaired_content)
                logger.warning("LLM 返回存在非严格 JSON 内容，已自动修复后解析")
                logger.debug("LLM JSON 修复后解析成功：顶层键=%s", list(parsed.keys()))
                return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        logger.error("解析 LLM 返回 JSON 失败：错误=%s", str(e))
        logger.error("解析 LLM 返回 JSON 失败：清理后内容=%s", content)
        raise ValueError(f"LLM 返回的内容不是有效的 JSON 格式: {e}")


async def _call_llm(prompt: str) -> Dict[str, Any]:
    """调用 LLM 并返回解析后的 JSON"""
    system_prompt = (
        "You are a strict JSON API. Output ONLY valid JSON. "
        "Do not output markdown blocks (```json), conversational text, comments, or internal thinking. "
        "Start with `{` and end with `}`. "
        "Use standard JSON syntax only: double-quoted keys, double-quoted string values, lowercase true/false/null, no trailing commas. "
        "If a string value needs quotation marks, escape them as \\\" or prefer single quotes / Chinese quotes. "
        "Do not include raw newlines or tabs inside JSON string values; escape them."
    )

    last_error: ValueError | None = None
    for attempt in range(MAX_JSON_PARSE_RETRY_COUNT):
        logger.debug(
            "LLM 调用开始：model=%s attempt=%s/%s prompt长度=%s prompt预览=%s",
            settings.ARK_API_MODEL_ID,
            attempt + 1,
            MAX_JSON_PARSE_RETRY_COUNT,
            len(prompt),
            _preview_text(prompt),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        if attempt > 0:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON after parsing. "
                        "Return the same content again as a single valid JSON object only, "
                        "using strict JSON syntax with no comments, no trailing commas, and properly escaped quotes."
                    ),
                }
            )

        response = await client.chat.completions.create(
            model=settings.ARK_API_MODEL_ID,
            messages=messages,
            extra_body={"thinking": {"type": "disabled"}, "temperature": 0.7},
        )
        content = response.choices[0].message.content
        logger.debug("LLM 返回内容预览：%s", _preview_text(content or ""))
        try:
            return _parse_json_response(content)
        except ValueError as e:
            last_error = e
            logger.warning(
                "LLM JSON 解析失败，准备重试：attempt=%s/%s 错误=%s",
                attempt + 1,
                MAX_JSON_PARSE_RETRY_COUNT,
                str(e),
            )

    if last_error is None:
        raise ValueError("LLM 返回内容为空，无法解析为 JSON")
    raise last_error


async def generate_text(prompt: str) -> Dict[str, Any]:
    """
    生成文本（不带验证的原始版本，保持向后兼容）
    """
    return await _call_llm(prompt)
