import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import create_engine

from app.db.daily_challenge import create_daily_run
from app.db.daily_challenge import _build_daily_prewarm_positions
from app.db.daily_challenge import _sanitize_question_content
from app.db.daily_challenge import get_daily_challenge_window
from app.db.daily_challenge import get_daily_leaderboard
from app.models.daily_challenge import DailyChallengeDay
from app.models.daily_challenge import DailyChallengeRun
from app.models.daily_challenge import DailyChallengeRunStatus
from app.models.question import Question
from app.models.user import User


class DailyChallengeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                DailyChallengeDay.__table__,
                DailyChallengeRun.__table__,
            ],
        )

        with Session(self.engine) as session:
            alice = User(username="alice", nickname="Alice", password_hash="hash")
            bob = User(username="bob", nickname="Bob", password_hash="hash")
            carol = User(username="carol", nickname="Carol", password_hash="hash")
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

            self.day = DailyChallengeDay(
                day_key="2026-04-06",
                opens_at=datetime(2026, 4, 5, 22, 0, tzinfo=timezone.utc),
                closes_at=datetime(2026, 4, 6, 22, 0, tzinfo=timezone.utc),
                source_tags=["zk", "gk", "cet4", "cet6", "ky"],
                config_snapshot={},
                created_at=datetime.now(timezone.utc),
            )
            session.add(self.day)
            session.commit()
            session.refresh(self.day)
            self.day_id = self.day.id

    def test_daily_window_resets_at_six_am_shanghai_time(self):
        before_reset = datetime(2026, 4, 5, 21, 59, tzinfo=timezone.utc)
        after_reset = datetime(2026, 4, 5, 22, 0, tzinfo=timezone.utc)

        before_key, _, _ = get_daily_challenge_window(before_reset)
        after_key, _, _ = get_daily_challenge_window(after_reset)

        self.assertEqual(before_key, "2026-04-05")
        self.assertEqual(after_key, "2026-04-06")

    def test_create_daily_run_enforces_one_run_per_user_per_day(self):
        with Session(self.engine) as session:
            first = create_daily_run(session, session.get(DailyChallengeDay, self.day_id), self.alice_id)
            second = create_daily_run(session, session.get(DailyChallengeDay, self.day_id), self.alice_id)

            self.assertEqual(first.id, second.id)

    def test_prewarm_positions_follow_shared_future_path(self):
        positions = _build_daily_prewarm_positions(floor=1, question_index=1, enemy_hp=30, count=3)
        self.assertEqual(positions, [(1, 2), (1, 3), (2, 1)])

    def test_daily_leaderboard_sorts_by_floor_then_first_reached_time(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            runs = [
                DailyChallengeRun(
                    day_id=self.day_id,
                    user_id=self.alice_id,
                    status=DailyChallengeRunStatus.DEAD,
                    current_floor=8,
                    current_question_index=1,
                    current_hp=0,
                    current_enemy_hp=20,
                    best_floor=8,
                    best_floor_reached_at=now + timedelta(minutes=2),
                    started_at=now,
                    ended_at=now + timedelta(minutes=5),
                ),
                DailyChallengeRun(
                    day_id=self.day_id,
                    user_id=self.bob_id,
                    status=DailyChallengeRunStatus.IN_PROGRESS,
                    current_floor=8,
                    current_question_index=2,
                    current_hp=90,
                    current_enemy_hp=10,
                    best_floor=8,
                    best_floor_reached_at=now + timedelta(minutes=1),
                    started_at=now + timedelta(seconds=10),
                ),
                DailyChallengeRun(
                    day_id=self.day_id,
                    user_id=self.carol_id,
                    status=DailyChallengeRunStatus.DEAD,
                    current_floor=7,
                    current_question_index=1,
                    current_hp=0,
                    current_enemy_hp=30,
                    best_floor=7,
                    best_floor_reached_at=now,
                    started_at=now,
                    ended_at=now + timedelta(minutes=4),
                ),
            ]
            for run in runs:
                session.add(run)
            session.commit()

            entries, current_user_entry = get_daily_leaderboard(session, self.day_id, self.alice_id, 10)

            self.assertEqual([entry.username for entry in entries], ["bob", "alice", "carol"])
            self.assertEqual(current_user_entry.username, "alice")
            self.assertEqual(current_user_entry.rank, 2)

    def test_sanitize_question_content_keeps_client_side_judging_fields(self):
        context_question = Question(
            type="context_guess",
            content={
                "target_word": "ninety",
                "story": "My grandma turned ninety.",
                "story_target_forms": ["ninety"],
                "options": {"A": "九十", "B": "九十岁", "C": "九十次", "D": "九十年"},
                "correct_option": "B",
                "explanation": "这里描述年龄，所以应理解为九十岁。",
            },
        )
        cloze_question = Question(
            type="cloze_test",
            content={
                "cloze_text": "He ____[1]____ home.",
                "shuffled_options": ["went"],
                "correct_sequence": ["went"],
                "chinese_translation": "他回家了。",
            },
        )

        context_payload = _sanitize_question_content(context_question)
        cloze_payload = _sanitize_question_content(cloze_question)

        self.assertEqual(context_payload["correct_option"], "B")
        self.assertEqual(context_payload["explanation"], "这里描述年龄，所以应理解为九十岁。")
        self.assertEqual(cloze_payload["correct_sequence"], ["went"])
        self.assertEqual(cloze_payload["chinese_translation"], "他回家了。")


if __name__ == "__main__":
    unittest.main()
