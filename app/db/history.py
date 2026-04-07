from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_
from sqlmodel import Session, select

from app.db.daily_challenge import get_current_daily_question_for_run
from app.models.challenge import Challenge, ChallengeStatus
from app.models.daily_challenge import (
    DailyChallengeAnswer,
    DailyChallengeDay,
    DailyChallengeFloorQuestion,
    DailyChallengeRun,
    DailyChallengeRunStatus,
)
from app.models.history import HistoryAnswerRead, HistoryQuestionRead, HistoryRunDetail, HistoryRunSummary
from app.models.level import Level
from app.models.level_question_link import LevelQuestionLink
from app.models.question import Question
from app.models.user import User
from app.models.user_question_record import UserQuestionRecord


@dataclass
class TowerHistoryRunBundle:
    rows: list[tuple[Challenge, int]]

    @property
    def last_challenge(self) -> Challenge:
        return self.rows[-1][0]

    @property
    def floors(self) -> list[int]:
        return [floor for _, floor in self.rows]


def _build_tower_run_ref(run_id: int) -> str:
    return f"tower-{run_id}"


def _build_daily_run_ref(run_id: int) -> str:
    return f"daily-{run_id}"


def _parse_history_run_ref(run_ref: str) -> tuple[str, int] | None:
    normalized = str(run_ref).strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return "tower", int(normalized)
    if normalized.startswith("tower-") and normalized[6:].isdigit():
        return "tower", int(normalized[6:])
    if normalized.startswith("daily-") and normalized[6:].isdigit():
        return "daily_challenge", int(normalized[6:])
    return None


def _group_tower_challenge_rows(rows: Iterable[tuple[Challenge, int]]) -> list[TowerHistoryRunBundle]:
    runs: list[list[tuple[Challenge, int]]] = []
    current_run: list[tuple[Challenge, int]] = []
    previous_floor: int | None = None

    for challenge, floor in rows:
        if floor is None:
            continue

        if not current_run:
            current_run.append((challenge, floor))
        elif floor == 1 or (previous_floor is not None and floor != previous_floor + 1):
            runs.append(current_run)
            current_run = [(challenge, floor)]
        else:
            current_run.append((challenge, floor))

        previous_floor = floor

    if current_run:
        runs.append(current_run)

    return [TowerHistoryRunBundle(rows=run) for run in runs]


def _get_tower_run_status(challenge: Challenge) -> str:
    if challenge.status == ChallengeStatus.IN_PROGRESS:
        return "in_progress"
    if challenge.end_hp is not None and challenge.end_hp <= 0:
        return "failed"
    return "completed"


def _get_daily_run_status(run: DailyChallengeRun) -> str:
    if run.status == DailyChallengeRunStatus.IN_PROGRESS:
        return "in_progress"
    if run.status == DailyChallengeRunStatus.DEAD:
        return "failed"
    return "completed"


def _build_tower_run_summary(
    bundle: TowerHistoryRunBundle,
    question_count_by_level: dict[int, int],
) -> HistoryRunSummary:
    last_challenge = bundle.last_challenge
    status = _get_tower_run_status(last_challenge)

    return HistoryRunSummary(
        run_ref=_build_tower_run_ref(last_challenge.id),
        run_id=last_challenge.id,
        mode="tower",
        status=status,
        started_at=bundle.rows[0][0].start_time,
        ended_at=last_challenge.end_time,
        highest_floor=max(bundle.floors) if bundle.floors else 0,
        current_floor=bundle.floors[-1] if status == "in_progress" and bundle.floors else None,
        total_exp=sum(challenge.exp_gained for challenge, _ in bundle.rows),
        total_coins=sum(challenge.coins_gained for challenge, _ in bundle.rows),
        question_count=sum(question_count_by_level.get(challenge.level_id, 0) for challenge, _ in bundle.rows),
        last_hp=last_challenge.end_hp,
    )


def _build_daily_run_summary(
    run: DailyChallengeRun,
    day: DailyChallengeDay,
    answer_count: int,
) -> HistoryRunSummary:
    status = _get_daily_run_status(run)
    question_count = answer_count + (1 if status == "in_progress" else 0)
    return HistoryRunSummary(
        run_ref=_build_daily_run_ref(run.id),
        run_id=run.id,
        mode="daily_challenge",
        status=status,
        day_key=day.day_key,
        started_at=run.started_at,
        ended_at=run.ended_at,
        highest_floor=run.best_floor,
        current_floor=run.current_floor if status == "in_progress" else None,
        total_exp=0,
        total_coins=0,
        question_count=question_count,
        last_hp=run.current_hp,
    )


def _build_sort_time(summary: HistoryRunSummary):
    value = summary.started_at or summary.ended_at
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.timestamp()


def _index_first_records_by_question(records: Iterable[UserQuestionRecord]) -> dict[int, UserQuestionRecord]:
    first_record_by_question: dict[int, UserQuestionRecord] = {}
    for record in records:
        if record.question_id not in first_record_by_question:
            first_record_by_question[record.question_id] = record
    return first_record_by_question


def _list_user_tower_challenge_rows(session: Session, user: User) -> list[tuple[Challenge, int]]:
    statement = (
        select(Challenge, Level.floor)
        .join(Level, Challenge.level_id == Level.id)
        .where(Challenge.user_id == user.id)
        .order_by(Challenge.start_time.asc(), Challenge.id.asc())
    )
    return list(session.exec(statement).all())


def _list_user_daily_runs(session: Session, user: User) -> list[tuple[DailyChallengeRun, DailyChallengeDay]]:
    statement = (
        select(DailyChallengeRun, DailyChallengeDay)
        .join(DailyChallengeDay, DailyChallengeRun.day_id == DailyChallengeDay.id)
        .where(DailyChallengeRun.user_id == user.id)
        .order_by(DailyChallengeRun.started_at.asc(), DailyChallengeRun.id.asc())
    )
    return list(session.exec(statement).all())


def list_history_runs(session: Session, user: User) -> list[HistoryRunSummary]:
    tower_rows = _list_user_tower_challenge_rows(session, user)
    tower_bundles = _group_tower_challenge_rows(tower_rows)

    level_ids = [challenge.level_id for bundle in tower_bundles for challenge, _ in bundle.rows]
    question_count_by_level: dict[int, int] = {}
    if level_ids:
        level_question_rows = session.exec(
            select(LevelQuestionLink.level_id).where(LevelQuestionLink.level_id.in_(level_ids))
        ).all()
        for level_id in level_question_rows:
            question_count_by_level[level_id] = question_count_by_level.get(level_id, 0) + 1

    summaries = [_build_tower_run_summary(bundle, question_count_by_level) for bundle in tower_bundles]

    daily_rows = _list_user_daily_runs(session, user)
    run_ids = [run.id for run, _ in daily_rows]
    answer_count_by_run: dict[int, int] = {}
    if run_ids:
        answer_run_ids = session.exec(
            select(DailyChallengeAnswer.run_id).where(DailyChallengeAnswer.run_id.in_(run_ids))
        ).all()
        for run_id in answer_run_ids:
            answer_count_by_run[run_id] = answer_count_by_run.get(run_id, 0) + 1

    summaries.extend(
        _build_daily_run_summary(run, day, answer_count_by_run.get(run.id, 0))
        for run, day in daily_rows
    )

    summaries.sort(key=_build_sort_time, reverse=True)
    return summaries


def _get_tower_history_run_detail(session: Session, user: User, run_id: int) -> HistoryRunDetail | None:
    rows = _list_user_tower_challenge_rows(session, user)
    bundles = _group_tower_challenge_rows(rows)
    target_bundle = next((bundle for bundle in bundles if bundle.last_challenge.id == run_id), None)
    if target_bundle is None:
        return None

    level_ids = [challenge.level_id for challenge, _ in target_bundle.rows]
    level_floor_map = {challenge.level_id: floor for challenge, floor in target_bundle.rows}
    question_count_by_level: dict[int, int] = {}
    question_rows: list[tuple[LevelQuestionLink, Question]] = []

    if level_ids:
        statement = (
            select(LevelQuestionLink, Question)
            .join(Question, LevelQuestionLink.question_id == Question.id)
            .where(LevelQuestionLink.level_id.in_(level_ids))
        )
        question_rows = list(session.exec(statement).all())
        for link, _ in question_rows:
            question_count_by_level[link.level_id] = question_count_by_level.get(link.level_id, 0) + 1

    run_summary = _build_tower_run_summary(target_bundle, question_count_by_level)

    question_ids = [link.question_id for link, _ in question_rows]
    first_records_by_question: dict[int, UserQuestionRecord] = {}
    if question_ids:
        records_statement = (
            select(UserQuestionRecord)
            .where(UserQuestionRecord.user_id == user.id)
            .where(UserQuestionRecord.question_id.in_(question_ids))
            .where(UserQuestionRecord.time >= (run_summary.started_at or target_bundle.rows[0][0].start_time))
            .order_by(UserQuestionRecord.time.asc(), UserQuestionRecord.id.asc())
        )
        if run_summary.ended_at is not None:
            records_statement = records_statement.where(UserQuestionRecord.time <= run_summary.ended_at)

        first_records_by_question = _index_first_records_by_question(session.exec(records_statement).all())

    question_rows.sort(
        key=lambda row: (
            level_floor_map.get(row[0].level_id, 0),
            row[0].order_index if row[0].order_index is not None else 10**6,
            row[0].id or 0,
        )
    )

    questions: list[HistoryQuestionRead] = []
    for index, (link, question) in enumerate(question_rows, start=1):
        first_record = first_records_by_question.get(question.id)
        questions.append(
            HistoryQuestionRead(
                question_id=question.id,
                order_index=index,
                floor=level_floor_map.get(link.level_id, 0),
                question_index=link.order_index,
                level_id=link.level_id,
                question_type=question.type,
                content=question.content,
                first_answer=HistoryAnswerRead(
                    id=first_record.id,
                    answered_at=first_record.time,
                    correct=first_record.correct,
                    answer_detail=first_record.answer_detail,
                    rating=first_record.rating,
                    report=first_record.report,
                )
                if first_record is not None
                else None,
            )
        )

    return HistoryRunDetail(run=run_summary, questions=questions)


def _get_daily_history_run_detail(session: Session, user: User, run_id: int) -> HistoryRunDetail | None:
    statement = (
        select(DailyChallengeRun, DailyChallengeDay)
        .join(DailyChallengeDay, DailyChallengeRun.day_id == DailyChallengeDay.id)
        .where(DailyChallengeRun.id == run_id)
        .where(DailyChallengeRun.user_id == user.id)
    )
    row = session.exec(statement).first()
    if row is None:
        return None

    run, day = row
    answer_count = session.exec(
        select(DailyChallengeAnswer.run_id).where(DailyChallengeAnswer.run_id == run.id)
    ).all()
    run_summary = _build_daily_run_summary(run, day, len(answer_count))

    answered_rows = session.exec(
        select(DailyChallengeAnswer, DailyChallengeFloorQuestion, Question)
        .join(
            DailyChallengeFloorQuestion,
            and_(
                DailyChallengeFloorQuestion.day_id == run.day_id,
                DailyChallengeFloorQuestion.floor == DailyChallengeAnswer.floor,
                DailyChallengeFloorQuestion.question_index == DailyChallengeAnswer.question_index,
                DailyChallengeFloorQuestion.question_id == DailyChallengeAnswer.question_id,
            ),
        )
        .join(Question, Question.id == DailyChallengeFloorQuestion.question_id)
        .where(DailyChallengeAnswer.run_id == run.id)
        .order_by(
            DailyChallengeFloorQuestion.floor.asc(),
            DailyChallengeFloorQuestion.question_index.asc(),
            DailyChallengeAnswer.answered_at.asc(),
            DailyChallengeAnswer.id.asc(),
        )
    ).all()

    question_items: dict[tuple[int, int, int], HistoryQuestionRead] = {}

    for answer, floor_question, question in answered_rows:
        key = (floor_question.floor, floor_question.question_index, question.id)
        if key in question_items:
            continue
        question_items[key] = HistoryQuestionRead(
            question_id=question.id,
            order_index=0,
            floor=floor_question.floor,
            question_index=floor_question.question_index,
            level_id=None,
            question_type=question.type,
            content=question.content,
            first_answer=HistoryAnswerRead(
                id=answer.id,
                answered_at=answer.answered_at,
                correct=answer.is_correct,
                answer_detail=answer.answer_detail,
                rating=None,
                report=None,
            ),
        )

    current_floor_question, current_question = get_current_daily_question_for_run(session, run)
    if current_floor_question is not None and current_question is not None:
        current_key = (
            current_floor_question.floor,
            current_floor_question.question_index,
            current_question.id,
        )
        question_items.setdefault(
            current_key,
            HistoryQuestionRead(
                question_id=current_question.id,
                order_index=0,
                floor=current_floor_question.floor,
                question_index=current_floor_question.question_index,
                level_id=None,
                question_type=current_question.type,
                content=current_question.content,
                first_answer=None,
            ),
        )

    sorted_questions = sorted(
        question_items.values(),
        key=lambda item: (
            item.floor,
            item.question_index if item.question_index is not None else 10**6,
            item.question_id,
        ),
    )

    for index, question in enumerate(sorted_questions, start=1):
        question.order_index = index

    return HistoryRunDetail(run=run_summary, questions=sorted_questions)


def get_history_run_detail(session: Session, user: User, run_ref: str) -> HistoryRunDetail | None:
    parsed = _parse_history_run_ref(run_ref)
    if parsed is None:
        return None

    mode, run_id = parsed
    if mode == "tower":
        return _get_tower_history_run_detail(session, user, run_id)
    if mode == "daily_challenge":
        return _get_daily_history_run_detail(session, user, run_id)
    return None
