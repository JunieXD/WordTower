from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from app.db.redis import get_redis
from app.services.traffic import user_action
from app.api.api_responses import success_response, conflict_response, internal_server_error_response, not_found_response
from app.db.database import SessionDep
from app.db.challenge import (
    get_current_floor,
    get_last_hp,
    current_challenge,
    new_challenge,
    end_challenge,
    get_last_failed_tower_run_rewards,
)
from app.api.dependencies import get_current_user
from app.models.user import User
from app.utils.config import get_enemy_hp, get_enemy_attack
from app.db.level import new_level
from app.models.challenge import EndChallenge
from app.db.user import update_user_max_floor
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/combat", tags=["combat"])
logger = get_logger(__name__)

@router.post("/start")
@user_action("combat-start")
def start_combat(request: Request, session: SessionDep, user_in: User = Depends(get_current_user), redis: Redis = Depends(get_redis)):
    challenge = current_challenge(session, user_in)
    if not challenge:
        challenge = new_challenge(session, user_in, new_level(session, 1))
        if not challenge:
            logger.error("开始战斗失败：创建挑战失败，用户ID=%s", user_in.id)
            return internal_server_error_response(message="战斗开始失败")
    last_hp = get_last_hp(session, user_in)
    player_hp = last_hp if (last_hp is not None and last_hp > 0) else user_in.max_hp
    current_floor = get_current_floor(session, user_in)
    enemy_max_hp = get_enemy_hp(current_floor)
    combat_data = {
        "level_id": challenge.level_id,
        "current_floor": current_floor,
        "player_hp": player_hp,
        "player_max_hp": user_in.max_hp,
        "player_attack": user_in.attack,
        "enemy_max_hp": enemy_max_hp,
        "enemy_hp": enemy_max_hp,
        "enemy_attack": get_enemy_attack(current_floor)
    }
    logger.info("开始战斗：用户ID=%s 关卡ID=%s 层数=%s 玩家血量=%s", user_in.id, challenge.level_id, current_floor, player_hp)
    return success_response(data=combat_data)

@router.post("/end")
@user_action("combat-end")
def end_combat(request: Request, session: SessionDep, end_challenge_in: EndChallenge, user_in: User = Depends(get_current_user), redis: Redis = Depends(get_redis)):
    challenge = current_challenge(session, user_in)
    if not challenge:
        logger.warning("结束战斗失败：无进行中的挑战，用户ID=%s", user_in.id)
        return conflict_response(message="没有进行中的战斗")
    current_floor = get_current_floor(session, user_in)
    update_user_max_floor(session, user_in, current_floor)
    challenge = end_challenge(session, user_in, end_challenge_in.end_hp, end_challenge_in.exp_gained, end_challenge_in.coins_gained)
    if not challenge:
        logger.error("结束战斗失败：结算挑战失败，用户ID=%s 层数=%s", user_in.id, current_floor)
        return internal_server_error_response(message="战斗结束失败")
    if end_challenge_in.next:
        challenge = new_challenge(session, user_in, new_level(session, current_floor + 1))
        if not challenge:
            logger.error("结束战斗失败：创建下一层挑战失败，用户ID=%s 下一层=%s", user_in.id, current_floor + 1)
            return internal_server_error_response(message="战斗开始失败")

    logger.info(
        "结束战斗：用户ID=%s 层数=%s 是否继续=%s 结束血量=%s 获得经验=%s 获得金币=%s",
        user_in.id,
        current_floor,
        end_challenge_in.next,
        end_challenge_in.end_hp,
        end_challenge_in.exp_gained,
        end_challenge_in.coins_gained,
    )
    
    return success_response(message="战斗结束", data={"level_id": challenge.level_id})

@router.get("/checkout")
def get_tower_rewards(session: SessionDep, user_in: User = Depends(get_current_user)):
    """获取用户最近一次以失败结束的连续闯塔累计获得的经验和金币。"""

    result = get_last_failed_tower_run_rewards(session, user_in)
    if result is None:
        logger.warning("获取闯塔奖励失败：无失败记录，用户ID=%s", user_in.id)
        return not_found_response(message="没有以失败结束的连续闯塔记录")

    logger.info("获取闯塔奖励：用户ID=%s 经验=%s 金币=%s", user_in.id, result.get("exp"), result.get("coins"))
    return success_response(message="获取最近一次连续闯塔奖励成功", data=result)
