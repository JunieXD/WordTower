from app.utils.config import settings
from openai import AsyncOpenAI
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from app.utils.logger import get_logger

client = AsyncOpenAI(api_key=settings.ARK_API_KEY, base_url=settings.ARK_API_BASE_URL)
logger = get_logger(__name__)

# 最大重试次数
MAX_RETRY_COUNT = 3


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


class QuestionValidationError(Exception):
    """题目验证失败时抛出的异常"""
    def __init__(self, message: str, errors: List[str]):
        self.message = message
        self.errors = errors
        super().__init__(self.message)


def generate_word_variants(word: str) -> List[str]:
    """
    生成单词的常见变体形式（复数、过去式、现在分词等）
    返回包含原词和所有变体的列表
    """
    word = word.lower()
    variants = {word}  # 使用集合避免重复
    
    # 1. 复数形式 / 第三人称单数
    # -s
    variants.add(word + "s")
    # -es (以 s, x, z, ch, sh 结尾)
    if word.endswith(("s", "x", "z", "ch", "sh")):
        variants.add(word + "es")
    # -ies (以辅音+y结尾)
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        variants.add(word[:-1] + "ies")
    # -ves (以f或fe结尾)
    if word.endswith("f"):
        variants.add(word[:-1] + "ves")
    if word.endswith("fe"):
        variants.add(word[:-2] + "ves")
    
    # 2. 过去式 / 过去分词
    # -ed
    variants.add(word + "ed")
    # -d (以e结尾)
    if word.endswith("e"):
        variants.add(word + "d")
    # -ied (以辅音+y结尾)
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        variants.add(word[:-1] + "ied")
    # 双写辅音 + ed (以辅音结尾的短词，如 stop -> stopped)
    if len(word) >= 2 and word[-1] not in "aeiouwy" and word[-2] in "aeiou":
        variants.add(word + word[-1] + "ed")
    
    # 3. 现在分词
    # -ing
    variants.add(word + "ing")
    # 去e加ing (以e结尾)
    if word.endswith("e") and not word.endswith("ee"):
        variants.add(word[:-1] + "ing")
    # 双写辅音 + ing
    if len(word) >= 2 and word[-1] not in "aeiouwy" and word[-2] in "aeiou":
        variants.add(word + word[-1] + "ing")
    
    # 4. 比较级 / 最高级 (主要针对形容词)
    # -er, -est
    variants.add(word + "er")
    variants.add(word + "est")
    # 去e加er/est
    if word.endswith("e"):
        variants.add(word + "r")
        variants.add(word + "st")
    # -ier, -iest (以辅音+y结尾)
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        variants.add(word[:-1] + "ier")
        variants.add(word[:-1] + "iest")
    
    # 5. 副词形式
    # -ly
    variants.add(word + "ly")
    # -ily (以辅音+y结尾)
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        variants.add(word[:-1] + "ily")
    
    return list(variants)


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
    
    # 1. 检查 story 中是否包含 target_word 或其变体形式
    word_variants = generate_word_variants(target_word)
    story_lower = story.lower()
    found_in_story = False
    for variant in word_variants:
        pattern = r'\b' + re.escape(variant) + r'\b'
        if re.search(pattern, story_lower, re.IGNORECASE):
            found_in_story = True
            break
    if not found_in_story:
        errors.append(f"story 中未包含目标单词 '{target_word}' 或其变体形式")
    
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
    
    # 3. 检查 correct_sequence 中的单词是否都在 shuffled_options 中（考虑变体形式）
    # 为 shuffled_options 中的每个单词生成变体集合
    shuffled_variants_map = {}
    for word in shuffled_options:
        for variant in generate_word_variants(word):
            shuffled_variants_map[variant] = word  # 变体映射到原词
    
    for word in correct_sequence:
        word_lower = word.lower()
        # 检查该单词或其变体是否在 shuffled_options 的变体集合中
        word_variants = generate_word_variants(word)
        found = any(v in shuffled_variants_map for v in word_variants)
        if not found:
            errors.append(f"correct_sequence 中的单词 '{word}' 不在 shuffled_options 中（也没有匹配的变体形式）")
    
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
    
    # 生成目标单词的所有变体形式
    word_variants = generate_word_variants(target_word)
    
    # 检查 reference_answer 中是否包含 target_word 或其变体
    # 使用单词边界匹配，确保是完整的单词匹配
    found = False
    for variant in word_variants:
        # 使用 \b 单词边界确保匹配完整单词
        pattern = r'\b' + re.escape(variant) + r'\b'
        if re.search(pattern, reference_answer, re.IGNORECASE):
            found = True
            break
    
    if not found:
        errors.append(f"reference_answer 中未包含目标单词 '{target_word}' 或其变体形式")
    
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

        logger.error("解析 LLM 返回 JSON 失败：错误=%s", str(e))
        logger.error("解析 LLM 返回 JSON 失败：清理后内容=%s", content)
        raise ValueError(f"LLM 返回的内容不是有效的 JSON 格式: {e}")


async def _call_llm(prompt: str) -> Dict[str, Any]:
    """调用 LLM 并返回解析后的 JSON"""
    logger.debug(
        "LLM 调用开始：model=%s prompt长度=%s prompt预览=%s",
        settings.ARK_API_MODEL_ID,
        len(prompt),
        _preview_text(prompt),
    )
    response = await client.chat.completions.create(
        model=settings.ARK_API_MODEL_ID,
        messages=[
            {"role": "system", "content": "You are a strict JSON API. Output ONLY valid JSON. Do not output markdown blocks (```json), conversational text, or internal thinking. Start with `{` and end with `}`."},
            {"role": "user", "content": prompt}
        ],
        extra_body={"thinking": {"type": "disabled"}, "temperature": 0.7}
    )
    content = response.choices[0].message.content
    logger.debug("LLM 返回内容预览：%s", _preview_text(content or ""))
    return _parse_json_response(content)


async def generate_text(prompt: str) -> Dict[str, Any]:
    """
    生成文本（不带验证的原始版本，保持向后兼容）
    """
    return await _call_llm(prompt)


async def generate_question_with_validation(
    prompt: str, 
    question_type: str,
    max_retries: int = MAX_RETRY_COUNT
) -> Dict[str, Any]:
    """
    生成题目并进行验证，验证失败时自动重试
    
    Args:
        prompt: 生成题目的 prompt
        question_type: 题目类型
        max_retries: 最大重试次数
    
    Returns:
        验证通过的题目内容
    
    Raises:
        QuestionValidationError: 达到最大重试次数仍验证失败
        ValueError: JSON 解析错误
    """
    last_errors = []
    logger.debug("题目生成校验开始：题型=%s 最大重试=%s", question_type, max_retries)
    
    for attempt in range(max_retries):
        try:
            logger.debug("题目生成校验尝试：题型=%s attempt=%s/%s", question_type, attempt + 1, max_retries)
            content = await _call_llm(prompt)
            
            # 验证题目内容
            is_valid, errors = validate_question(question_type, content)
            logger.debug(
                "题目生成校验结果：题型=%s attempt=%s/%s is_valid=%s errors=%s",
                question_type,
                attempt + 1,
                max_retries,
                is_valid,
                errors,
            )
            
            if is_valid:
                if attempt > 0:
                    logger.info("题目校验重试成功：尝试次数=%s 最大重试=%s 题型=%s", attempt + 1, max_retries, question_type)
                return content
            
            # 验证失败，记录错误并重试
            last_errors = errors
            logger.warning(
                "题目校验失败：尝试次数=%s 最大重试=%s 题型=%s 错误=%s",
                attempt + 1,
                max_retries,
                question_type,
                errors,
            )
            
        except ValueError as e:
            # JSON 解析失败也计入重试
            last_errors = [str(e)]
            logger.warning(
                "题目 JSON 解析失败：尝试次数=%s 最大重试=%s 题型=%s 错误=%s",
                attempt + 1,
                max_retries,
                question_type,
                str(e),
            )
    
    # 达到最大重试次数
    raise QuestionValidationError(
        f"题目验证失败，已达到最大重试次数 ({max_retries})",
        last_errors
    )
