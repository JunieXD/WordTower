from __future__ import annotations


LEVEL_BASE_EXP = 100
LEVEL_GROWTH_EXP = 20


def get_level_info(total_exp: int) -> dict[str, int]:
    """
    Progression formula:
    need_exp(level n -> n+1) = LEVEL_BASE_EXP + LEVEL_GROWTH_EXP * n
    where n starts from 0.
    """
    exp = max(int(total_exp), 0)
    level = 0
    need = LEVEL_BASE_EXP

    while exp >= need:
        exp -= need
        level += 1
        need = LEVEL_BASE_EXP + LEVEL_GROWTH_EXP * level

    return {
        "level": level,
        "current_level_exp": exp,
        "next_level_need_exp": need,
    }


def get_level_from_exp(total_exp: int) -> int:
    return int(get_level_info(total_exp)["level"])
