from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models.friend_message import FriendMessage
from app.models.social import FriendMessagePreview, FriendMessageRead
from app.models.user import User
from app.models.user_user_link import FriendStatus, UserUserLink


def get_relation_between_users(session: Session, user_id: int, other_user_id: int) -> UserUserLink | None:
    statement = (
        select(UserUserLink)
        .where(
            or_(
                (UserUserLink.user_id == user_id) & (UserUserLink.friend_id == other_user_id),
                (UserUserLink.user_id == other_user_id) & (UserUserLink.friend_id == user_id),
            )
        )
        .order_by(UserUserLink.updated_at.desc())
    )
    return session.exec(statement).first()


def search_users(session: Session, current_user: User, query: str, limit: int = 20) -> list[User]:
    query = query.strip()
    if not query:
        return []

    like_pattern = f"%{query}%"
    statement = (
        select(User)
        .where(User.id != current_user.id)
        .where(or_(User.username.ilike(like_pattern), User.nickname.ilike(like_pattern)))
        .order_by(User.nickname.is_(None), User.nickname.asc(), User.username.asc())
        .limit(limit)
    )
    return list(session.exec(statement).all())


def list_incoming_friend_requests(session: Session, current_user: User) -> list[UserUserLink]:
    statement = (
        select(UserUserLink)
        .where(UserUserLink.friend_id == current_user.id)
        .where(UserUserLink.status == FriendStatus.PENDING)
        .order_by(UserUserLink.created_at.desc())
    )
    return list(session.exec(statement).all())


def list_accepted_friend_links(session: Session, current_user: User) -> list[UserUserLink]:
    statement = (
        select(UserUserLink)
        .where(
            or_(UserUserLink.user_id == current_user.id, UserUserLink.friend_id == current_user.id)
        )
        .where(UserUserLink.status == FriendStatus.ACCEPTED)
        .order_by(UserUserLink.updated_at.desc())
    )
    return list(session.exec(statement).all())


def get_users_by_ids(session: Session, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    statement = select(User).where(User.id.in_(user_ids))
    return list(session.exec(statement).all())


def send_friend_request(session: Session, current_user: User, target_user_id: int) -> tuple[UserUserLink | None, str | None]:
    if current_user.id == target_user_id:
        return None, "不能添加自己为好友"

    target_user = session.get(User, target_user_id)
    if target_user is None:
        return None, "用户不存在"

    relation = get_relation_between_users(session, current_user.id, target_user_id)
    if relation is not None:
        if relation.status == FriendStatus.ACCEPTED:
            return None, "你们已经是好友了"
        if relation.status == FriendStatus.PENDING:
            if relation.user_id == current_user.id:
                return None, "好友申请已发送"
            return None, "对方已向你发送好友申请"

        relation.user_id = current_user.id
        relation.friend_id = target_user_id
        relation.status = FriendStatus.PENDING
        relation.created_at = datetime.now(timezone.utc)
        relation.updated_at = relation.created_at
        session.add(relation)
        session.commit()
        session.refresh(relation)
        return relation, None

    relation = UserUserLink(
        user_id=current_user.id,
        friend_id=target_user_id,
        status=FriendStatus.PENDING,
    )
    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation, None


def accept_friend_request(session: Session, current_user: User, request_id: int) -> tuple[UserUserLink | None, str | None]:
    relation = session.get(UserUserLink, request_id)
    if relation is None or relation.status != FriendStatus.PENDING:
        return None, "好友申请不存在"
    if relation.friend_id != current_user.id:
        return None, "无权处理该好友申请"

    relation.status = FriendStatus.ACCEPTED
    relation.updated_at = datetime.now(timezone.utc)
    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation, None


def reject_friend_request(session: Session, current_user: User, request_id: int) -> tuple[UserUserLink | None, str | None]:
    relation = session.get(UserUserLink, request_id)
    if relation is None or relation.status != FriendStatus.PENDING:
        return None, "好友申请不存在"
    if relation.friend_id != current_user.id:
        return None, "无权处理该好友申请"

    relation.status = FriendStatus.REJECTED
    relation.updated_at = datetime.now(timezone.utc)
    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation, None


def delete_friend(session: Session, current_user: User, friend_id: int) -> tuple[UserUserLink | None, str | None]:
    relation = get_relation_between_users(session, current_user.id, friend_id)
    if relation is None or relation.status != FriendStatus.ACCEPTED:
        return None, "好友关系不存在"

    relation.status = FriendStatus.DELETED
    relation.updated_at = datetime.now(timezone.utc)
    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation, None


def are_friends(session: Session, user_id: int, other_user_id: int) -> bool:
    relation = get_relation_between_users(session, user_id, other_user_id)
    return relation is not None and relation.status == FriendStatus.ACCEPTED


def get_last_message_between_users(session: Session, user_id: int, other_user_id: int) -> FriendMessage | None:
    statement = (
        select(FriendMessage)
        .where(
            or_(
                (FriendMessage.sender_id == user_id) & (FriendMessage.recipient_id == other_user_id),
                (FriendMessage.sender_id == other_user_id) & (FriendMessage.recipient_id == user_id),
            )
        )
        .order_by(FriendMessage.created_at.desc())
    )
    return session.exec(statement).first()


def get_unread_count_from_friend(session: Session, current_user_id: int, friend_id: int) -> int:
    statement = (
        select(func.count())
        .select_from(FriendMessage)
        .where(FriendMessage.sender_id == friend_id)
        .where(FriendMessage.recipient_id == current_user_id)
        .where(FriendMessage.read_at.is_(None))
    )
    return int(session.exec(statement).one())


def get_total_unread_count(session: Session, current_user_id: int) -> int:
    statement = (
        select(func.count())
        .select_from(FriendMessage)
        .where(FriendMessage.recipient_id == current_user_id)
        .where(FriendMessage.read_at.is_(None))
    )
    return int(session.exec(statement).one())


def create_friend_message(
    session: Session,
    sender_id: int,
    recipient_id: int,
    content: str,
) -> FriendMessage:
    message = FriendMessage(
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content.strip(),
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def get_conversation_messages(
    session: Session,
    user_id: int,
    friend_id: int,
    before: datetime | None = None,
    limit: int = 30,
) -> tuple[list[FriendMessage], bool]:
    statement = (
        select(FriendMessage)
        .where(
            or_(
                (FriendMessage.sender_id == user_id) & (FriendMessage.recipient_id == friend_id),
                (FriendMessage.sender_id == friend_id) & (FriendMessage.recipient_id == user_id),
            )
        )
        .order_by(FriendMessage.created_at.desc(), FriendMessage.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        statement = statement.where(FriendMessage.created_at < before)

    rows = list(session.exec(statement).all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    rows.reverse()
    return rows, has_more


def mark_messages_read(session: Session, current_user_id: int, friend_id: int) -> int:
    statement = (
        select(FriendMessage)
        .where(FriendMessage.sender_id == friend_id)
        .where(FriendMessage.recipient_id == current_user_id)
        .where(FriendMessage.read_at.is_(None))
    )
    messages = list(session.exec(statement).all())
    if not messages:
        return 0

    now = datetime.now(timezone.utc)
    for message in messages:
        message.read_at = now
        session.add(message)
    session.commit()
    return len(messages)


def serialize_message(message: FriendMessage, current_user_id: int) -> FriendMessageRead:
    return FriendMessageRead(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        content=message.content,
        created_at=message.created_at,
        read_at=message.read_at,
        is_mine=message.sender_id == current_user_id,
    )


def serialize_message_preview(message: FriendMessage | None) -> FriendMessagePreview | None:
    if message is None:
        return None
    return FriendMessagePreview(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        content=message.content,
        created_at=message.created_at,
        read_at=message.read_at,
    )
