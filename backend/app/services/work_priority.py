from contextlib import contextmanager
from contextvars import ContextVar

is_background_work: ContextVar[bool] = ContextVar("is_background_work", default=False)


@contextmanager
def background_work():
    token = is_background_work.set(True)
    try:
        yield
    finally:
        is_background_work.reset(token)
