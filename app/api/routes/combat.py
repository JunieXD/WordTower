from fastapi import APIRouter, Depends
from app.api.api_responses import success_response, conflict_response, internal_server_error_response
from app.db.database import SessionDep
from app.db.challenge import get_current_floor, get_last_hp, current_challenge, new_challenge, end_challenge
from app.api.dependencies import get_current_user
from app.models.user import User
from app.utils.config import get_enemy_hp, get_enemy_attack
from app.db.level import new_level
from app.models.challenge import EndChallenge
from app.db.user import update_user_max_floor

router = APIRouter(prefix="/api/combat", tags=["combat"])

@router.post("/start")
async def start_combat(session: SessionDep, user_in: User = Depends(get_current_user)):
    if not current_challenge(session, user_in):
        challenge = new_challenge(session, user_in, new_level(session, 1))
        if not challenge:
            return internal_server_error_response(message="战斗开始失败")
    last_hp = get_last_hp(session, user_in)
    player_hp = last_hp if (last_hp is not None and last_hp > 0) else user_in.max_hp
    current_floor = get_current_floor(session, user_in)
    enemy_max_hp = get_enemy_hp(current_floor)
    combat_data = {
        "current_floor": current_floor,
        "player_hp": player_hp,
        "player_max_hp": user_in.max_hp,
        "player_attack": user_in.attack,
        "enemy_max_hp": enemy_max_hp,
        "enemy_hp": enemy_max_hp,
        "enemy_attack": get_enemy_attack(current_floor)
    }
    return success_response(data=combat_data)

@router.post("/end")
async def end_combat(session: SessionDep, end_challenge_in: EndChallenge, user_in: User = Depends(get_current_user)):
    challenge = current_challenge(session, user_in)
    if not challenge:
        return conflict_response(message="没有进行中的战斗")
    current_floor = get_current_floor(session, user_in)
    update_user_max_floor(session, user_in, current_floor)
    challenge = end_challenge(session, user_in, end_challenge_in.end_hp, end_challenge_in.exp_gained, end_challenge_in.coins_gained)
    if not challenge:
        return internal_server_error_response(message="战斗结束失败")
    if end_challenge_in.next:
        challenge = new_challenge(session, user_in, new_level(session, current_floor + 1))
        if not challenge:
            return internal_server_error_response(message="战斗开始失败")
    return success_response(message="战斗结束")