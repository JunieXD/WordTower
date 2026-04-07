import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.social import (
    accept_friend_request,
    are_friends,
    create_friend_message,
    get_total_unread_count,
    get_unread_count_from_friend,
    mark_messages_read,
    search_users,
    send_friend_request,
)
from app.db.social_presence import (
    _last_active_key,
    _last_combat_active_key,
    _last_persist_key,
    get_presence_map,
    touch_user_presence,
)
from app.models.friend_message import FriendMessage
from app.models.user import User
from app.models.user_user_link import UserUserLink


class SocialDbTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[User.__table__, UserUserLink.__table__, FriendMessage.__table__],
        )

        with Session(self.engine) as session:
            alice = User(username="alice", nickname="塔塔", password_hash="hash")
            bob = User(username="bob", nickname="学习搭子", password_hash="hash")
            carol = User(username="carol", nickname="夜行者", password_hash="hash")
            session.add(alice)
            session.add(bob)
            session.add(carol)
            session.commit()
            session.refresh(alice)
            session.refresh(bob)
            session.refresh(carol)
            self.alice_id = alice.id
            self.bob_id = bob.id
            self.carol_id = carol.id

    def test_search_matches_username_and_nickname_and_excludes_self(self):
        with Session(self.engine) as session:
            alice = session.get(User, self.alice_id)

            username_results = search_users(session, alice, "bo")
            nickname_results = search_users(session, alice, "搭子")

            self.assertEqual([user.username for user in username_results], ["bob"])
            self.assertEqual([user.username for user in nickname_results], ["bob"])
            self.assertNotIn("alice", [user.username for user in username_results])

    def test_friend_request_flow_blocks_duplicates_and_cross_requests(self):
        with Session(self.engine) as session:
            alice = session.get(User, self.alice_id)
            bob = session.get(User, self.bob_id)

            relation, error = send_friend_request(session, alice, bob.id)
            self.assertIsNone(error)
            self.assertIsNotNone(relation)

            _, duplicate_error = send_friend_request(session, alice, bob.id)
            self.assertEqual(duplicate_error, "好友申请已发送")

            _, cross_error = send_friend_request(session, bob, alice.id)
            self.assertEqual(cross_error, "对方已向你发送好友申请")

            accepted_relation, accept_error = accept_friend_request(session, bob, relation.id)
            self.assertIsNone(accept_error)
            self.assertIsNotNone(accepted_relation)
            self.assertTrue(are_friends(session, alice.id, bob.id))

            _, self_error = send_friend_request(session, alice, alice.id)
            self.assertEqual(self_error, "不能添加自己为好友")

    def test_unread_counts_and_read_marking_work(self):
        with Session(self.engine) as session:
            alice = session.get(User, self.alice_id)
            bob = session.get(User, self.bob_id)

            relation, _ = send_friend_request(session, alice, bob.id)
            accept_friend_request(session, bob, relation.id)

            create_friend_message(session, bob.id, alice.id, "第一条")
            create_friend_message(session, bob.id, alice.id, "第二条")
            create_friend_message(session, alice.id, bob.id, "收到啦")

            self.assertEqual(get_unread_count_from_friend(session, alice.id, bob.id), 2)
            self.assertEqual(get_total_unread_count(session, alice.id), 2)

            read_count = mark_messages_read(session, alice.id, bob.id)
            self.assertEqual(read_count, 2)
            self.assertEqual(get_unread_count_from_friend(session, alice.id, bob.id), 0)
            self.assertEqual(get_total_unread_count(session, alice.id), 0)


class FakePipeline:
    def __init__(self, storage: dict[str, str]):
        self.storage = storage
        self.commands: list[tuple[str, str, int, str]] = []

    def setex(self, key: str, ttl: int, value: str):
        self.commands.append(("setex", key, ttl, value))
        return self

    async def execute(self):
        for _, key, _, value in self.commands:
            self.storage[key] = value


class FakeRedis:
    def __init__(self, storage: dict[str, str]):
        self.storage = storage
        self.pipeline_instance = FakePipeline(storage)

    def pipeline(self):
        return self.pipeline_instance

    async def get(self, key: str):
        return self.storage.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.storage[key] = value

    async def mget(self, keys: list[str]):
        return [self.storage.get(key) for key in keys]

    async def close(self):
        return None


class SocialPresenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_touch_user_presence_marks_question_requests_as_combat_activity(self):
        storage = {
            _last_persist_key("alice"): datetime.now(timezone.utc).isoformat(),
        }

        with patch("app.db.social_presence.Redis", side_effect=lambda *args, **kwargs: FakeRedis(storage)):
            await touch_user_presence("alice", "/api/question/get")

        self.assertIn(_last_active_key("alice"), storage)
        self.assertIn(_last_combat_active_key("alice"), storage)

    async def test_get_presence_map_distinguishes_combat_online_and_offline(self):
        now = datetime.now(timezone.utc)
        storage = {
            _last_combat_active_key("bob"): now.isoformat(),
        }

        alice = User(id=1, username="alice", password_hash="hash", last_active_at=now - timedelta(seconds=20))
        bob = User(id=2, username="bob", password_hash="hash", last_active_at=now - timedelta(minutes=10))
        carol = User(id=3, username="carol", password_hash="hash", last_active_at=now - timedelta(minutes=10))

        with patch("app.db.social_presence.Redis", side_effect=lambda *args, **kwargs: FakeRedis(storage)):
          presence_map = await get_presence_map([alice, bob, carol])

        self.assertEqual(presence_map[alice.id].social_status, "online")
        self.assertEqual(presence_map[bob.id].social_status, "combat")
        self.assertEqual(presence_map[carol.id].social_status, "offline")


if __name__ == "__main__":
    unittest.main()
