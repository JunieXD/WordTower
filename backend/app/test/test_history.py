import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.history import get_history_run_detail, list_history_runs
from app.models.challenge import Challenge, ChallengeStatus
from app.models.daily_challenge import (
    DailyChallengeAnswer,
    DailyChallengeDay,
    DailyChallengeFloorQuestion,
    DailyChallengeRun,
    DailyChallengeRunStatus,
)
from app.models.level import Level
from app.models.level_question_link import LevelQuestionLink
from app.models.question import Question
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord


class HistoryTests(unittest.TestCase):
    def setUp(self):
        # SQLite 测试库不支持 PostgreSQL 的 JSONB，这里仅对测试表做兼容覆盖。
        Question.__table__.c.content.type = JSON()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                Level.__table__,
                Question.__table__,
                Challenge.__table__,
                LevelQuestionLink.__table__,
                UserQuestionRecord.__table__,
                DailyChallengeDay.__table__,
                DailyChallengeRun.__table__,
                DailyChallengeFloorQuestion.__table__,
                DailyChallengeAnswer.__table__,
            ],
        )

        now = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)

        with Session(self.engine) as session:
            user = User(username="alice", nickname="Alice", password_hash="hash")
            session.add(user)
            session.commit()
            session.refresh(user)
            self.user_id = user.id

            level = Level(floor=1)
            session.add(level)
            session.commit()
            session.refresh(level)

            tower_question = Question(
                type="context_guess",
                content={
                    "target_word": "canal",
                    "story": "We walked along a wide canal.",
                    "options": {"A": "管", "B": "沟渠", "C": "开运河", "D": "水道"},
                    "correct_option": "D",
                    "explanation": "这里表示水道。",
                },
            )
            session.add(tower_question)
            session.commit()
            session.refresh(tower_question)

            challenge = Challenge(
                user_id=user.id,
                level_id=level.id,
                start_time=now,
                end_time=now + timedelta(minutes=2),
                end_hp=80,
                status=ChallengeStatus.COMPLETED,
                exp_gained=12,
                coins_gained=6,
            )
            session.add(challenge)
            session.commit()
            session.refresh(challenge)
            self.challenge_id = challenge.id

            session.add(
                LevelQuestionLink(level_id=level.id, question_id=tower_question.id, order_index=1)
            )
            session.add(
                UserQuestionRecord(
                    user_id=user.id,
                    question_id=tower_question.id,
                    time=now + timedelta(seconds=30),
                    correct=True,
                    answer_detail={"selected_option": "D"},
                )
            )

            day = DailyChallengeDay(
                day_key="2026-04-07",
                opens_at=now + timedelta(hours=12),
                closes_at=now + timedelta(hours=36),
                source_tags=["zk", "gk", "cet4", "cet6", "ky"],
                config_snapshot={},
                created_at=now + timedelta(hours=12),
            )
            session.add(day)
            session.commit()
            session.refresh(day)

            daily_question = Question(
                type="context_guess",
                content={
                    "target_word": "village",
                    "story": "My uncle took me to a small village.",
                    "options": {"A": "村庄", "B": "村民", "C": "乡村的", "D": "搬到村里"},
                    "correct_option": "A",
                    "explanation": "这里表示地点名词，指村庄。",
                },
            )
            session.add(daily_question)
            session.commit()
            session.refresh(daily_question)

            daily_run = DailyChallengeRun(
                day_id=day.id,
                user_id=user.id,
                status=DailyChallengeRunStatus.DEAD,
                current_floor=1,
                current_question_index=1,
                current_hp=0,
                current_enemy_hp=20,
                best_floor=1,
                best_floor_reached_at=now + timedelta(hours=13),
                started_at=now + timedelta(hours=13),
                ended_at=now + timedelta(hours=13, minutes=3),
            )
            session.add(daily_run)
            session.commit()
            session.refresh(daily_run)
            self.daily_run_id = daily_run.id

            session.add(
                DailyChallengeFloorQuestion(
                    day_id=day.id,
                    floor=1,
                    question_index=1,
                    question_id=daily_question.id,
                    question_type="context_guess",
                    word_ids=[],
                    created_at=now + timedelta(hours=13),
                )
            )
            session.add(
                DailyChallengeAnswer(
                    run_id=daily_run.id,
                    floor=1,
                    question_index=1,
                    question_id=daily_question.id,
                    answer_detail={"selected_option": "B"},
                    is_correct=False,
                    answered_at=now + timedelta(hours=13, minutes=1),
                )
            )
            session.commit()

    def test_history_runs_include_daily_challenge_entries(self):
        with Session(self.engine) as session:
            user = session.get(User, self.user_id)
            runs = list_history_runs(session, user)

            self.assertEqual([run.mode for run in runs], ["daily_challenge", "tower"])
            self.assertEqual(runs[0].run_ref, f"daily-{self.daily_run_id}")
            self.assertEqual(runs[1].run_ref, f"tower-{self.challenge_id}")

    def test_history_runs_sorts_mixed_naive_and_aware_datetimes(self):
        with Session(self.engine) as session:
            challenge = session.get(Challenge, self.challenge_id)
            challenge.start_time = challenge.start_time.replace(tzinfo=None)
            challenge.end_time = challenge.end_time.replace(tzinfo=None)
            session.add(challenge)
            session.commit()

            user = session.get(User, self.user_id)
            runs = list_history_runs(session, user)

            self.assertEqual(runs[0].mode, "daily_challenge")
            self.assertEqual(runs[1].mode, "tower")

    def test_history_detail_supports_daily_challenge_run_ref(self):
        with Session(self.engine) as session:
            user = session.get(User, self.user_id)
            detail = get_history_run_detail(session, user, f"daily-{self.daily_run_id}")

            self.assertIsNotNone(detail)
            self.assertEqual(detail.run.mode, "daily_challenge")
            self.assertEqual(detail.run.day_key, "2026-04-07")
            self.assertEqual(len(detail.questions), 1)
            self.assertEqual(detail.questions[0].question_index, 1)
            self.assertFalse(detail.questions[0].first_answer.correct)

    def test_history_detail_keeps_numeric_tower_run_ref_compatible(self):
        with Session(self.engine) as session:
            user = session.get(User, self.user_id)
            detail = get_history_run_detail(session, user, str(self.challenge_id))

            self.assertIsNotNone(detail)
            self.assertEqual(detail.run.mode, "tower")
            self.assertEqual(detail.run.run_ref, f"tower-{self.challenge_id}")


if __name__ == "__main__":
    unittest.main()
