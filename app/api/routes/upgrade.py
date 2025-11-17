from fastapi import APIRouter
from app.db.database import SessionDep
from app.api.api_responses import success_response, unprocessable_entity_response
from app.api.dependencies import get_current_user
from app.db.upgrade import user_upgrade_hp, user_upgrade_attack, user_upgrade_crit_rate
from app.models.user import User
from fastapi import Depends
from app.db.database import SessionDep
from app.utils.config import settings


upgrade_hp_coins = settings.UPGRADE_HP_COINS
upgrade_attack_coins = settings.UPGRADE_ATTACK_COINS
upgrade_crit_rate_coins = settings.UPGRADE_CRIT_RATE_COINS
upgrade_hp_value = settings.UPGRADE_HP_VALUE
upgrade_attack_value = settings.UPGRADE_ATTACK_VALUE
upgrade_crit_rate_value = settings.UPGRADE_CRIT_RATE_VALUE

router = APIRouter(prefix="/api/upgrade", tags=["upgrade"])

@router.get("/get_values", response_model=dict)
async def get_values(session: SessionDep, user: User = Depends(get_current_user)):
    value = {
        "upgrade_hp_coins": upgrade_hp_coins,
        "upgrade_attack_coins": upgrade_attack_coins,
        "upgrade_crit_rate_coins": upgrade_crit_rate_coins,
        "upgrade_hp_value": upgrade_hp_value,
        "upgrade_attack_value": upgrade_attack_value,
        "upgrade_crit_rate_value": upgrade_crit_rate_value
    }
    return success_response(data=value)

@router.post("/max_hp")
async def upgrade_hp(session: SessionDep, user: User = Depends(get_current_user)):
    if user.coins < upgrade_hp_coins:
        return unprocessable_entity_response(message="金币不足")
    user_upgrade_hp(session, user.username, upgrade_hp_coins, upgrade_hp_value)
    return success_response(message="升级成功")

@router.post("/attack")
async def upgrade_attack(session: SessionDep, user: User = Depends(get_current_user)):
    if user.coins < upgrade_attack_coins:
        return unprocessable_entity_response(message="金币不足")
    user_upgrade_attack(session, user.username, upgrade_attack_coins, upgrade_attack_value)
    return success_response(message="升级成功")

@router.post("/crit_rate")
async def upgrade_crit_rate(session: SessionDep, user: User = Depends(get_current_user)):
    if user.coins < upgrade_crit_rate_coins:
        return unprocessable_entity_response(message="金币不足")
    user_upgrade_crit_rate(session, user.username, upgrade_crit_rate_coins, upgrade_crit_rate_value)
    return success_response(message="升级成功")