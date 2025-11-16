import os


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
    UPGRADE_HP_HP: int = os.getenv("UPGRADE_HP_HP", 1)
    # 升级攻击力数值
    UPGRADE_ATTACK_ATTACK: int = os.getenv("UPGRADE_ATTACK_ATTACK", 1)
    # 升级暴击率数值
    UPGRADE_CRIT_RATE_CRIT_RATE: float = os.getenv("UPGRADE_CRIT_RATE_CRIT_RATE", 0.01)

settings = Settings()
