"""Per-user admission control and retry-safe actions, backed by Redis.

Only new work spends tokens. Replays and in-flight retries never count as abuse.
Keys expire; Redis TIME and Lua keep admission atomic across processes.
"""
import asyncio
from contextlib import suppress
from contextvars import ContextVar
from functools import wraps
import hashlib
import inspect
import json
import math
import uuid

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from redis.exceptions import RedisError

from app.api.api_responses import too_many_requests_response, service_unavailable_response
from app.utils.config import settings


_operation_id: ContextVar[str] = ContextVar("traffic_operation_id", default="")
LEASE_SECONDS = 180
REPLAY_SECONDS = 86400

ADMIT_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local cap, interval = tonumber(ARGV[1]), tonumber(ARGV[2])
local background = ARGV[4] == '1'
local state = redis.call('HMGET', KEYS[1], 'tokens', 'updated', 'cooldown')
local tokens = math.min(cap, tonumber(state[1] or cap) + math.max(0, now - tonumber(state[2] or now)) / interval)
local cooldown = tonumber(state[3] or 0)
local function save()
  redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now, 'cooldown', cooldown)
  redis.call('PEXPIRE', KEYS[1], math.max(120000, cap * interval * 2))
end
if cooldown > now then
  save()
  return {0, cooldown - now}
end
-- Leave two tokens for interactive work. Never penalize background prefetch.
if background and (tokens < 3 or redis.call('EXISTS', KEYS[3]) == 1) then
  save()
  return {0, interval}
end
if tokens >= 1 then
  tokens = tokens - 1
  save()
  return {1, 0}
end
if not background then
  redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now - 40000)
  redis.call('ZADD', KEYS[2], 'NX', now, ARGV[3])
  redis.call('ZREMRANGEBYRANK', KEYS[2], 0, -129)
  redis.call('PEXPIRE', KEYS[2], 60000)
  local entries = redis.call('ZRANGE', KEYS[2], 0, -1, 'WITHSCORES')
  local bins = {}
  for i = 2, #entries, 2 do
    local bin = math.floor(tonumber(entries[i]) / 10000)
    bins[bin] = (bins[bin] or 0) + 1
  end
  local current = math.floor(now / 10000)
  -- A single reconnect burst cannot trigger cooldown, however large it is.
  if (bins[current] or 0) >= 3 and (bins[current-1] or 0) >= 3 and (bins[current-2] or 0) >= 3 then
    cooldown = now + tonumber(ARGV[5])
    redis.call('DEL', KEYS[2])
    save()
    return {0, cooldown - now}
  end
end
save()
return {0, math.ceil((1 - tokens) * interval)}
"""

RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""
RENEW_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('EXPIRE', KEYS[1], ARGV[2]) end
return 0
"""

CACHE_SCRIPT = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
redis.call('ZADD', KEYS[2], now, KEYS[1])
local stale = redis.call('ZRANGE', KEYS[2], 0, -513)
for _, key in ipairs(stale) do redis.call('DEL', key) end
redis.call('ZREMRANGEBYRANK', KEYS[2], 0, -513)
redis.call('EXPIRE', KEYS[2], ARGV[2])
return 1
"""


class TrafficLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


def _keys(user_id: int) -> tuple[str, str, str]:
    prefix = f"traffic:{{{user_id}}}"
    return f"{prefix}:bucket", f"{prefix}:bursts", f"{prefix}:active"


async def admit(redis, user_id: int, *, background: bool = False, soft_wait: bool = True) -> bool:
    """Spend one generation/grading unit; background work skips instead of waiting."""
    operation = _operation_id.get() or str(uuid.uuid4())
    async def check():
        return await redis.eval(
            ADMIT_SCRIPT, 3, *_keys(user_id), settings.TRAFFIC_BURST,
            settings.TRAFFIC_REFILL_SECONDS * 1000, operation, int(background),
            settings.TRAFFIC_COOLDOWN_SECONDS * 1000,
        )

    allowed, wait_ms = await check()
    if not allowed and not background and soft_wait and wait_ms <= 2000:
        await asyncio.sleep(wait_ms / 1000 + 0.02)
        allowed, wait_ms = await check()
    if allowed:
        return True
    if background:
        return False
    raise TrafficLimited(max(1, math.ceil(wait_ms / 1000)))


async def _renew(redis, key: str, owner: str):
    while True:
        await asyncio.sleep(LEASE_SECONDS / 3)
        if not await redis.eval(RENEW_SCRIPT, 1, key, owner, LEASE_SECONDS):
            return


async def run_action(redis, user_id: int, scope: str, action_id: str, fingerprint: str, operation):
    """Cache successful responses; allow only one interactive action per user.

    Same-user duplicate callers poll a cached result, never queue new LLM tasks.
    The one admitted caller owns at most a two-second admission wait.
    """
    digest = hashlib.sha256(f"{scope}:{action_id}".encode()).hexdigest()
    cache_key = f"traffic:{{{user_id}}}:replay:{digest}"
    lock_key = _keys(user_id)[2]
    owner = str(uuid.uuid4())

    async def cached():
        raw = await redis.get(cache_key)
        if not raw:
            return None
        entry = json.loads(raw)
        if entry["fingerprint"] != fingerprint:
            return JSONResponse(status_code=409, content={
                "success": False, "error_code": "IDEMPOTENCY_CONFLICT",
                "message": "这次操作的内容已变化，请重新提交。",
            })
        return JSONResponse(content=entry["body"], status_code=entry["status"],
                            headers={"Idempotency-Replayed": "true", "Cache-Control": "no-store"})

    try:
        replay = await cached()
        if replay is not None:
            return replay
        if not await redis.set(lock_key, owner, nx=True, ex=LEASE_SECONDS):
            # A tiny bounded wait often absorbs a duplicated click without another HTTP round trip.
            await asyncio.sleep(0.15)
            replay = await cached()
            if replay is not None:
                return replay
            return JSONResponse(status_code=425, headers={"Retry-After": "2"}, content={
                "success": False, "error_code": "REQUEST_IN_PROGRESS",
                "message": "上一项操作仍在处理，请稍等片刻。", "details": {"retry_after": 2},
            })
        renewal = asyncio.create_task(_renew(redis, lock_key, owner))
        context = _operation_id.set(digest)
        try:
            # Another process may have finished between our initial read and lock acquisition.
            replay = await cached()
            if replay is not None:
                return replay
            response = await operation()
            response.headers["Cache-Control"] = "no-store"
            if 200 <= response.status_code < 300:
                await redis.eval(CACHE_SCRIPT, 2, cache_key, f"traffic:{{{user_id}}}:replays", json.dumps({
                    "fingerprint": fingerprint, "status": response.status_code,
                    "body": json.loads(response.body),
                }, ensure_ascii=False), REPLAY_SECONDS)
            return response
        finally:
            _operation_id.reset(context)
            renewal.cancel()
            with suppress(asyncio.CancelledError, RedisError):
                await renewal
            await redis.eval(RELEASE_SCRIPT, 1, lock_key, owner)
    except TrafficLimited as exc:
        return too_many_requests_response(
            message="请求有些密集，请稍等片刻再继续。", retry_after=exc.retry_after,
        )
    except RedisError:
        # Never send unmetered work to the provider when coordination is unavailable.
        return service_unavailable_response(message="正在恢复连接，请稍后重试。", retry_after=3)


def user_action(scope: str, identity=None):
    """Endpoints retain their FastAPI signature; all must accept request and redis."""
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            request = kwargs["request"]
            user = kwargs.get("user_in") or kwargs["current_user"]
            body = await request.body()
            try:
                normalized = json.dumps(json.loads(body), sort_keys=True, ensure_ascii=False) if body else ""
            except ValueError:
                normalized = body.decode(errors="replace")
            fingerprint = hashlib.sha256((request.url.path + normalized).encode()).hexdigest()
            action_id = identity(kwargs, fingerprint) if identity else request.headers.get("Idempotency-Key")
            action_id = action_id or str(uuid.uuid4())
            if len(action_id) > 200:
                return JSONResponse(status_code=400, content={"success": False, "message": "请求标识过长"})
            async def invoke():
                if inspect.iscoroutinefunction(function):
                    return await function(*args, **kwargs)
                return await run_in_threadpool(function, *args, **kwargs)
            return await run_action(kwargs["redis"], user.id, scope, action_id, fingerprint, invoke)
        wrapped.__signature__ = inspect.signature(function, eval_str=True)
        return wrapped
    return decorate
