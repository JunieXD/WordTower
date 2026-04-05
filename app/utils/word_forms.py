from __future__ import annotations

import re

from lemminflect import getAllLemmas

WORD_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def tokenize_english_words(text: str) -> list[str]:
    """提取文本中的英文词元。"""
    return WORD_TOKEN_RE.findall(text or "")


def get_lemma_set(word: str) -> set[str]:
    """返回单词的 lemma 集合，包含原词本身。"""
    normalized = word.strip().lower()
    if not normalized:
        return set()

    lemmas = {normalized}
    for values in getAllLemmas(normalized).values():
        for lemma in values:
            if lemma:
                lemmas.add(lemma.lower())
    return lemmas


def token_matches_target(token: str, target_word: str) -> bool:
    """判断 token 是否是目标词的某种词形。"""
    token_lemmas = get_lemma_set(token)
    target_lemmas = get_lemma_set(target_word)
    return bool(token_lemmas & target_lemmas)


def text_contains_target_form(text: str, target_word: str) -> bool:
    """判断一段文本中是否出现目标词或其词形变化。"""
    return any(token_matches_target(token, target_word) for token in tokenize_english_words(text))


def extract_target_surface_forms(text: str, target_word: str) -> list[str]:
    """
    提取文本里命中的目标词表层形式。

    例如 target_word=go, story 中出现 went，则返回 ["went"]。
    """
    forms: list[str] = []
    seen: set[str] = set()
    for token in tokenize_english_words(text):
        lowered = token.lower()
        if lowered in seen:
            continue
        if token_matches_target(token, target_word):
            seen.add(lowered)
            forms.append(token)
    return forms
