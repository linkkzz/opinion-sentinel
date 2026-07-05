from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collection.adapters.base import RawCollectedItem
from app.collection.events import run_event, source_item_event, status_event
from app.collection.normalizer import normalize_item
from app.models import CollectionAccount, CollectionCursor, CollectionEvent, CollectionRun, SourceItem, Task

SUPPORTED_PLATFORMS = {"微博", "快手", "bilibili"}


def _valid_platforms(db: Session) -> set[str]:
    """查有 valid 采集账号的平台集合。没账号的平台不调度采集。

    bilibili 免登录即可采集，始终视为有效。
    """
    valid = set(db.scalars(
        select(CollectionAccount.platform).where(
            CollectionAccount.status == "valid",
            CollectionAccount.cookie_str != "",
        ).distinct()
    ).all())
    valid.add("bilibili")  # bilibili 免登录优先
    return valid


def active_collection_task(task: Task, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return (
        task.status == "running"
        and task.collection_enabled
        and task.collection_state != "paused"
        and (task.end_time is None or task.end_time >= now)
    )


def ensure_cursors(db: Session, task: Task, *, force_due: bool = False) -> list[CollectionCursor]:
    if not task.collection_enabled:
        return []
    existing = {
        (cursor.platform, cursor.keyword): cursor
        for cursor in db.scalars(select(CollectionCursor).where(CollectionCursor.task_id == task.id)).all()
    }
    result: list[CollectionCursor] = []
    for platform in task.platforms or []:
        if platform not in SUPPORTED_PLATFORMS:
            continue
        for keyword in task.keywords or []:
            key = (platform, keyword)
            cursor = existing.get(key)
            if not cursor:
                cursor = CollectionCursor(task_id=task.id, platform=platform, keyword=keyword, next_run_at=datetime.now())
                db.add(cursor)
                db.flush()
            elif force_due:
                cursor.next_run_at = datetime.now()
            result.append(cursor)
    return result


def enqueue_due_runs(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now()
    valid = _valid_platforms(db)
    queued = 0
    tasks = db.scalars(select(Task).where(Task.status == "running", Task.collection_enabled.is_(True))).all()
    for task in tasks:
        if not active_collection_task(task, now):
            if task.collection_state not in {"paused", "stopped"}:
                task.collection_state = "stopped" if task.end_time and task.end_time < now else "idle"
            continue
        # error 状态但有 valid 账号 → 重置为 idle 允许重试（cookie_refresher 已恢复）
        if task.collection_state == "error" and any(p in valid for p in (task.platforms or [])):
            task.collection_state = "idle"
        cursors = ensure_cursors(db, task)
        for cursor in cursors:
            # 没账号的平台不创建 run，推迟 next_run_at 避免反复检查
            if cursor.platform not in valid:
                if cursor.next_run_at is None or cursor.next_run_at <= now:
                    cursor.next_run_at = now + timedelta(seconds=max(60, task.collection_interval_seconds or 300))
                continue
            if cursor.next_run_at is not None and cursor.next_run_at > now:
                continue
            exists = db.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.task_id == task.id,
                    CollectionRun.platform == cursor.platform,
                    CollectionRun.keyword == cursor.keyword,
                    CollectionRun.status.in_(["queued", "running"]),
                )
            )
            if exists:
                continue
            run = CollectionRun(task_id=task.id, platform=cursor.platform, keyword=cursor.keyword, status="queued")
            db.add(run)
            cursor.next_run_at = now + timedelta(seconds=max(60, task.collection_interval_seconds or 300))
            queued += 1
        if queued and task.collection_state not in {"paused", "error"}:
            task.collection_state = "queued"
    if queued:
        db.flush()
    return queued


def enqueue_task_now(db: Session, task: Task) -> int:
    valid = _valid_platforms(db)
    cursors = ensure_cursors(db, task, force_due=True)
    queued = 0
    for cursor in cursors:
        if cursor.platform not in valid:
            continue
        exists = db.scalar(
            select(CollectionRun.id).where(
                CollectionRun.task_id == task.id,
                CollectionRun.platform == cursor.platform,
                CollectionRun.keyword == cursor.keyword,
                CollectionRun.status.in_(["queued", "running"]),
            )
        )
        if exists:
            continue
        db.add(CollectionRun(task_id=task.id, platform=cursor.platform, keyword=cursor.keyword, status="queued"))
        queued += 1
    task.collection_state = "queued" if queued else task.collection_state
    return queued


def claim_next_run(db: Session) -> CollectionRun | None:
    run = db.scalar(select(CollectionRun).where(CollectionRun.status == "queued").order_by(CollectionRun.created_at).limit(1))
    if not run:
        return None
    task = db.get(Task, run.task_id)
    if not task or not active_collection_task(task):
        run.status = "skipped"
        run.finished_at = datetime.now()
        run.error_message = "任务未处于持续监测状态"
        db.add(run_event(run, "collection.run_skipped"))
        return None
    run.status = "running"
    run.started_at = datetime.now()
    task.collection_state = "collecting"
    db.add(status_event(task.id, "collection.status_changed", {"state": task.collection_state}, run.id))
    return run


def cursor_for_run(db: Session, run: CollectionRun) -> CollectionCursor | None:
    return db.scalar(
        select(CollectionCursor).where(
            CollectionCursor.task_id == run.task_id,
            CollectionCursor.platform == run.platform,
            CollectionCursor.keyword == run.keyword,
        )
    )


def _refresh_demo_item(item: SourceItem, payload: dict) -> bool:
    """已废弃：demo 模式已移除。保留空实现避免外部引用报错，真实数据不会进入此分支。"""
    return False


def insert_items(db: Session, task_id: int, items: list[RawCollectedItem]) -> tuple[int, int, datetime | None]:
    imported = skipped = 0
    latest_external_time: datetime | None = None
    for raw in items:
        payload = normalize_item(raw)
        existing_item = db.scalar(
            select(SourceItem).where(SourceItem.task_id == task_id, SourceItem.dedupe_key == payload["dedupe_key"])
        )
        if existing_item:
            _refresh_demo_item(existing_item, payload)
            skipped += 1
            if existing_item.publish_time and (
                latest_external_time is None or existing_item.publish_time > latest_external_time
            ):
                latest_external_time = existing_item.publish_time
            continue
        item = SourceItem(task_id=task_id, **payload)
        db.add(item)
        try:
            db.flush()
            db.add(source_item_event(item))
            imported += 1
            if item.publish_time and (latest_external_time is None or item.publish_time > latest_external_time):
                latest_external_time = item.publish_time
        except IntegrityError:
            db.rollback()
            skipped += 1
    return imported, skipped, latest_external_time


def finish_run(db: Session, run: CollectionRun, imported: int, skipped: int, latest_external_time: datetime | None) -> None:
    now = datetime.now()
    run.status = "completed"
    run.finished_at = now
    run.imported_count = imported
    run.skipped_count = skipped
    cursor = cursor_for_run(db, run)
    task = db.get(Task, run.task_id)
    if cursor:
        cursor.last_success_at = now
        cursor.failure_count = 0
        if latest_external_time and (cursor.last_external_time is None or latest_external_time > cursor.last_external_time):
            cursor.last_external_time = latest_external_time
        if task:
            cursor.next_run_at = now + timedelta(seconds=max(60, task.collection_interval_seconds or 300))
    if task and task.collection_state != "paused":
        task.collection_state = "waiting"
        db.add(status_event(task.id, "collection.status_changed", {"state": task.collection_state}, run.id))
    db.add(run_event(run, "collection.run_completed"))


def fail_run(db: Session, run: CollectionRun, error: str) -> None:
    now = datetime.now()
    run.status = "failed"
    run.finished_at = now
    run.error_message = error[:2000]
    cursor = cursor_for_run(db, run)
    if cursor:
        cursor.failure_count += 1
        cursor.next_run_at = now + timedelta(minutes=min(30, 2 * max(1, cursor.failure_count)))
    task = db.get(Task, run.task_id)
    if task:
        task.collection_state = "error"
        db.add(status_event(task.id, "collection.status_changed", {"state": "error", "error": error[:500]}, run.id))
    db.add(run_event(run, "collection.run_failed"))


def collection_totals(db: Session, task_id: int) -> dict[str, int | datetime | None]:
    today = datetime.now().date()
    rows = db.execute(
        select(
            func.coalesce(func.sum(CollectionRun.imported_count), 0),
            func.coalesce(func.sum(CollectionRun.skipped_count), 0),
            func.max(CollectionRun.finished_at),
        ).where(CollectionRun.task_id == task_id, CollectionRun.status == "completed")
    ).one()
    today_imported = db.scalar(
        select(func.coalesce(func.sum(CollectionRun.imported_count), 0)).where(
            CollectionRun.task_id == task_id,
            CollectionRun.status == "completed",
            func.date(CollectionRun.finished_at) == today,
        )
    ) or 0
    current_round = db.scalar(
        select(func.coalesce(func.sum(CollectionRun.imported_count), 0)).where(
            CollectionRun.task_id == task_id,
            CollectionRun.status == "completed",
            CollectionRun.finished_at == rows[2],
        )
    ) or 0
    return {
        "total_imported": int(rows[0]),
        "total_skipped": int(rows[1]),
        "latest_success_at": rows[2],
        "today_imported": int(today_imported),
        "current_round_imported": int(current_round),
    }


def latest_events(db: Session, task_id: int, after_id: int = 0, limit: int = 50) -> list[CollectionEvent]:
    return db.scalars(
        select(CollectionEvent)
        .where(CollectionEvent.task_id == task_id, CollectionEvent.id > after_id)
        .order_by(CollectionEvent.id)
        .limit(limit)
    ).all()
