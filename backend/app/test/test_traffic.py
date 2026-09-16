import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from fakeredis.aioredis import FakeRedis
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError

from app.services import traffic


class TrafficTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 1_800_000_001.0
        self.clock = patch("time.time", side_effect=lambda: self.now)
        self.clock.start()
        self.redis = FakeRedis(decode_responses=True)
        self.settings = patch.multiple(traffic.settings, TRAFFIC_BURST=8,
                                       TRAFFIC_REFILL_SECONDS=3, TRAFFIC_COOLDOWN_SECONDS=15)
        self.settings.start()

    async def asyncTearDown(self):
        await self.redis.aclose()
        self.settings.stop()
        self.clock.stop()

    async def spend(self, operation, user=1, background=False):
        context = traffic._operation_id.set(operation)
        try:
            return await traffic.admit(self.redis, user, background=background, soft_wait=False)
        finally:
            traffic._operation_id.reset(context)

    async def empty_bucket(self):
        bucket = traffic._keys(1)[0]
        await self.redis.hset(bucket, mapping={"tokens": 0, "updated": int(self.now * 1000)})

    async def test_atomic_burst_limit_and_independent_users(self):
        results = await asyncio.gather(*(self.spend(str(i)) for i in range(20)), return_exceptions=True)
        self.assertEqual(sum(result is True for result in results), 8)
        self.assertEqual(sum(isinstance(result, traffic.TrafficLimited) for result in results), 12)
        self.assertTrue(await self.spend("another-user", user=2))

    async def test_continuous_normal_play_has_no_daily_quota(self):
        for i in range(1000):
            self.assertTrue(await self.spend(str(i)))
            self.now += 3

    async def test_large_reconnect_burst_does_not_trigger_cooldown(self):
        await self.empty_bucket()
        for i in range(100):
            with self.assertRaises(traffic.TrafficLimited):
                await self.spend(str(i))
        self.assertEqual(await self.redis.hget(traffic._keys(1)[0], "cooldown"), "0")
        self.now += 3
        self.assertTrue(await self.spend("recovered"))

    async def test_same_retry_is_only_one_observation(self):
        for _ in range(3):
            await self.empty_bucket()
            for _ in range(5):
                with self.assertRaises(traffic.TrafficLimited):
                    await self.spend("same-network-retry")
            self.now += 10
        self.assertEqual(await self.redis.zcard(traffic._keys(1)[1]), 1)
        self.assertEqual(await self.redis.hget(traffic._keys(1)[0], "cooldown"), "0")

    async def test_sustained_new_requests_cool_down_without_extending_deadline(self):
        for window in range(3):
            await self.empty_bucket()
            for i in range(3):
                with self.assertRaises(traffic.TrafficLimited):
                    await self.spend(f"{window}:{i}")
            if window < 2:
                self.now += 10
        bucket = traffic._keys(1)[0]
        deadline = await self.redis.hget(bucket, "cooldown")
        self.assertEqual(int(deadline), int((self.now + 15) * 1000))
        self.now += 5
        with self.assertRaises(traffic.TrafficLimited) as caught:
            await self.spend("during-cooldown")
        self.assertEqual(caught.exception.retry_after, 10)
        self.assertEqual(await self.redis.hget(bucket, "cooldown"), deadline)
        self.now += 10
        self.assertTrue(await self.spend("after-cooldown"))

    async def test_background_reserves_foreground_capacity_and_never_adds_strikes(self):
        for i in range(6):
            self.assertTrue(await self.spend(str(i), background=True))
        self.assertFalse(await self.spend("background-full", background=True))
        self.assertEqual(await self.redis.zcard(traffic._keys(1)[1]), 0)
        self.assertTrue(await self.spend("foreground"))
        await self.redis.set(traffic._keys(1)[2], "active-user")
        self.assertFalse(await self.spend("interactive-priority", background=True))

    async def test_replay_avoids_work_and_spending_even_during_cooldown(self):
        async def work():
            await self.spend("actual-work")
            return JSONResponse({"success": True, "data": {"id": 42}})
        operation = AsyncMock(side_effect=work)
        first = await traffic.run_action(self.redis, 1, "get", "one", "body", operation)
        await self.redis.hset(traffic._keys(1)[0], "cooldown", int((self.now + 15) * 1000))
        second = await traffic.run_action(self.redis, 1, "get", "one", "body", operation)
        self.assertEqual(first.body, second.body)
        self.assertEqual(second.headers["Idempotency-Replayed"], "true")
        operation.assert_awaited_once()

    async def test_concurrent_duplicate_has_one_owner_and_no_unbounded_queue(self):
        started, finish = asyncio.Event(), asyncio.Event()
        async def work():
            started.set()
            await finish.wait()
            return JSONResponse({"success": True})
        operation = AsyncMock(side_effect=work)
        first = asyncio.create_task(traffic.run_action(self.redis, 1, "get", "one", "body", operation))
        await started.wait()
        second = await traffic.run_action(self.redis, 1, "get", "one", "body", operation)
        self.assertEqual(second.status_code, 425)
        finish.set()
        await first
        replay = await traffic.run_action(self.redis, 1, "get", "one", "body", operation)
        self.assertEqual(replay.status_code, 200)
        operation.assert_awaited_once()

    async def test_reusing_key_with_changed_payload_does_not_reexecute(self):
        work = AsyncMock(return_value=JSONResponse({"success": True}))
        await traffic.run_action(self.redis, 1, "answer", "one", "old", work)
        result = await traffic.run_action(self.redis, 1, "answer", "one", "changed", work)
        self.assertEqual(result.status_code, 409)
        work.assert_awaited_once()

    async def test_rate_limit_response_has_retry_after_and_is_not_cached(self):
        await self.empty_bucket()
        async def work():
            await self.spend("one")
            return JSONResponse({"success": True})
        first = await traffic.run_action(self.redis, 1, "get", "one", "body", work)
        self.assertEqual(first.status_code, 429)
        self.assertEqual(first.headers["Retry-After"], "3")
        self.now += 3
        second = await traffic.run_action(self.redis, 1, "get", "one", "body", work)
        self.assertEqual(second.status_code, 200)

    async def test_cache_is_scoped_to_authenticated_user(self):
        work = AsyncMock(return_value=JSONResponse({"success": True}))
        await traffic.run_action(self.redis, 1, "get", "same", "same", work)
        await traffic.run_action(self.redis, 2, "get", "same", "same", work)
        self.assertEqual(work.await_count, 2)

    async def test_redis_outage_never_starts_unmetered_work(self):
        redis = AsyncMock()
        redis.get.side_effect = ConnectionError("offline")
        operation = AsyncMock()
        response = await traffic.run_action(redis, 1, "get", "one", "body", operation)
        self.assertEqual(response.status_code, 503)
        operation.assert_not_awaited()

    async def test_failed_work_releases_lock_and_can_be_retried(self):
        work = AsyncMock(side_effect=ValueError("failed"))
        with self.assertRaises(ValueError):
            await traffic.run_action(self.redis, 1, "get", "one", "body", work)
        self.assertFalse(await self.redis.exists(traffic._keys(1)[2]))

    async def test_http_question_replay_does_not_pop_two_questions(self):
        from app.api.routes import question
        from app.api.dependencies import get_current_user
        from app.db.redis import get_redis

        app = FastAPI()
        app.include_router(question.router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        async def redis_dependency():
            yield self.redis
        app.dependency_overrides[get_redis] = redis_dependency
        payload = {"id": 12, "type": "keyword_translation", "content": {"target_word": "tower"}}
        with patch.object(question, "ensure_question_queue_day", new=AsyncMock()), \
             patch.object(question, "_try_get_question_from_queue", new=AsyncMock(return_value=payload)) as pop:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                first = await client.get("/api/question/get", headers={"Idempotency-Key": "same-click"})
                retry = await client.get("/api/question/get", headers={"Idempotency-Key": "same-click"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), retry.json())
        pop.assert_awaited_once()
        self.assertFalse(await self.redis.exists(traffic._keys(1)[0]))

    async def test_http_check_admission_precedes_model_call(self):
        from app.api.routes import question
        from app.api.dependencies import get_current_user
        from app.db.redis import get_redis

        app = FastAPI()
        app.include_router(question.router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        async def redis_dependency():
            yield self.redis
        app.dependency_overrides[get_redis] = redis_dependency
        await self.empty_bucket()
        with patch.object(question, "precheck_translation_answer", return_value=None), \
             patch.object(question, "generate_text", new=AsyncMock()) as model:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/question/check", json={
                    "target_word": "tower", "chinese_sentence": "这是一座塔。", "user_input": "This is a tower.",
                })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "3")
        model.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
