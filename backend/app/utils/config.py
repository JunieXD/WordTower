import os
import random
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DAILY_CHALLENGE_CONFIG_PATH = PROJECT_ROOT / "config" / "daily_challenge.toml"


DEFAULT_DAILY_TAG_WEIGHTS = [
    {"min_floor": 1, "max_floor": 5, "weights": {"zk": 50, "gk": 30, "cet4": 15, "cet6": 5, "ky": 0}},
    {"min_floor": 6, "max_floor": 10, "weights": {"zk": 25, "gk": 35, "cet4": 25, "cet6": 10, "ky": 5}},
    {"min_floor": 11, "max_floor": 15, "weights": {"zk": 10, "gk": 25, "cet4": 35, "cet6": 20, "ky": 10}},
    {"min_floor": 16, "max_floor": 20, "weights": {"zk": 5, "gk": 15, "cet4": 35, "cet6": 25, "ky": 20}},
    {"min_floor": 21, "max_floor": 999999, "weights": {"zk": 0, "gk": 10, "cet4": 25, "cet6": 35, "ky": 30}},
]


DEFAULT_DAILY_CHALLENGE_CONFIG: dict[str, Any] = {
    "combat": {
        "player_max_hp": 100,
        "player_attack": 10,
        "enemy_hp": 30,
        "enemy_attack": 10,
        "heal_every_floors": 5,
        "heal_amount": 50,
    },
    "words": {
        "source_tags": ["zk", "gk", "cet4", "cet6", "ky"],
        "tag_weights": DEFAULT_DAILY_TAG_WEIGHTS,
    },
}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _parse_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        loaded = tomllib.load(file)
    return loaded if isinstance(loaded, dict) else {}


def _load_daily_challenge_config(path: Path) -> dict[str, Any]:
    loaded = _load_toml_file(path)
    return _deep_merge_dict(DEFAULT_DAILY_CHALLENGE_CONFIG, loaded)


def _resolve_config_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _normalize_daily_tag_weights(raw: Any) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        return DEFAULT_DAILY_TAG_WEIGHTS

    normalized: list[dict[str, object]] = []
    for rule in raw:
        if not isinstance(rule, dict):
            continue
        weights = rule.get("weights", {})
        if not isinstance(weights, dict):
            continue
        normalized.append(
            {
                "min_floor": int(rule.get("min_floor", 1)),
                "max_floor": int(rule.get("max_floor", 999999)),
                "weights": {str(tag): int(weight) for tag, weight in weights.items()},
            }
        )

    return normalized or DEFAULT_DAILY_TAG_WEIGHTS


def _normalize_str_list(raw: Any, default: list[str]) -> list[str]:
    if not isinstance(raw, list):
        return default
    normalized = [str(item).strip() for item in raw if str(item).strip()]
    return normalized or default


def get_question_type_weights(floor: int) -> list[int]:
    """根据楼层返回普通闯塔的题型权重。"""
    return [
        100 - min(floor / 10 * 4, 20),
        min(floor / 10 * 2, 10),
        min(floor / 10 * 2, 10),
    ]


def get_enemy_hp(floor: int) -> int:
    return int(floor * random.random()) + 10


def get_enemy_attack(floor: int) -> int:
    return int(floor * random.random()) + 10


def get_daily_question_type_weights(floor: int) -> list[int]:
    """每日挑战暂时复用普通闯塔的题型权重曲线。"""
    return get_question_type_weights(floor)


def get_daily_tag_weights(floor: int) -> dict[str, int]:
    """根据楼层命中每日挑战词源权重分段。"""
    for rule in settings.DAILY_CHALLENGE_TAG_WEIGHTS:
        min_floor = int(rule.get("min_floor", 1))
        max_floor = int(rule.get("max_floor", 999999))
        if min_floor <= floor <= max_floor:
            raw_weights = rule.get("weights", {})
            return {str(tag): int(weight) for tag, weight in raw_weights.items()}

    last_rule = settings.DAILY_CHALLENGE_TAG_WEIGHTS[-1]
    raw_weights = last_rule.get("weights", {})
    return {str(tag): int(weight) for tag, weight in raw_weights.items()}


class Settings:
    # ==================== 核心 ====================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "wordtower")

    # ==================== 基础设施 ====================
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:123456@localhost:5432/wordtower",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ==================== 战斗 / 题目 ====================
    QUESTION_TYPES = ["context_guess", "cloze_test", "keyword_translation"]
    QUESTION_GET_GENERATION_BATCH_SIZE: int = _parse_int(os.getenv("QUESTION_GET_GENERATION_BATCH_SIZE"), 5)
    SRS_ENABLED: bool = _parse_bool(os.getenv("SRS_ENABLED"), False)
    SRS_TARGET_RECALL: float = _parse_float(os.getenv("SRS_TARGET_RECALL"), 0.8)

    # ==================== HTTP / 运行环境 ====================
    COOKIE_SECURE: bool = _parse_bool(os.getenv("COOKIE_SECURE"), False)
    DB_POOL_SIZE: int = _parse_int(os.getenv("DB_POOL_SIZE"), 5)
    DB_MAX_OVERFLOW: int = _parse_int(os.getenv("DB_MAX_OVERFLOW"), 10)

    # ==================== 升级 ====================
    UPGRADE_HP_COINS: int = _parse_int(os.getenv("UPGRADE_HP_COINS"), 100)
    UPGRADE_ATTACK_COINS: int = _parse_int(os.getenv("UPGRADE_ATTACK_COINS"), 100)
    UPGRADE_CRIT_RATE_COINS: int = _parse_int(os.getenv("UPGRADE_CRIT_RATE_COINS"), 100)
    UPGRADE_HP_VALUE: int = _parse_int(os.getenv("UPGRADE_HP_VALUE"), 1)
    UPGRADE_ATTACK_VALUE: int = _parse_int(os.getenv("UPGRADE_ATTACK_VALUE"), 1)
    UPGRADE_CRIT_RATE_VALUE: float = _parse_float(os.getenv("UPGRADE_CRIT_RATE_VALUE"), 0.01)

    # ==================== 大模型 ====================
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "")
    ARK_API_BASE_URL: str = os.getenv(
        "ARK_API_BASE_URL",
        "https://ark.cn-beijing.volces.com/api/v3",
    )
    ARK_API_MODEL_ID: str = os.getenv("ARK_API_MODEL_ID", "doubao-seed-2-0-mini-260215")

    # ==================== 每日挑战：基础运行参数 ====================
    DAILY_CHALLENGE_RESET_HOUR: int = _parse_int(os.getenv("DAILY_CHALLENGE_RESET_HOUR"), 6)
    DAILY_CHALLENGE_TIMEZONE: str = os.getenv("DAILY_CHALLENGE_TIMEZONE", "Asia/Shanghai")
    DAILY_CHALLENGE_PREWARM_COUNT: int = _parse_int(os.getenv("DAILY_CHALLENGE_PREWARM_COUNT"), 6)
    DAILY_CHALLENGE_LEADERBOARD_LIMIT: int = _parse_int(
        os.getenv("DAILY_CHALLENGE_LEADERBOARD_LIMIT"),
        20,
    )

    # ==================== 每日挑战：规则文件 ====================
    DAILY_CHALLENGE_CONFIG_PATH: str = os.getenv(
        "DAILY_CHALLENGE_CONFIG_PATH",
        str(DEFAULT_DAILY_CHALLENGE_CONFIG_PATH),
    )
    _daily_challenge_config: dict[str, Any] = _load_daily_challenge_config(
        _resolve_config_path(DAILY_CHALLENGE_CONFIG_PATH)
    )
    _daily_combat_config: dict[str, Any] = _daily_challenge_config.get("combat", {})
    _daily_words_config: dict[str, Any] = _daily_challenge_config.get("words", {})

    # ==================== 每日挑战：战斗规则 ====================
    DAILY_CHALLENGE_PLAYER_MAX_HP: int = int(_daily_combat_config.get("player_max_hp", 100))
    DAILY_CHALLENGE_PLAYER_ATTACK: int = int(_daily_combat_config.get("player_attack", 10))
    DAILY_CHALLENGE_ENEMY_HP: int = int(_daily_combat_config.get("enemy_hp", 30))
    DAILY_CHALLENGE_ENEMY_ATTACK: int = int(_daily_combat_config.get("enemy_attack", 10))
    DAILY_CHALLENGE_HEAL_EVERY_FLOORS: int = int(_daily_combat_config.get("heal_every_floors", 5))
    DAILY_CHALLENGE_HEAL_AMOUNT: int = int(_daily_combat_config.get("heal_amount", 50))

    # ==================== 每日挑战：题库规则 ====================
    DAILY_CHALLENGE_SOURCE_TAGS: list[str] = _normalize_str_list(
        _daily_words_config.get("source_tags"),
        DEFAULT_DAILY_CHALLENGE_CONFIG["words"]["source_tags"],
    )
    DAILY_CHALLENGE_TAG_WEIGHTS: list[dict[str, object]] = _normalize_daily_tag_weights(
        _daily_words_config.get("tag_weights")
    )


settings = Settings()
