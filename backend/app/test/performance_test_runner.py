"""
WordTower 性能测试脚本用法

1) 启动后端服务（另一个终端）:
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

2) 运行核心性能测试（默认，不调用 LLM）:
   uv run python app/test/performance_test_runner.py --mode core_no_llm --rounds 3

3) 运行 LLM 专项小并发测试（会消耗模型额度）:
   uv run python app/test/performance_test_runner.py --mode llm_focus --rounds 1

4) 常用参数:
   --base-url     后端地址，默认 http://127.0.0.1:8000
   --user-count   测试账号数（必须 >= 当前模式最大并发）
   --init-concurrency  初始化账号并发数（控制注册/登录并行度）
   --output-csv   CSV 输出路径（相对本脚本）
   --output-json  JSON 输出路径（相对本脚本）
   --log-file     日志文件路径（相对本脚本）

5) 默认输出:
   CSV/JSON: docs/performance_test_results_<mode>.*
   日志:     docs/perf_logs/performance_test_<mode>_<timestamp>.log

注意:
- 脚本会自动注册并登录测试账号（每次运行会生成唯一前缀），并写入测试数据。
- 建议连接测试库，避免污染正式数据。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import json
import logging
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx
import psycopg2

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


API_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
MODE_CORE_NO_LLM = "core_no_llm"
MODE_LLM_FOCUS = "llm_focus"
LOGGER = logging.getLogger("perf_test")
REQUEST_LOG_RE = re.compile(
    r"HTTP请求 方法=(?P<method>\S+) 路径=(?P<path>\S+) 状态码=(?P<status>\d+) 客户端IP=(?P<ip>\S+) 耗时=(?P<ms>\d+(?:\.\d+)?)ms"
)
LLM_GEN_RE = re.compile(r"单题生成耗时：.*?耗时=(?P<ms>\d+(?:\.\d+)?)ms")


@dataclass
class VirtualUser:
    username: str
    password: str
    client: httpx.AsyncClient


@dataclass
class ScenarioDef:
    scene: str
    concurrency: int
    call_fn: Callable[[VirtualUser, str], Awaitable[tuple[bool, str]]]
    prepare_fn: Callable[[list[VirtualUser], str], Awaitable[None]] | None = None
    warmup_count: int = 10
    no_conflict_mode: bool = False


@dataclass
class ScenarioResult:
    scene: str
    concurrency: int
    avg_ms: float
    p95_ms: float
    throughput: float
    error_rate: float
    conclusion: str
    total_requests: int
    success_requests: int
    failed_requests: int
    elapsed_seconds: float
    cpu_avg_pct: float | None = None
    ram_peak_mb: float | None = None
    disk_read_mb: float | None = None
    disk_write_mb: float | None = None
    disk_total_mb: float | None = None
    rtt_ms: float | None = None
    llm_api_ms: float | None = None
    db_query_ms: float | None = None
    server_avg_ms: float | None = None
    network_overhead_ms: float | None = None


@dataclass
class MetricsConfig:
    collect_system_metrics: bool
    collect_chain_metrics: bool
    backend_pid: int | None
    backend_log_path: Path | None
    db_url: str
    rtt_samples: int
    db_probe_samples: int
    sample_interval: float = 0.5


@dataclass
class ResourceMetrics:
    cpu_avg_pct: float | None = None
    ram_peak_mb: float | None = None
    disk_read_mb: float | None = None
    disk_write_mb: float | None = None
    disk_total_mb: float | None = None


@dataclass
class ChainMetrics:
    rtt_ms: float | None = None
    llm_api_ms: float | None = None
    db_query_ms: float | None = None
    server_avg_ms: float | None = None
    network_overhead_ms: float | None = None


def _normalize_db_url(db_url: str) -> str:
    return (
        db_url.replace("postgresql+psycopg2://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .strip()
    )


def _extract_method_and_path(scene: str) -> tuple[str | None, str | None]:
    method_match = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b", scene)
    path_match = re.search(r"(/api/\S+)", scene)
    method = method_match.group(1) if method_match else None
    path = path_match.group(1) if path_match else None
    return method, path


def _today_backend_log_path(script_dir: Path) -> Path:
    project_root = script_dir.parents[1]
    return project_root / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def _mark_log_offset(log_path: Path | None) -> int:
    if log_path is None or not log_path.exists():
        return 0
    return log_path.stat().st_size


def _read_log_chunk(log_path: Path | None, start_offset: int) -> str:
    if log_path is None or not log_path.exists():
        return ""
    with log_path.open("rb") as file:
        file.seek(start_offset)
        chunk = file.read()
    return chunk.decode("utf-8", errors="ignore")


def _parse_server_request_ms(
    log_chunk: str, method: str | None, path: str | None
) -> list[float]:
    if not method or not path:
        return []
    values: list[float] = []
    for match in REQUEST_LOG_RE.finditer(log_chunk):
        if match.group("method") == method and match.group("path") == path:
            values.append(float(match.group("ms")))
    return values


def _parse_llm_gen_ms(log_chunk: str) -> list[float]:
    return [float(match.group("ms")) for match in LLM_GEN_RE.finditer(log_chunk)]


async def _measure_tcp_rtt_ms(base_url: str, samples: int) -> float | None:
    parsed = urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host or samples <= 0:
        return None

    values: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        writer = None
        try:
            _, writer = await asyncio.open_connection(host, port)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            values.append(elapsed_ms)
        except Exception:
            continue
        finally:
            if writer is not None:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
    if not values:
        return None
    return mean(values)


def _probe_db_query_ms(db_url: str, samples: int, keyword: str = "a") -> float | None:
    if samples <= 0:
        return None
    sql = """
    SELECT text
    FROM word
    WHERE text ILIKE %s
      AND POSITION(' ' IN text) = 0
      AND POSITION('.' IN text) = 0
      AND POSITION('''' IN text) = 0
    ORDER BY
      CASE
        WHEN lower(text) = lower(%s) THEN 3
        WHEN lower(text) LIKE lower(%s) || '%%' THEN 2
        ELSE 1
      END DESC,
      length(text),
      text
    LIMIT 10
    """
    values: list[float] = []
    norm_db_url = _normalize_db_url(db_url)
    try:
        with psycopg2.connect(norm_db_url) as conn:
            with conn.cursor() as cur:
                for _ in range(samples):
                    started = time.perf_counter()
                    cur.execute(sql, (f"%{keyword}%", keyword, keyword))
                    cur.fetchall()
                    values.append((time.perf_counter() - started) * 1000.0)
    except Exception as exc:
        LOGGER.warning("DB 查询耗时采样失败：%s", exc)
        return None
    return mean(values) if values else None


def _detect_backend_pid(base_url: str) -> int | None:
    if psutil is None:
        return None
    parsed = urlparse(base_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if (
                conn.status == psutil.CONN_LISTEN
                and conn.laddr
                and conn.laddr.port == port
                and conn.pid
            ):
                return int(conn.pid)
    except Exception as exc:
        LOGGER.warning("自动检测后端 PID 失败：%s", exc)
        return None
    return None


class BackendResourceMonitor:
    def __init__(self, pid: int, sample_interval: float = 0.5):
        self.pid = pid
        self.sample_interval = sample_interval
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._cpu_samples: list[float] = []
        self._mem_samples: list[int] = []
        self._io_start: tuple[int, int] | None = None
        self._io_end: tuple[int, int] | None = None

    async def start(self) -> None:
        if psutil is None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> ResourceMetrics:
        if self._task is not None:
            self._stop_event.set()
            await self._task
        if not self._cpu_samples and not self._mem_samples:
            return ResourceMetrics()

        read_mb = None
        write_mb = None
        total_mb = None
        if self._io_start is not None and self._io_end is not None:
            read_delta = max(0, self._io_end[0] - self._io_start[0])
            write_delta = max(0, self._io_end[1] - self._io_start[1])
            read_mb = read_delta / (1024 * 1024)
            write_mb = write_delta / (1024 * 1024)
            total_mb = read_mb + write_mb

        return ResourceMetrics(
            cpu_avg_pct=mean(self._cpu_samples) if self._cpu_samples else None,
            ram_peak_mb=(max(self._mem_samples) / (1024 * 1024))
            if self._mem_samples
            else None,
            disk_read_mb=read_mb,
            disk_write_mb=write_mb,
            disk_total_mb=total_mb,
        )

    async def _run(self) -> None:
        if psutil is None:
            return
        try:
            proc = psutil.Process(self.pid)
            proc.cpu_percent(interval=None)
            io = proc.io_counters() if hasattr(proc, "io_counters") else None
            if io is not None:
                self._io_start = (int(io.read_bytes), int(io.write_bytes))
        except Exception as exc:
            LOGGER.warning("资源监控初始化失败 pid=%s err=%s", self.pid, exc)
            return

        while not self._stop_event.is_set():
            try:
                self._cpu_samples.append(proc.cpu_percent(interval=None))
                self._mem_samples.append(int(proc.memory_info().rss))
                if hasattr(proc, "io_counters"):
                    io = proc.io_counters()
                    self._io_end = (int(io.read_bytes), int(io.write_bytes))
            except Exception:
                break
            await asyncio.sleep(self.sample_interval)


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = int(0.95 * (len(sorted_values) - 1))
    return sorted_values[idx]


def build_conclusion(error_rate: float, p95_ms: float) -> str:
    if error_rate > 0.05:
        return "不满足/需优化"
    if error_rate > 0.01 or p95_ms > 2000:
        return "满足/接近上限"
    return "满足"


def render_progress(
    scene: str, done: int, total: int, start_time: float, bar_len: int = 24
) -> str:
    ratio = (done / total) if total > 0 else 1.0
    fill = int(ratio * bar_len)
    bar = "#" * fill + "-" * (bar_len - fill)
    elapsed = time.perf_counter() - start_time
    return (
        f"{scene} [{bar}] {done}/{total} ({ratio * 100:5.1f}%) elapsed={elapsed:6.1f}s"
    )


async def ensure_user(base_url: str, user: VirtualUser) -> None:
    register_payload = {"username": user.username, "password": user.password}
    register_resp = await user.client.post(
        f"{base_url}/api/auth/register", json=register_payload
    )
    if register_resp.status_code not in (201, 409):
        raise RuntimeError(
            f"注册用户失败 username={user.username} status={register_resp.status_code} body={register_resp.text}"
        )

    login_payload = {"username": user.username, "password": user.password}
    login_resp = await user.client.post(
        f"{base_url}/api/auth/login", json=login_payload
    )
    if login_resp.status_code != 200:
        raise RuntimeError(
            f"登录失败 username={user.username} status={login_resp.status_code} body={login_resp.text}"
        )


async def prepare_users(
    base_url: str, user_count: int, init_concurrency: int
) -> list[VirtualUser]:
    run_prefix = datetime.now().strftime("%y%m%d%H%M%S")
    run_suffix = uuid.uuid4().hex[:4]
    username_prefix = f"perf_user_{run_prefix}_{run_suffix}"
    LOGGER.info("本轮测试账号前缀：%s", username_prefix)

    users: list[VirtualUser] = [
        VirtualUser(
            username=f"{username_prefix}_{idx:04d}",
            password="Perf@123456",
            client=httpx.AsyncClient(timeout=API_TIMEOUT),
        )
        for idx in range(user_count)
    ]
    started_at = time.perf_counter()
    done = 0
    failed = 0
    errors: list[str] = []
    sem = asyncio.Semaphore(max(1, init_concurrency))
    lock = asyncio.Lock()
    progress_step = max(1, user_count // 100)

    async def _init_one(user: VirtualUser) -> None:
        nonlocal done, failed
        async with sem:
            try:
                await ensure_user(base_url, user)
            except Exception as exc:
                failed += 1
                if len(errors) < 5:
                    errors.append(f"{user.username}: {exc}")
            finally:
                done += 1
                if done % progress_step == 0 or done == user_count:
                    async with lock:
                        print(
                            "\r"
                            + render_progress(
                                "初始化测试账号", done, user_count, started_at
                            ),
                            end="",
                            flush=True,
                        )

    await asyncio.gather(*[_init_one(user) for user in users])
    print("")
    if failed > 0:
        await asyncio.gather(
            *[user.client.aclose() for user in users], return_exceptions=True
        )
        error_preview = "; ".join(errors)
        raise RuntimeError(
            f"初始化账号失败 {failed}/{user_count}，示例：{error_preview}"
        )
    return users


async def noop_prepare(_users: list[VirtualUser], _base_url: str) -> None:
    return None


async def prepare_combat_end(users: list[VirtualUser], base_url: str) -> None:
    async def _init_one(user: VirtualUser) -> None:
        await user.client.post(f"{base_url}/api/combat/start")

    await asyncio.gather(*[_init_one(user) for user in users], return_exceptions=True)


async def call_auth_login(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    payload = {"username": user.username, "password": user.password}
    resp = await user.client.post(f"{base_url}/api/auth/login", json=payload)
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_word_search(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/word/search", params={"q": "a"})
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_selected_words_count(
    user: VirtualUser, base_url: str
) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/library/get_selected_words_count")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_combat_start(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.post(f"{base_url}/api/combat/start")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_combat_end(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    payload = {"next": True, "end_hp": 80, "exp_gained": 5, "coins_gained": 5}
    resp = await user.client.post(f"{base_url}/api/combat/end", json=payload)
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_daily_overview(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/daily-challenge/overview")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_daily_leaderboard(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/daily-challenge/leaderboard")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_history_runs(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/history/runs")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_question_get(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.get(f"{base_url}/api/question/get")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_daily_start(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    resp = await user.client.post(f"{base_url}/api/daily-challenge/start")
    if resp.status_code == 200:
        return True, ""
    return False, f"HTTP {resp.status_code}"


async def call_daily_answer(user: VirtualUser, base_url: str) -> tuple[bool, str]:
    start_resp = await user.client.post(f"{base_url}/api/daily-challenge/start")
    if start_resp.status_code != 200:
        return False, f"start HTTP {start_resp.status_code}"

    try:
        payload = start_resp.json()
        question_id = payload["data"]["question"]["question_id"]
    except (KeyError, TypeError, ValueError):
        return False, "start response parse error"

    answer_payload = {
        "question_id": int(question_id),
        "is_correct": True,
        "answer_detail": {"source": "perf-test"},
    }
    answer_resp = await user.client.post(
        f"{base_url}/api/daily-challenge/answer", json=answer_payload
    )
    if answer_resp.status_code == 200:
        return True, ""
    return False, f"answer HTTP {answer_resp.status_code}"


def _expand(
    scene: str,
    concurrencies: list[int],
    fn: Callable[[VirtualUser, str], Awaitable[tuple[bool, str]]],
    prepare_fn: Callable[[list[VirtualUser], str], Awaitable[None]] | None = None,
    warmup_count: int = 10,
    no_conflict_mode: bool = False,
) -> list[ScenarioDef]:
    return [
        ScenarioDef(
            scene=scene,
            concurrency=concurrency,
            call_fn=fn,
            prepare_fn=prepare_fn,
            warmup_count=warmup_count,
            no_conflict_mode=no_conflict_mode,
        )
        for concurrency in concurrencies
    ]


def build_scenarios(mode: str) -> list[ScenarioDef]:
    if mode == MODE_CORE_NO_LLM:
        scenarios: list[ScenarioDef] = []
        scenarios += _expand(
            "用户登录 POST /api/auth/login",
            [10, 50, 100],
            call_auth_login,
            noop_prepare,
        )
        scenarios += _expand(
            "单词搜索 GET /api/word/search",
            [50, 100, 200],
            call_word_search,
            noop_prepare,
        )
        scenarios += _expand(
            "词库已选统计 GET /api/library/get_selected_words_count",
            [50, 100, 200],
            call_selected_words_count,
            noop_prepare,
        )
        scenarios += _expand(
            "战斗开始 POST /api/combat/start",
            [10, 50, 100],
            call_combat_start,
            noop_prepare,
        )
        scenarios += _expand(
            "战斗结算 POST /api/combat/end",
            [10, 30, 50],
            call_combat_end,
            prepare_combat_end,
        )
        scenarios += _expand(
            "每日概览 GET /api/daily-challenge/overview",
            [20, 50, 100],
            call_daily_overview,
            noop_prepare,
        )
        scenarios += _expand(
            "每日排行榜 GET /api/daily-challenge/leaderboard",
            [50, 100, 200],
            call_daily_leaderboard,
            noop_prepare,
        )
        scenarios += _expand(
            "历史记录列表 GET /api/history/runs",
            [50, 100, 200],
            call_history_runs,
            noop_prepare,
        )
        return scenarios

    if mode == MODE_LLM_FOCUS:
        scenarios = []
        scenarios += _expand(
            "题目获取 GET /api/question/get",
            [10, 20, 50],
            call_question_get,
            noop_prepare,
            warmup_count=2,
        )
        scenarios += _expand(
            "每日开始 POST /api/daily-challenge/start",
            [10, 20, 50],
            call_daily_start,
            noop_prepare,
            warmup_count=2,
        )
        scenarios += _expand(
            "每日作答 POST /api/daily-challenge/answer",
            [10, 20, 50],
            call_daily_answer,
            noop_prepare,
            warmup_count=0,
            no_conflict_mode=True,
        )
        return scenarios

    raise ValueError(f"未知模式: {mode}")


async def warmup(
    users: list[VirtualUser],
    base_url: str,
    call_fn: Callable[[VirtualUser, str], Awaitable[tuple[bool, str]]],
    request_count: int,
) -> None:
    if not users or request_count <= 0:
        return
    for idx in range(request_count):
        user = users[idx % len(users)]
        try:
            await call_fn(user, base_url)
        except Exception:
            pass


async def run_scenario(
    scenario: ScenarioDef,
    users: list[VirtualUser],
    base_url: str,
    rounds: int,
    metrics_config: MetricsConfig,
) -> ScenarioResult:
    if scenario.concurrency > len(users):
        raise ValueError(f"并发数 {scenario.concurrency} 超过用户数 {len(users)}")

    active_users = users[: scenario.concurrency]
    if scenario.prepare_fn is not None:
        await scenario.prepare_fn(active_users, base_url)
    await warmup(
        active_users,
        base_url,
        scenario.call_fn,
        request_count=min(scenario.warmup_count, scenario.concurrency),
    )

    method, path = _extract_method_and_path(scenario.scene)
    log_offset = _mark_log_offset(metrics_config.backend_log_path)
    resource_monitor: BackendResourceMonitor | None = None
    if (
        metrics_config.collect_system_metrics
        and metrics_config.backend_pid is not None
        and psutil is not None
    ):
        resource_monitor = BackendResourceMonitor(
            metrics_config.backend_pid,
            sample_interval=metrics_config.sample_interval,
        )
        await resource_monitor.start()

    rtt_ms: float | None = None
    db_query_ms: float | None = None
    if metrics_config.collect_chain_metrics:
        rtt_ms = await _measure_tcp_rtt_ms(base_url, metrics_config.rtt_samples)
        db_query_ms = await asyncio.to_thread(
            _probe_db_query_ms,
            metrics_config.db_url,
            metrics_config.db_probe_samples,
            "a",
        )

    effective_rounds = rounds
    if scenario.no_conflict_mode and rounds != 1:
        LOGGER.warning(
            "场景启用无冲突模式，自动将 rounds 从 %s 调整为 1：scene=%s",
            rounds,
            scenario.scene,
        )
        effective_rounds = 1

    total_requests = scenario.concurrency * effective_rounds
    latencies_ms: list[float] = []
    failed = 0
    failed_reason_counter: Counter[str] = Counter()
    sem = asyncio.Semaphore(scenario.concurrency)
    progress_lock = asyncio.Lock()
    completed = 0
    started_all = time.perf_counter()
    progress_step = max(1, total_requests // 100)

    async def one_request(req_idx: int) -> None:
        nonlocal failed, completed
        user = active_users[req_idx % scenario.concurrency]
        async with sem:
            started = time.perf_counter()
            try:
                ok, reason = await scenario.call_fn(user, base_url)
            except Exception:
                ok = False
                reason = "exception"
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(elapsed_ms)
            if not ok:
                failed += 1
                failed_reason_counter[reason] += 1
            completed += 1
            if completed % progress_step == 0 or completed == total_requests:
                async with progress_lock:
                    print(
                        "\r"
                        + render_progress(
                            scenario.scene, completed, total_requests, started_all
                        ),
                        end="",
                        flush=True,
                    )

    await asyncio.gather(*[one_request(i) for i in range(total_requests)])
    resource_metrics = (
        await resource_monitor.stop()
        if resource_monitor is not None
        else ResourceMetrics()
    )
    log_chunk = _read_log_chunk(metrics_config.backend_log_path, log_offset)
    server_values = (
        _parse_server_request_ms(log_chunk, method=method, path=path)
        if metrics_config.collect_chain_metrics
        else []
    )
    llm_values = (
        _parse_llm_gen_ms(log_chunk) if metrics_config.collect_chain_metrics else []
    )
    print("")
    elapsed_seconds = time.perf_counter() - started_all
    success = total_requests - failed
    avg_ms = mean(latencies_ms) if latencies_ms else 0.0
    p95_ms = percentile_95(latencies_ms)
    throughput = (total_requests / elapsed_seconds) if elapsed_seconds > 0 else 0.0
    error_rate = (failed / total_requests) if total_requests > 0 else 0.0
    conclusion = build_conclusion(error_rate, p95_ms)
    server_avg_ms = mean(server_values) if server_values else None
    network_overhead_ms = (
        max(avg_ms - server_avg_ms, 0.0) if server_avg_ms is not None else None
    )
    llm_api_ms = mean(llm_values) if llm_values else None

    result = ScenarioResult(
        scene=scenario.scene,
        concurrency=scenario.concurrency,
        avg_ms=avg_ms,
        p95_ms=p95_ms,
        throughput=throughput,
        error_rate=error_rate,
        conclusion=conclusion,
        total_requests=total_requests,
        success_requests=success,
        failed_requests=failed,
        elapsed_seconds=elapsed_seconds,
        cpu_avg_pct=resource_metrics.cpu_avg_pct,
        ram_peak_mb=resource_metrics.ram_peak_mb,
        disk_read_mb=resource_metrics.disk_read_mb,
        disk_write_mb=resource_metrics.disk_write_mb,
        disk_total_mb=resource_metrics.disk_total_mb,
        rtt_ms=rtt_ms,
        llm_api_ms=llm_api_ms,
        db_query_ms=db_query_ms,
        server_avg_ms=server_avg_ms,
        network_overhead_ms=network_overhead_ms,
    )
    if failed_reason_counter:
        LOGGER.warning(
            "场景失败分布 scene=%s concurrency=%s reasons=%s",
            scenario.scene,
            scenario.concurrency,
            dict(failed_reason_counter.most_common(5)),
        )
    return result


def save_csv(results: list[ScenarioResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "场景",
                "并发数",
                "Avg(ms)",
                "P95(ms)",
                "吞吐量",
                "错误率",
                "结论",
                "总请求数",
                "成功数",
                "失败数",
                "总耗时(s)",
                "CPU均值(%)",
                "RAM峰值(MB)",
                "磁盘读(MB)",
                "磁盘写(MB)",
                "磁盘IO总量(MB)",
                "RTT(ms)",
                "LLM生成耗时(ms)",
                "DB查询耗时(ms)",
                "服务端耗时均值(ms)",
                "网络开销均值(ms)",
            ]
        )
        for result in results:
            cpu_avg_pct = (
                f"{result.cpu_avg_pct:.2f}" if result.cpu_avg_pct is not None else ""
            )
            ram_peak_mb = (
                f"{result.ram_peak_mb:.2f}" if result.ram_peak_mb is not None else ""
            )
            disk_read_mb = (
                f"{result.disk_read_mb:.2f}" if result.disk_read_mb is not None else ""
            )
            disk_write_mb = (
                f"{result.disk_write_mb:.2f}"
                if result.disk_write_mb is not None
                else ""
            )
            disk_total_mb = (
                f"{result.disk_total_mb:.2f}"
                if result.disk_total_mb is not None
                else ""
            )
            rtt_ms = f"{result.rtt_ms:.2f}" if result.rtt_ms is not None else ""
            llm_api_ms = (
                f"{result.llm_api_ms:.2f}" if result.llm_api_ms is not None else ""
            )
            db_query_ms = (
                f"{result.db_query_ms:.2f}" if result.db_query_ms is not None else ""
            )
            server_avg_ms = (
                f"{result.server_avg_ms:.2f}"
                if result.server_avg_ms is not None
                else ""
            )
            network_overhead_ms = (
                f"{result.network_overhead_ms:.2f}"
                if result.network_overhead_ms is not None
                else ""
            )
            writer.writerow(
                [
                    result.scene,
                    result.concurrency,
                    f"{result.avg_ms:.2f}",
                    f"{result.p95_ms:.2f}",
                    f"{result.throughput:.2f}",
                    f"{result.error_rate * 100:.2f}%",
                    result.conclusion,
                    result.total_requests,
                    result.success_requests,
                    result.failed_requests,
                    f"{result.elapsed_seconds:.2f}",
                    cpu_avg_pct,
                    ram_peak_mb,
                    disk_read_mb,
                    disk_write_mb,
                    disk_total_mb,
                    rtt_ms,
                    llm_api_ms,
                    db_query_ms,
                    server_avg_ms,
                    network_overhead_ms,
                ]
            )


def save_json(results: list[ScenarioResult], mode: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "results": [result.__dict__ for result in results],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_fallback_output_path(path: Path, timestamp: str) -> Path:
    return path.with_name(f"{path.stem}_fallback_{timestamp}{path.suffix}")


def save_results_with_fallback(
    results: list[ScenarioResult], mode: str, output_csv: Path, output_json: Path
) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    actual_csv = output_csv
    actual_json = output_json

    try:
        save_csv(results, output_csv)
    except PermissionError as exc:
        actual_csv = _build_fallback_output_path(output_csv, timestamp)
        LOGGER.warning(
            "CSV 写入失败（可能文件被占用），已切换到备用文件：src=%s fallback=%s err=%s",
            output_csv,
            actual_csv,
            exc,
        )
        save_csv(results, actual_csv)

    try:
        save_json(results, mode, output_json)
    except PermissionError as exc:
        actual_json = _build_fallback_output_path(output_json, timestamp)
        LOGGER.warning(
            "JSON 写入失败（可能文件被占用），已切换到备用文件：src=%s fallback=%s err=%s",
            output_json,
            actual_json,
            exc,
        )
        save_json(results, mode, actual_json)

    return actual_csv, actual_json


def resolve_output_paths(
    script_dir: Path, mode: str, output_csv: str | None, output_json: str | None
) -> tuple[Path, Path]:
    csv_rel = output_csv or f"../../../docs/performance_test_results_{mode}.csv"
    json_rel = output_json or f"../../../docs/performance_test_results_{mode}.json"
    return (script_dir / csv_rel).resolve(), (script_dir / json_rel).resolve()


def resolve_log_path(script_dir: Path, mode: str, log_file: str | None) -> Path:
    if log_file:
        return (script_dir / log_file).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        script_dir / f"../../../docs/perf_logs/performance_test_{mode}_{timestamp}.log"
    ).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WordTower 性能测试脚本")
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000", help="后端服务地址"
    )
    parser.add_argument(
        "--mode",
        default=MODE_CORE_NO_LLM,
        choices=[MODE_CORE_NO_LLM, MODE_LLM_FOCUS],
        help="core_no_llm 默认不测 LLM；llm_focus 为小并发 LLM 专项",
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="每个场景轮次，总请求=并发数*轮次"
    )
    parser.add_argument(
        "--user-count",
        type=int,
        default=None,
        help="测试账号数量，默认自动取当前模式的最大并发",
    )
    parser.add_argument(
        "--init-concurrency", type=int, default=20, help="初始化账号并发数，默认 20"
    )
    parser.add_argument(
        "--output-csv", default=None, help="CSV 输出路径（相对当前脚本）"
    )
    parser.add_argument(
        "--output-json", default=None, help="JSON 输出路径（相对当前脚本）"
    )
    parser.add_argument("--log-file", default=None, help="日志文件路径（相对当前脚本）")
    parser.add_argument(
        "--no-system-metrics",
        action="store_true",
        help="不采集系统资源指标（CPU/RAM/磁盘IO）",
    )
    parser.add_argument(
        "--no-chain-metrics",
        action="store_true",
        help="不采集链路拆解指标（RTT/LLM/DB）",
    )
    parser.add_argument(
        "--backend-pid",
        type=int,
        default=None,
        help="后端进程 PID（不传则自动按端口检测）",
    )
    parser.add_argument(
        "--backend-log-path",
        default=None,
        help="后端应用日志路径（默认自动使用 backend/logs/当天.log）",
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv(
            "DATABASE_URL", "postgresql://postgres:123456@localhost:5432/wordtower"
        ),
        help="数据库连接串（用于 DB 查询耗时采样）",
    )
    parser.add_argument(
        "--rtt-samples",
        type=int,
        default=5,
        help="每个场景 RTT 采样次数，默认 5",
    )
    parser.add_argument(
        "--db-probe-samples",
        type=int,
        default=5,
        help="每个场景 DB 查询耗时采样次数，默认 5",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.5,
        help="系统资源采样间隔（秒），默认 0.5",
    )
    return parser.parse_args()


async def run_all(
    base_url: str,
    mode: str,
    rounds: int,
    user_count: int | None,
    init_concurrency: int,
    output_csv: Path,
    output_json: Path,
    log_path: Path,
    metrics_config: MetricsConfig,
) -> None:
    configure_logging(log_path)
    scenarios = build_scenarios(mode)
    max_concurrency = max(scenario.concurrency for scenario in scenarios)
    final_user_count = user_count or max_concurrency
    if final_user_count < max_concurrency:
        raise ValueError(
            f"user-count({final_user_count}) 不能小于最大并发({max_concurrency})"
        )

    print(
        f"[INFO] 模式={mode} 场景数={len(scenarios)} 最大并发={max_concurrency} 账号数={final_user_count}"
    )
    print(f"[INFO] 初始化并发={init_concurrency}")
    print(f"[INFO] 日志文件={log_path}")
    print(
        f"[INFO] 资源指标采集={'开' if metrics_config.collect_system_metrics else '关'} "
        f"链路拆解采集={'开' if metrics_config.collect_chain_metrics else '关'}"
    )
    if metrics_config.backend_pid is not None:
        print(f"[INFO] 后端PID={metrics_config.backend_pid}")
    if metrics_config.backend_log_path is not None:
        print(f"[INFO] 后端日志={metrics_config.backend_log_path}")
    LOGGER.info(
        "测试启动 mode=%s rounds=%s scenarios=%s max_concurrency=%s user_count=%s base_url=%s collect_system_metrics=%s collect_chain_metrics=%s backend_pid=%s backend_log=%s",
        mode,
        rounds,
        len(scenarios),
        max_concurrency,
        final_user_count,
        base_url,
        metrics_config.collect_system_metrics,
        metrics_config.collect_chain_metrics,
        metrics_config.backend_pid,
        metrics_config.backend_log_path,
    )
    print("[INIT] 正在初始化测试账号（注册+登录）...")
    LOGGER.info(
        "初始化账号开始 user_count=%s init_concurrency=%s",
        final_user_count,
        init_concurrency,
    )
    users = await prepare_users(base_url, final_user_count, init_concurrency)
    LOGGER.info("初始化账号完成 user_count=%s", final_user_count)
    try:
        results: list[ScenarioResult] = []
        for idx, scenario in enumerate(scenarios, start=1):
            LOGGER.info(
                "场景开始 index=%s/%s scene=%s concurrency=%s rounds=%s",
                idx,
                len(scenarios),
                scenario.scene,
                scenario.concurrency,
                rounds,
            )
            print(
                f"[SCENE {idx}/{len(scenarios)}] {scenario.scene} 并发={scenario.concurrency}"
            )
            result = await run_scenario(
                scenario, users, base_url, rounds, metrics_config
            )
            results.append(result)
            print(
                f"[DONE] {result.scene} 并发={result.concurrency} Avg={result.avg_ms:.2f}ms "
                f"P95={result.p95_ms:.2f}ms 吞吐={result.throughput:.2f}/s 错误率={result.error_rate * 100:.2f}% "
                f"CPU={result.cpu_avg_pct:.2f}% RTT={result.rtt_ms:.2f}ms DB={result.db_query_ms:.2f}ms"
                if (
                    result.cpu_avg_pct is not None
                    and result.rtt_ms is not None
                    and result.db_query_ms is not None
                )
                else f"[DONE] {result.scene} 并发={result.concurrency} Avg={result.avg_ms:.2f}ms "
                f"P95={result.p95_ms:.2f}ms 吞吐={result.throughput:.2f}/s 错误率={result.error_rate * 100:.2f}%"
            )
            LOGGER.info(
                "场景完成 scene=%s concurrency=%s avg_ms=%.2f p95_ms=%.2f throughput=%.2f error_rate=%.4f success=%s failed=%s",
                result.scene,
                result.concurrency,
                result.avg_ms,
                result.p95_ms,
                result.throughput,
                result.error_rate,
                result.success_requests,
                result.failed_requests,
            )

        actual_csv, actual_json = save_results_with_fallback(
            results, mode, output_csv, output_json
        )
        print(f"\n结果已写入: {actual_csv}")
        print(f"详细JSON: {actual_json}")
        if actual_csv != output_csv or actual_json != output_json:
            print("[WARN] 默认结果文件被占用，已自动写入 fallback 文件。")
        LOGGER.info("结果写入完成 csv=%s json=%s", actual_csv, actual_json)
    finally:
        await asyncio.gather(
            *[user.client.aclose() for user in users], return_exceptions=True
        )
        LOGGER.info("测试结束，客户端连接已关闭")


if __name__ == "__main__":
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    output_csv_path, output_json_path = resolve_output_paths(
        script_dir=script_dir,
        mode=args.mode,
        output_csv=args.output_csv,
        output_json=args.output_json,
    )
    log_path = resolve_log_path(
        script_dir=script_dir, mode=args.mode, log_file=args.log_file
    )
    backend_pid = args.backend_pid or _detect_backend_pid(args.base_url)
    backend_log_path = (
        (script_dir / args.backend_log_path).resolve()
        if args.backend_log_path
        else _today_backend_log_path(script_dir)
    )
    metrics_config = MetricsConfig(
        collect_system_metrics=not args.no_system_metrics,
        collect_chain_metrics=not args.no_chain_metrics,
        backend_pid=backend_pid,
        backend_log_path=backend_log_path,
        db_url=args.db_url,
        rtt_samples=args.rtt_samples,
        db_probe_samples=args.db_probe_samples,
        sample_interval=args.sample_interval,
    )
    if metrics_config.collect_system_metrics and psutil is None:
        print("[WARN] 未安装 psutil，系统资源采集将自动关闭。可执行：uv add psutil")
        metrics_config.collect_system_metrics = False
    if metrics_config.collect_system_metrics and metrics_config.backend_pid is None:
        print(
            "[WARN] 未检测到后端进程 PID，系统资源采集将自动关闭。可通过 --backend-pid 指定。"
        )
        metrics_config.collect_system_metrics = False
    asyncio.run(
        run_all(
            base_url=args.base_url,
            mode=args.mode,
            rounds=args.rounds,
            user_count=args.user_count,
            init_concurrency=args.init_concurrency,
            output_csv=output_csv_path,
            output_json=output_json_path,
            log_path=log_path,
            metrics_config=metrics_config,
        )
    )
