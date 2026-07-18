from __future__ import annotations

import math
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.models.question_word_link import QuestionWordLink
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord
from app.models.word import Word
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Same difficulty prior used by the paper preprocess.
_D2P = [0.86, 0.78, 0.72, 0.66, 0.61, 0.55, 0.49, 0.44, 0.39, 0.34]
_MIN_INTERVAL_DAYS = 1e-3
_EPS = 1e-6


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _interval_days(left: datetime, right: datetime) -> float:
    seconds = (_to_utc(right) - _to_utc(left)).total_seconds()
    return max(seconds / 86400.0, _MIN_INTERVAL_DAYS)


def _difficulty_prior(difficulty: int | None) -> float:
    if difficulty is None:
        return _D2P[0]
    idx = _clamp(float(difficulty), 1.0, float(len(_D2P)))
    return _D2P[int(idx) - 1]


class _GruHlrPredictor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._available = False
        self._torch = None
        self._model = None
        self._warned = False

    def _warn_once(self, message: str, *args: object) -> None:
        if self._warned:
            return
        self._warned = True
        logger.warning(message, *args)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if not settings.SRS_ENABLED:
                return

            model_path = Path(settings.SRS_MODEL_PATH)
            if not model_path.exists():
                self._warn_once("SRS model file not found, fallback to heuristic scheduler: %s", str(model_path))
                return

            try:
                import torch  # type: ignore
            except Exception as exc:  # pragma: no cover
                self._warn_once("SRS torch import failed, fallback to heuristic scheduler: %s", str(exc))
                return

            try:
                model = torch.jit.load(str(model_path), map_location="cpu")
                model.eval()
                self._torch = torch
                self._model = model
                self._available = True
                logger.info("SRS model loaded: %s", str(model_path))
            except Exception as exc:  # pragma: no cover
                self._warn_once("SRS model load failed, fallback to heuristic scheduler: %s", str(exc))

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._available

    def predict_halflife(self, r_history: list[int], t_history: list[float], p_history: list[float]) -> float:
        self._ensure_loaded()
        if not self._available or not r_history:
            return _fallback_halflife(r_history, t_history)

        torch = self._torch
        model = self._model
        feature_num = 3
        sample_tensor = torch.zeros(len(r_history), 1, feature_num, dtype=torch.float32)
        for idx, response in enumerate(r_history):
            sample_tensor[idx][0][0] = float(int(response))
            sample_tensor[idx][0][1] = float(t_history[idx])
            sample_tensor[idx][0][2] = float(p_history[idx])

        hidden = torch.zeros(1, 1, int(settings.SRS_MODEL_HIDDEN))
        with torch.no_grad():
            output, _ = model.forward(sample_tensor, hidden)
            halflife = float(output[0][0].item())
        return max(halflife, 0.1)


def _fallback_halflife(r_history: list[int], t_history: list[float]) -> float:
    if not r_history:
        return 1.0
    correct_ratio = sum(r_history) / len(r_history)
    mean_interval = sum(t_history) / max(len(t_history), 1)
    # Lightweight fallback when model is unavailable.
    base = 0.8 + 1.2 * correct_ratio + 0.5 * math.log1p(len(r_history))
    return max(base + 0.3 * mean_interval, 0.2)


_PREDICTOR = _GruHlrPredictor()


@dataclass
class _WordSchedule:
    word: Word
    is_new: bool
    is_due: bool
    p_now: float
    halflife_hat: float
    next_interval_days: float
    overdue_days: float
    history_count: int
    last_review_at: datetime | None


@dataclass
class _ScheduleBuckets:
    due_words: list[_WordSchedule]
    new_words: list[_WordSchedule]
    review_not_due: list[_WordSchedule]


def _build_model_inputs(events: list[tuple[datetime, bool]], difficulty: int | None) -> tuple[list[int], list[float], list[float]]:
    r_history: list[int] = []
    t_history: list[float] = []
    if not events:
        return r_history, t_history, []

    for idx, (_, is_correct) in enumerate(events):
        r_history.append(1 if is_correct else 0)
        if idx == 0:
            t_history.append(0.0)
        else:
            delta_days = _interval_days(events[idx - 1][0], events[idx][0])
            t_history.append(delta_days)

    p_history: list[float] = [_difficulty_prior(difficulty)]
    for idx in range(1, len(r_history)):
        # We do not have native p_history in DB; approximate it from previous result confidence.
        previous_correct = r_history[idx - 1]
        p_history.append(0.86 if previous_correct == 1 else 0.38)
    return r_history, t_history, p_history


def _calc_schedule_for_word(word: Word, events: list[tuple[datetime, bool]], now: datetime) -> _WordSchedule:
    if not events:
        return _WordSchedule(
            word=word,
            is_new=True,
            is_due=False,
            p_now=1.0,
            halflife_hat=0.0,
            next_interval_days=0.0,
            overdue_days=0.0,
            history_count=0,
            last_review_at=None,
        )

    r_history, t_history, p_history = _build_model_inputs(events, word.difficulty)
    halflife_hat = _PREDICTOR.predict_halflife(r_history, t_history, p_history)
    elapsed_days = _interval_days(events[-1][0], now)

    p_now = math.exp(math.log(0.5) * elapsed_days / max(halflife_hat, 0.1))
    p_now = _clamp(p_now, _EPS, 1.0)

    target_recall = _clamp(float(settings.SRS_TARGET_RECALL), 0.5, 0.95)
    next_interval_days = max(halflife_hat * math.log(target_recall) / math.log(0.5), _MIN_INTERVAL_DAYS)
    overdue_days = elapsed_days - next_interval_days
    is_due = elapsed_days >= next_interval_days

    return _WordSchedule(
        word=word,
        is_new=False,
        is_due=is_due,
        p_now=p_now,
        halflife_hat=halflife_hat,
        next_interval_days=next_interval_days,
        overdue_days=overdue_days,
        history_count=len(events),
        last_review_at=events[-1][0],
    )


def _bucket_and_sort_schedules(schedules: list[_WordSchedule]) -> _ScheduleBuckets:
    due_words = [item for item in schedules if (not item.is_new and item.is_due)]
    new_words = [item for item in schedules if item.is_new]
    review_not_due = [item for item in schedules if (not item.is_new and not item.is_due)]

    # Lower p_now means more urgent; then more overdue first.
    due_words.sort(key=lambda item: (item.p_now, -item.overdue_days, item.word.id or 0))
    random.shuffle(new_words)
    review_not_due.sort(key=lambda item: (item.p_now, item.word.id or 0))
    return _ScheduleBuckets(
        due_words=due_words,
        new_words=new_words,
        review_not_due=review_not_due,
    )


def _load_word_events(session: Session, user: User, word_ids: list[int]) -> dict[int, list[tuple[datetime, bool]]]:
    if not word_ids:
        return {}

    statement = (
        select(
            QuestionWordLink.word_id,
            UserQuestionRecord.time,
            UserQuestionRecord.correct,
        )
        .join(UserQuestionRecord, UserQuestionRecord.question_id == QuestionWordLink.question_id)
        .where(UserQuestionRecord.user_id == user.id)
        .where(QuestionWordLink.word_id.in_(word_ids))
        .where(UserQuestionRecord.correct.is_not(None))
        .order_by(QuestionWordLink.word_id, UserQuestionRecord.time.asc(), UserQuestionRecord.id.asc())
    )

    rows = session.exec(statement).all()
    events_by_word: dict[int, list[tuple[datetime, bool]]] = {}
    for word_id, answered_at, is_correct in rows:
        if answered_at is None:
            continue
        events_by_word.setdefault(int(word_id), []).append((_to_utc(answered_at), bool(is_correct)))
    return events_by_word


def rank_words_with_srs_priority(session: Session, user: User, all_words: list[Word]) -> list[Word]:
    if not all_words:
        return []
    now = datetime.now(timezone.utc)
    word_ids = [word.id for word in all_words if word.id is not None]
    events_by_word = _load_word_events(session, user, word_ids)

    schedules: list[_WordSchedule] = []
    for word in all_words:
        if word.id is None:
            continue
        schedules.append(_calc_schedule_for_word(word, events_by_word.get(word.id, []), now))

    buckets = _bucket_and_sort_schedules(schedules)
    # Priority: due review -> not-yet-due review -> new words.
    ranked = buckets.due_words + buckets.review_not_due + buckets.new_words
    selected_words = [item.word for item in ranked]
    logger.debug(
        "SRS selection completed: user_id=%s need=%s selected=%s due=%s new=%s review_not_due=%s model=%s",
        user.id,
        len(all_words),
        len(selected_words),
        len(buckets.due_words),
        len(buckets.new_words),
        len(buckets.review_not_due),
        "gru-hlr" if _PREDICTOR.is_available() else "fallback",
    )
    return selected_words


def select_words_with_srs_priority(session: Session, user: User, all_words: list[Word], num: int) -> list[Word]:
    if num <= 0 or not all_words:
        return []
    if num > len(all_words):
        return []
    ranked_words = rank_words_with_srs_priority(session, user, all_words)
    return ranked_words[:num]


def estimate_word_next_review_days(session: Session, user: User, word: Word) -> float:
    """
    Estimate the next suggested review interval (days) for one word.
    This is used by the combat answer API to display post-answer review hints.
    """
    if word.id is None:
        return 0.0
    now = datetime.now(timezone.utc)
    events_by_word = _load_word_events(session, user, [int(word.id)])
    schedule = _calc_schedule_for_word(word, events_by_word.get(int(word.id), []), now)
    return max(float(schedule.next_interval_days), 0.0)
