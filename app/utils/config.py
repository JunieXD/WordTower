import os
import random

def get_question_type_weights(floor: int) -> list[int]:
    """根据楼层返回题目类型权重"""
    return [100 - min(floor // 10 * 2, 20), min(floor // 10, 10), min(floor // 10, 10)]
    # return [0, 100, 0]

def get_enemy_hp(floor: int) -> int:
    return int(floor * random.random()) + 10

def get_enemy_attack(floor: int) -> int:
    return int(floor * random.random()) + 10

class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:123456@localhost:5432/wordtower"
    )

    SECRET_KEY: str = os.getenv("SECRET_KEY", "wordtower")

    # 升级血量所需金币
    UPGRADE_HP_COINS: int = os.getenv("UPGRADE_HP_COINS", 100)
    # 升级攻击力所需金币
    UPGRADE_ATTACK_COINS: int = os.getenv("UPGRADE_ATTACK_COINS", 100)
    # 升级暴击率所需金币
    UPGRADE_CRIT_RATE_COINS: int = os.getenv("UPGRADE_CRIT_RATE_COINS", 100)
    # 升级血量数值
    UPGRADE_HP_VALUE: int = os.getenv("UPGRADE_HP_VALUE", 1)
    # 升级攻击力数值
    UPGRADE_ATTACK_VALUE: int = os.getenv("UPGRADE_ATTACK_VALUE", 1)
    # 升级暴击率数值
    UPGRADE_CRIT_RATE_VALUE: float = os.getenv("UPGRADE_CRIT_RATE_VALUE", 0.01)

    # 火山方舟 API Key
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "")
    # 火山方舟 API Base URL
    ARK_API_BASE_URL: str = os.getenv("ARK_API_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    # 火山方舟 API Model ID
    ARK_API_MODEL_ID: str = os.getenv("ARK_API_MODEL_ID", "doubao-seed-1-6-flash-250828")

    # 题目类型
    QUESTION_TYPES = ["context_guess", "cloze_test", "keyword_translation"]

settings = Settings()
