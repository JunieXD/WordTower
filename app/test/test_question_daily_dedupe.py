import unittest
from unittest.mock import patch

from app.db.question import _question_queue_day_key
from app.db.question import _question_queue_key
from app.db.question import _question_word_keys_from_type_and_content
from app.db.question import _queue_fp_set_key
from app.db.question import _queue_id_set_key
from app.db.question import _is_word_generation_cooled_down
from app.db.question import _mark_word_generation_cooldown
from app.db.question import _record_word_generation_failure
from app.db.question import _select_fallback_question
from app.db.question import ensure_question_queue_day
from app.db.question import is_same_day_word_duplicate_payload
from app.db.question import mark_question_served_payload
from app.models.question import Question


class _FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.command_stack: list[tuple[str, str, int, str]] = []

    def setex(self, key: str, ttl_seconds: int, value: str):
        self.command_stack.append(("setex", key, ttl_seconds, value))
        return self

    async def execute(self):
        for _, key, _, value in self.command_stack:
            self.redis.values[key] = value


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def setex(self, key: str, ttl_seconds: int, value: str):
        self.values[key] = value

    async def expire(self, key: str, ttl_seconds: int):
        return True

    async def sadd(self, key: str, *values: str):
        current = self.sets.setdefault(key, set())
        before = len(current)
        current.update(values)
        return len(current) - before

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))

    async def llen(self, key: str):
        return len(self.lists.get(key, []))

    async def delete(self, *keys: str):
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)
            self.lists.pop(key, None)

    def pipeline(self):
        return _FakePipeline(self)


class _FakeSession:
    def __init__(self, exec_results: list[list[Question]]):
        self._exec_results = exec_results
        self._exec_index = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exec(self, statement):
        result = self._exec_results[self._exec_index]
        self._exec_index += 1
        return iter(result)

    def expunge(self, question: Question):
        return None


class QuestionDailyDedupeTests(unittest.IsolatedAsyncioTestCase):
    async def test_mark_question_served_payload_blocks_same_word_for_same_day(self):
        redis = _FakeRedis()
        first_payload = {
            "id": 22,
            "type": "context_guess",
            "content": {"target_word": "suit"},
        }
        repeated_payload = {
            "id": 99,
            "type": "context_guess",
            "content": {"target_word": "  SUIT  "},
        }

        await mark_question_served_payload(redis, 7, first_payload)

        self.assertTrue(await is_same_day_word_duplicate_payload(redis, 7, repeated_payload))

    async def test_ensure_question_queue_day_clears_untagged_queue(self):
        redis = _FakeRedis()
        user_id = 7
        redis.lists[_question_queue_key(user_id)] = ["q1", "q2"]
        redis.sets[_queue_id_set_key(user_id)] = {"1", "2"}
        redis.sets[_queue_fp_set_key(user_id)] = {"fp1", "fp2"}

        with (
            patch("app.db.question._current_srs_day_key", return_value="2026-04-10"),
            patch("app.db.question._seconds_until_srs_day_end", return_value=3600),
        ):
            await ensure_question_queue_day(redis, user_id)

        self.assertEqual(redis.lists.get(_question_queue_key(user_id), []), [])
        self.assertEqual(redis.sets.get(_queue_id_set_key(user_id), set()), set())
        self.assertEqual(redis.sets.get(_queue_fp_set_key(user_id), set()), set())
        self.assertEqual(redis.values[_question_queue_day_key(user_id)], "2026-04-10")

    async def test_word_generation_failure_reaches_threshold_and_enters_cooldown(self):
        redis = _FakeRedis()

        with (
            patch("app.db.question._current_srs_day_key", return_value="2026-04-10"),
            patch("app.db.question._seconds_until_srs_day_end", return_value=3600),
        ):
            first_count = await _record_word_generation_failure(redis, 7, "context_guess", ["headline"])
            second_count = await _record_word_generation_failure(redis, 7, "context_guess", ["headline"])
            await _mark_word_generation_cooldown(redis, 7, "context_guess", ["headline"])
            is_cooled_down = await _is_word_generation_cooled_down(redis, 7, "context_guess", ["headline"])

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 2)
        self.assertTrue(is_cooled_down)


class QuestionFallbackSelectionTests(unittest.TestCase):
    def test_extracts_and_dedupes_word_keys_from_cloze_content(self):
        word_keys = _question_word_keys_from_type_and_content(
            "cloze_test",
            {"correct_sequence": [" suit ", "SUIT", "coat"]},
        )

        self.assertEqual(word_keys, ["suit", "coat"])

    def test_select_fallback_question_skips_today_used_word(self):
        suit_question = Question(id=22, type="context_guess", content={"target_word": "suit"})
        delight_question = Question(id=23, type="context_guess", content={"target_word": "delight"})
        fake_session = _FakeSession(
            exec_results=[
                [suit_question],
                [delight_question],
                [],
            ]
        )

        with patch("app.db.question.DBSession", return_value=fake_session):
            selected = _select_fallback_question(7, "context_guess", {"suit"})

        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, 23)

    def test_select_fallback_question_skips_request_reserved_question(self):
        first_question = Question(id=30, type="context_guess", content={"target_word": "suit"})
        second_question = Question(id=31, type="context_guess", content={"target_word": "delight"})
        fake_session = _FakeSession(
            exec_results=[
                [first_question, second_question],
                [],
                [],
            ]
        )

        with patch("app.db.question.DBSession", return_value=fake_session):
            selected = _select_fallback_question(
                7,
                "context_guess",
                {"absent"},
                {30},
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, 31)


if __name__ == "__main__":
    unittest.main()
