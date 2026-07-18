import unittest

from sqlalchemy import JSON
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.user import user_question_answer
from app.models.question import Question
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord


class UserQuestionRecordTests(unittest.TestCase):
    def setUp(self):
        # SQLite 测试环境不支持 PostgreSQL 的 JSONB，这里仅对测试表做兼容覆盖。
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
                Question.__table__,
                UserQuestionRecord.__table__,
            ],
        )

    def test_only_first_answer_is_recorded_for_same_user_and_question(self):
        with Session(self.engine) as session:
            user = User(username="alice", nickname="Alice", password_hash="hash")
            question = Question(
                type="context_guess",
                content={
                    "target_word": "canal",
                    "story": "We walked along a wide canal.",
                    "options": {"A": "管", "B": "沟渠", "C": "开运河", "D": "水道"},
                    "correct_option": "D",
                    "explanation": "这里表示水道。",
                },
            )
            session.add(user)
            session.add(question)
            session.commit()
            session.refresh(user)
            session.refresh(question)

            first = user_question_answer(
                session,
                user,
                question,
                False,
                {"selected_option": "A", "selected_text": "管"},
            )
            second = user_question_answer(
                session,
                user,
                question,
                True,
                {"selected_option": "D", "selected_text": "水道"},
            )

            records = session.exec(select(UserQuestionRecord)).all()

            self.assertEqual(len(records), 1)
            self.assertEqual(first.id, second.id)
            self.assertFalse(records[0].correct)
            self.assertEqual(records[0].answer_detail["selected_option"], "A")


if __name__ == "__main__":
    unittest.main()
