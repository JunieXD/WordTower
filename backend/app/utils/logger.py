from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar, Token
from datetime import datetime
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_MAX_LOG_FILES = 7
DEBUG_SWITCH_ENV = "WORDTOWER_DEBUG"
STDOUT_SWITCH_ENV = "LOG_TO_STDOUT"

_user_label_var: ContextVar[str] = ContextVar("user_label", default="未登录")


def _env_to_bool(value: str | None, default: bool = False) -> bool:
    """将环境变量字符串解析为布尔值。"""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "debug"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def is_debug_logging_enabled() -> bool:
    """
    是否开启调试日志。

    通过环境变量 `WORDTOWER_DEBUG` 控制：
    - 1 / true / on / debug => 开启
    - 0 / false / off => 关闭
    """
    return _env_to_bool(os.getenv(DEBUG_SWITCH_ENV), default=False)


class RequestContextFilter(logging.Filter):
    """向日志记录注入用户信息。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_label = _user_label_var.get()
        return True


class DailyFileHandler(logging.Handler):
    """
    按天写入日志文件（YYYY-MM-DD.log），并自动清理超出数量的历史日志。
    """

    def __init__(self, log_dir: Path | str, max_files: int = DEFAULT_MAX_LOG_FILES, encoding: str = "utf-8"):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_files = max_files
        self.encoding = encoding

        self._current_date: str | None = None
        self._stream: TextIO | None = None

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _current_log_path(self) -> Path:
        return self.log_dir / f"{self._current_date}.log"

    def _open_stream_for_today(self) -> None:
        today = self._today()
        if self._current_date == today and self._stream:
            return

        if self._stream:
            self._stream.close()
            self._stream = None

        self._current_date = today
        self._stream = self._current_log_path().open(mode="a", encoding=self.encoding)
        self._cleanup_old_files()

    def _cleanup_old_files(self) -> None:
        files = sorted(self.log_dir.glob("*.log"), key=lambda p: p.name)
        if len(files) <= self.max_files:
            return

        for old_file in files[: len(files) - self.max_files]:
            old_file.unlink(missing_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._open_stream_for_today()
            if self._stream is None:
                return
            msg = self.format(record)
            self._stream.write(msg + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        if self._stream:
            self._stream.flush()

    def close(self) -> None:
        try:
            if self._stream:
                self._stream.close()
                self._stream = None
        finally:
            super().close()


def setup_logging(
    log_dir: Path | str = DEFAULT_LOG_DIR,
    max_files: int = DEFAULT_MAX_LOG_FILES,
    level: int = DEFAULT_LOG_LEVEL,
) -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_wordtower_logging_ready", False):
        return

    debug_enabled = is_debug_logging_enabled()
    stdout_enabled = debug_enabled or _env_to_bool(os.getenv(STDOUT_SWITCH_ENV), default=False)
    effective_level = logging.DEBUG if debug_enabled else level

    root_logger.setLevel(effective_level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | 用户=%(user_label)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = RequestContextFilter()

    file_handler = DailyFileHandler(log_dir=log_dir, max_files=max_files, encoding="utf-8")
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    root_logger.addHandler(file_handler)

    if stdout_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)

    # 容器通过 LOG_TO_STDOUT 输出日志；本地仍可只保留文件日志。
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.setLevel(effective_level)
        uvicorn_logger.propagate = True

    # 第三方库日志默认降级，避免刷屏影响可读性。
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    root_logger.info(
        "日志初始化完成：debug=%s 级别=%s 终端输出=%s 开关=%s",
        debug_enabled,
        logging.getLevelName(effective_level),
        stdout_enabled,
        DEBUG_SWITCH_ENV,
    )

    setattr(root_logger, "_wordtower_logging_ready", True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_context(user_label: str | None = None) -> Token[str]:
    if not user_label:
        return _user_label_var.set("未登录")
    return _user_label_var.set(str(user_label))


def set_user_context(user_label: int | str | None) -> Token[str]:
    if user_label is None:
        return _user_label_var.set("未登录")
    return _user_label_var.set(str(user_label))


def clear_request_context(token: Token[str]) -> None:
    _user_label_var.reset(token)
