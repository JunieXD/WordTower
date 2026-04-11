from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder

from app.api.api_responses import (
    bad_request_response,
    conflict_response,
    forbidden_response,
    not_found_response,
    success_response,
)
from app.api.dependencies import get_current_user
from app.db.database import SessionDep
from app.db.social import (
    accept_friend_request,
    are_friends,
    create_friend_message,
    delete_friend,
    get_conversation_messages,
    get_last_message_between_users,
    get_relation_between_users,
    get_total_unread_count,
    get_unread_count_from_friend,
    get_users_by_ids,
    list_accepted_friend_links,
    list_incoming_friend_requests,
    mark_messages_read,
    reject_friend_request,
    search_users,
    send_friend_request,
    serialize_message,
    serialize_message_preview,
)
from app.db.social_presence import get_presence_map
from app.models.social import (
    FriendConversationRead,
    FriendMessageCreate,
    FriendMessagesPage,
    FriendRequestCreate,
    FriendRequestRead,
    SocialChatRead,
    SocialSearchUser,
    SocialUserSummary,
    UnreadSummary,
)
from app.models.user import User
from app.models.user_user_link import FriendStatus
from app.services.progression import get_level_from_exp
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/social", tags=["social"])
logger = get_logger(__name__)


def build_social_user(
    user: User,
    social_status: str = "offline",
    last_online_at: datetime | None = None,
) -> SocialUserSummary:
    return SocialUserSummary(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        exp=user.exp,
        level=get_level_from_exp(user.exp),
        max_floor=user.max_floor,
        social_status=social_status,
        last_online_at=last_online_at,
    )


def build_relation_status(current_user: User, relation) -> tuple[str, int | None]:
    if relation is None:
        return "none", None
    if relation.status == FriendStatus.ACCEPTED:
        return "accepted", relation.id
    if relation.status == FriendStatus.PENDING:
        if relation.user_id == current_user.id:
            return "outgoing_pending", relation.id
        if relation.friend_id == current_user.id:
            return "incoming_pending", relation.id
    return "none", None


@router.get("/friends")
async def get_friends(session: SessionDep, current_user: User = Depends(get_current_user)):
    relations = list_accepted_friend_links(session, current_user)
    friend_ids = [
        relation.friend_id if relation.user_id == current_user.id else relation.user_id
        for relation in relations
    ]
    friends = get_users_by_ids(session, friend_ids)
    friend_by_id = {friend.id: friend for friend in friends}
    presence_map = await get_presence_map(friends)

    items: list[FriendConversationRead] = []
    for relation in relations:
        friend_id = relation.friend_id if relation.user_id == current_user.id else relation.user_id
        friend = friend_by_id.get(friend_id)
        if friend is None:
            continue
        presence = presence_map.get(friend.id)
        last_message = get_last_message_between_users(session, current_user.id, friend.id)
        unread_count = get_unread_count_from_friend(session, current_user.id, friend.id)
        items.append(
            FriendConversationRead(
                relation_id=relation.id,
                friend=build_social_user(
                    friend,
                    social_status=presence.social_status if presence else "offline",
                    last_online_at=presence.last_online_at if presence else friend.last_active_at,
                ),
                unread_count=unread_count,
                last_message=serialize_message_preview(last_message),
            )
        )

    status_priority = {"combat": 0, "online": 1, "offline": 2}

    def sort_key(item: FriendConversationRead):
        last_message_at = item.last_message.created_at if item.last_message else None
        return (
            0 if last_message_at else 1,
            -(last_message_at.timestamp()) if last_message_at else 0,
            status_priority.get(item.friend.social_status, 9),
            (item.friend.nickname or item.friend.username).lower(),
        )

    items.sort(key=sort_key)
    logger.info("获取好友列表：用户ID=%s 数量=%s", current_user.id, len(items))
    return success_response(data=jsonable_encoder(items))


@router.get("/requests")
async def get_requests(session: SessionDep, current_user: User = Depends(get_current_user)):
    relations = list_incoming_friend_requests(session, current_user)
    requester_ids = [relation.user_id for relation in relations]
    requesters = get_users_by_ids(session, requester_ids)
    requester_by_id = {requester.id: requester for requester in requesters}
    presence_map = await get_presence_map(requesters)

    items: list[FriendRequestRead] = []
    for relation in relations:
        requester = requester_by_id.get(relation.user_id)
        if requester is None:
            continue
        presence = presence_map.get(requester.id)
        items.append(
            FriendRequestRead(
                request_id=relation.id,
                created_at=relation.created_at,
                requester=build_social_user(
                    requester,
                    social_status=presence.social_status if presence else "offline",
                    last_online_at=presence.last_online_at if presence else requester.last_active_at,
                ),
            )
        )

    logger.info("获取好友申请：用户ID=%s 数量=%s", current_user.id, len(items))
    return success_response(data=jsonable_encoder(items))


@router.get("/search")
async def search_social_users(
    session: SessionDep,
    q: str = Query("", min_length=0, max_length=50),
    current_user: User = Depends(get_current_user),
):
    query = q.strip()
    if not query:
        return success_response(data=[])

    users = search_users(session, current_user, query)
    presence_map = await get_presence_map(users)
    items: list[SocialSearchUser] = []
    for user in users:
        relation = get_relation_between_users(session, current_user.id, user.id)
        relation_status, request_id = build_relation_status(current_user, relation)
        presence = presence_map.get(user.id)
        items.append(
            SocialSearchUser(
                user=build_social_user(
                    user,
                    social_status=presence.social_status if presence else "offline",
                    last_online_at=presence.last_online_at if presence else user.last_active_at,
                ),
                relation_status=relation_status,
                request_id=request_id,
            )
        )

    logger.info("搜索社交用户：用户ID=%s 关键词=%s 数量=%s", current_user.id, query, len(items))
    return success_response(data=jsonable_encoder(items))


@router.post("/requests")
async def create_friend_request(
    request_in: FriendRequestCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    relation, error = send_friend_request(session, current_user, request_in.user_id)
    if error:
        if error == "用户不存在":
            return not_found_response(message=error)
        if error == "不能添加自己为好友":
            return bad_request_response(message=error)
        return conflict_response(message=error)

    logger.info(
        "发送好友申请：用户ID=%s 目标用户ID=%s 申请ID=%s",
        current_user.id,
        request_in.user_id,
        relation.id if relation else None,
    )
    return success_response(
        data=jsonable_encoder({"request_id": relation.id if relation else None}),
        message="好友申请已发送",
    )


@router.post("/requests/{request_id}/accept")
async def accept_request(
    request_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    relation, error = accept_friend_request(session, current_user, request_id)
    if error:
        if error == "好友申请不存在":
            return not_found_response(message=error)
        return forbidden_response(message=error)

    logger.info("同意好友申请：用户ID=%s 申请ID=%s", current_user.id, relation.id if relation else request_id)
    return success_response(message="已同意好友申请")


@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    relation, error = reject_friend_request(session, current_user, request_id)
    if error:
        if error == "好友申请不存在":
            return not_found_response(message=error)
        return forbidden_response(message=error)

    logger.info("拒绝好友申请：用户ID=%s 申请ID=%s", current_user.id, relation.id if relation else request_id)
    return success_response(message="已拒绝好友申请")


@router.delete("/friends/{friend_id}")
async def remove_friend(
    friend_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    relation, error = delete_friend(session, current_user, friend_id)
    if error:
        return not_found_response(message=error)

    logger.info("删除好友：用户ID=%s 好友ID=%s 关系ID=%s", current_user.id, friend_id, relation.id if relation else None)
    return success_response(message="已删除好友")


@router.get("/chats/{friend_id}")
async def get_chat(
    friend_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    if not are_friends(session, current_user.id, friend_id):
        return forbidden_response(message="只有好友才能查看聊天记录")

    friend = session.get(User, friend_id)
    if friend is None:
        return not_found_response(message="好友不存在")

    presence_map = await get_presence_map([friend])
    presence = presence_map.get(friend.id)
    messages, has_more = get_conversation_messages(session, current_user.id, friend_id)
    data = SocialChatRead(
        friend=build_social_user(
            friend,
            social_status=presence.social_status if presence else "offline",
            last_online_at=presence.last_online_at if presence else friend.last_active_at,
        ),
        messages=[serialize_message(message, current_user.id) for message in messages],
        has_more=has_more,
    )
    logger.info("获取聊天初始化数据：用户ID=%s 好友ID=%s 消息数=%s", current_user.id, friend_id, len(messages))
    return success_response(data=jsonable_encoder(data))


@router.get("/chats/{friend_id}/messages")
async def get_chat_messages(
    session: SessionDep,
    friend_id: int,
    before: datetime | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    if not are_friends(session, current_user.id, friend_id):
        return forbidden_response(message="只有好友才能查看聊天记录")

    messages, has_more = get_conversation_messages(session, current_user.id, friend_id, before, limit)
    data = FriendMessagesPage(
        messages=[serialize_message(message, current_user.id) for message in messages],
        has_more=has_more,
    )
    logger.info("分页获取聊天记录：用户ID=%s 好友ID=%s 消息数=%s", current_user.id, friend_id, len(messages))
    return success_response(data=jsonable_encoder(data))


@router.post("/chats/{friend_id}/messages")
async def send_message(
    friend_id: int,
    message_in: FriendMessageCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    content = message_in.content.strip()
    if not content:
        return bad_request_response(message="消息内容不能为空")
    if not are_friends(session, current_user.id, friend_id):
        return forbidden_response(message="只有好友才能发送消息")

    friend = session.get(User, friend_id)
    if friend is None:
        return not_found_response(message="好友不存在")

    message = create_friend_message(session, current_user.id, friend_id, content)
    logger.info("发送聊天消息：用户ID=%s 好友ID=%s 消息ID=%s", current_user.id, friend_id, message.id)
    return success_response(data=jsonable_encoder(serialize_message(message, current_user.id)), message="发送成功")


@router.post("/chats/{friend_id}/read")
async def read_messages(
    friend_id: int,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
):
    if not are_friends(session, current_user.id, friend_id):
        return forbidden_response(message="只有好友才能标记已读")

    count = mark_messages_read(session, current_user.id, friend_id)
    logger.info("标记聊天已读：用户ID=%s 好友ID=%s 数量=%s", current_user.id, friend_id, count)
    return success_response(data=jsonable_encoder({"read_count": count}), message="已读状态已更新")


@router.get("/unread-summary")
async def get_unread_summary(session: SessionDep, current_user: User = Depends(get_current_user)):
    total = get_total_unread_count(session, current_user.id)
    data = UnreadSummary(total=total)
    logger.info("获取未读汇总：用户ID=%s 未读=%s", current_user.id, total)
    return success_response(data=jsonable_encoder(data))
