from fastapi import APIRouter, Depends
from app.api.api_responses import success_response
from app.db.database import SessionDep
from app.db.challenge import get_current_floor, get_current_hp
from app.api.dependencies import get_current_user
from app.models.user import User
from app.utils.config import get_enemy_hp, get_enemy_attack

router = APIRouter(prefix="/api/combat", tags=["combat"])

@router.get("/combat_info")
async def init_combat_info(session: SessionDep, user_in: User = Depends(get_current_user)):
    current_floor = get_current_floor(session, user_in) or 1
    player_hp = get_current_hp(session, user_in) or user_in.max_hp
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