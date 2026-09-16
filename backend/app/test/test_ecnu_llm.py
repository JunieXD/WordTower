import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from openai import AsyncOpenAI, AuthenticationError

from app.utils import LLM


def completion(content='{"ok":true}', finish_reason="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=content),
    )])


class ECNUCallTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.slots = asyncio.Semaphore(3)
        patcher = patch.object(LLM, "_request_slots", self.slots)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_background_requests_leave_slots_for_interactive_work(self):
        from app.services.work_priority import background_work
        active_background = peak_background = 0
        started, release = asyncio.Event(), asyncio.Event()
        async def create(**kwargs):
            nonlocal active_background, peak_background
            prompt = kwargs["messages"][1]["content"]
            if prompt == "background":
                active_background += 1
                peak_background = max(peak_background, active_background)
                started.set()
                await release.wait()
                active_background -= 1
            return completion()
        async def background():
            with background_work():
                return await LLM.generate_text("background")
        with patch.object(LLM, "_background_slots", asyncio.Semaphore(1)), \
             patch.object(LLM.client.chat.completions, "create", side_effect=create):
            tasks = [asyncio.create_task(background()) for _ in range(3)]
            try:
                await asyncio.wait_for(started.wait(), 1)
                result = await asyncio.wait_for(LLM.generate_text("interactive"), 1)
                self.assertEqual(result, {"ok": True})
            finally:
                release.set()
                await asyncio.gather(*tasks)
        self.assertEqual(peak_background, 1)

    async def test_shared_limit_queues_burst_and_releases_after_completion(self):
        active = peak = 0
        full = asyncio.Event()
        release = asyncio.Event()

        async def create(**kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 3:
                full.set()
            try:
                await release.wait()
                return completion()
            finally:
                active -= 1

        with patch.object(LLM.client.chat.completions, "create", side_effect=create) as mock:
            tasks = [asyncio.create_task(LLM.generate_text("JSON")) for _ in range(9)]
            try:
                await asyncio.wait_for(full.wait(), 1)
                self.assertEqual(mock.call_count, 3)
            finally:
                release.set()
                results = await asyncio.gather(*tasks)
        self.assertEqual(peak, 3)
        self.assertEqual(results, [{"ok": True}] * 9)
        self.assertEqual(self.slots._value, 3)

    async def test_error_and_cancellation_release_request_slot(self):
        started = asyncio.Event()

        async def blocked(**kwargs):
            started.set()
            await asyncio.Event().wait()

        with patch.object(LLM.client.chat.completions, "create", side_effect=blocked):
            task = asyncio.create_task(LLM.generate_text("JSON"))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(self.slots._value, 3)

        with patch.object(LLM.client.chat.completions, "create", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                await LLM.generate_text("JSON")
        self.assertEqual(self.slots._value, 3)

    async def test_queue_timeout_and_cancel_do_not_send_or_leak_slots(self):
        for _ in range(3):
            await self.slots.acquire()
        with patch.object(LLM.client.chat.completions, "create", new_callable=AsyncMock) as mock:
            with patch.object(LLM, "MAX_QUEUE_WAIT_SECONDS", 0.01):
                with self.assertRaisesRegex(TimeoutError, "排队超时"):
                    await LLM.generate_text("JSON")
            task = asyncio.create_task(LLM.generate_text("JSON"))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            mock.assert_not_awaited()
        self.assertEqual(self.slots._value, 0)
        for _ in range(3):
            self.slots.release()

    async def test_empty_and_incomplete_responses_retry_even_when_json_is_parseable(self):
        for bad in (completion(None), completion(" "), completion('{"ok":false}', "length"),
                    completion('{"ok":false}', "content_filter"), SimpleNamespace(choices=[])):
            with self.subTest(response=bad):
                with patch.object(LLM.client.chat.completions, "create",
                                  new=AsyncMock(side_effect=[bad, completion()])) as mock:
                    self.assertEqual(await LLM.generate_text("JSON"), {"ok": True})
                    self.assertEqual(mock.await_count, 2)
        self.assertEqual(self.slots._value, 3)

    async def test_invalid_responses_stop_after_retry_budget(self):
        with patch.object(LLM.client.chat.completions, "create",
                          new=AsyncMock(return_value=completion(None))) as mock:
            with self.assertRaisesRegex(ValueError, "为空"):
                await LLM.generate_text("JSON")
            self.assertEqual(mock.await_count, 2)
        self.assertEqual(self.slots._value, 3)

    async def test_wire_contract_and_sdk_429_retry(self):
        requests = []

        async def handler(request):
            requests.append(request)
            self.assertEqual(self.slots._value, 2)
            if len(requests) == 1:
                return httpx.Response(429, headers={"retry-after-ms": "1"},
                                      json={"error": {"message": "busy", "type": "rate_limit_error"}})
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0, "model": "ecnu-plus",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": '{"ok":true}'}}],
            })

        async with AsyncOpenAI(api_key="test-only", base_url="https://chat.ecnu.edu.cn/open/api/v1",
                               max_retries=1, http_client=httpx.AsyncClient(
                                   transport=httpx.MockTransport(handler))) as client:
            with patch.object(LLM, "client", client):
                self.assertEqual(await LLM.generate_text("Return JSON"), {"ok": True})
        self.assertEqual(len(requests), 2)
        payload = json.loads(requests[-1].content)
        self.assertEqual(str(requests[-1].url), "https://chat.ecnu.edu.cn/open/api/v1/chat/completions")
        self.assertEqual(payload["model"], "ecnu-plus")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(self.slots._value, 3)

    async def test_authentication_error_is_not_retried(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(401, json={"error": {"message": "invalid key"}})

        async with AsyncOpenAI(api_key="test-only", base_url="https://chat.ecnu.edu.cn/open/api/v1",
                               max_retries=1, http_client=httpx.AsyncClient(
                                   transport=httpx.MockTransport(handler))) as client:
            with patch.object(LLM, "client", client):
                with self.assertRaises(AuthenticationError):
                    await LLM.generate_text("JSON")
        self.assertEqual(len(requests), 1)
        self.assertEqual(self.slots._value, 3)
