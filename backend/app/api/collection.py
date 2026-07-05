from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.items import _serialize_item
from app.collection.repository import SUPPORTED_PLATFORMS, enqueue_task_now, latest_events
from app.core.database import get_db, SessionLocal
from app.models import CollectionAccount, CollectionCursor, CollectionRun, SourceItem, Task
from app.schemas import CollectionPlatformStatus, CollectionRunRead, CollectionStatusRead

router = APIRouter(prefix="/tasks/{task_id}/collection", tags=["持续监测"])
global_router = APIRouter(prefix="/collection", tags=["持续监测"])


def _task_or_404(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


def _platform_state(task: Task, platform: str, latest_run: CollectionRun | None, latest_cursor: CollectionCursor | None, account_status: str) -> str:
    if platform not in SUPPORTED_PLATFORMS:
        return "unsupported"
    if account_status == "none":
        return "no_account"
    if account_status in ("pending_refresh", "login_pending"):
        return "refreshing"
    if account_status == "expired":
        return "expired"
    if not task.collection_enabled:
        return "disabled"
    if task.collection_state == "paused":
        return "paused"
    if latest_run and latest_run.status in {"queued", "running"}:
        return latest_run.status
    if latest_run and latest_run.status == "failed":
        if latest_run.error_message and "无可用" in latest_run.error_message:
            pass
        elif "风控" in (latest_run.error_message or "") or "Cookie" in (latest_run.error_message or ""):
            # 风控导致 failed，但账号已恢复 valid → 等待下一轮重试
            return "waiting" if account_status == "valid" else "refreshing"
        else:
            return "failed"
    if task.collection_state == "error" and account_status == "valid":
        # error 状态但账号已恢复，允许重试
        return "waiting"
    if latest_cursor and latest_cursor.next_run_at and latest_cursor.next_run_at > datetime.now():
        return "waiting"
    return task.collection_state or "idle"


@router.get("/status", response_model=CollectionStatusRead)
def collection_status(task_id: int, db: Session = Depends(get_db)):
    task = _task_or_404(db, task_id)
    platforms = list(dict.fromkeys(task.platforms or []))
    # 查每个平台的账号状态：valid > pending_refresh > expired > none
    platform_account_status: dict[str, str] = {}
    for platform in platforms:
        # bilibili 免登录优先，无账号也能采集
        if platform == "bilibili":
            platform_account_status[platform] = "valid"
            continue
        accounts = db.scalars(
            select(CollectionAccount).where(CollectionAccount.platform == platform)
        ).all()
        if not accounts:
            platform_account_status[platform] = "none"
        elif any(a.status == "valid" for a in accounts):
            platform_account_status[platform] = "valid"
        elif any(a.status in ("pending_refresh", "login_pending") for a in accounts):
            platform_account_status[platform] = "pending_refresh"
        elif any(a.status == "expired" for a in accounts):
            platform_account_status[platform] = "expired"
        else:
            platform_account_status[platform] = "none"
    run_rows = db.scalars(
        select(CollectionRun).where(CollectionRun.task_id == task_id).order_by(CollectionRun.created_at.desc())
    ).all()
    latest_by_platform: dict[str, CollectionRun] = {}
    for run in run_rows:
        latest_by_platform.setdefault(run.platform, run)
    cursor_rows = db.scalars(select(CollectionCursor).where(CollectionCursor.task_id == task_id)).all()
    cursors_by_platform: dict[str, list[CollectionCursor]] = {}
    for cursor in cursor_rows:
        cursors_by_platform.setdefault(cursor.platform, []).append(cursor)

    today = datetime.now().date()
    current_round_imported = 0
    latest_success_at = None
    next_run_at = None
    platform_payload: list[CollectionPlatformStatus] = []
    for platform in platforms:
        latest_run = latest_by_platform.get(platform)
        platform_runs = [run for run in run_rows if run.platform == platform]
        cursors = cursors_by_platform.get(platform, [])
        platform_success = [cursor.last_success_at for cursor in cursors if cursor.last_success_at]
        platform_next = [cursor.next_run_at for cursor in cursors if cursor.next_run_at]
        latest_success = max(platform_success) if platform_success else None
        if latest_success and (latest_success_at is None or latest_success > latest_success_at):
            latest_success_at = latest_success
        if platform_next:
            candidate = min(platform_next)
            if next_run_at is None or candidate < next_run_at:
                next_run_at = candidate
        imported_total = sum(run.imported_count for run in platform_runs if run.status == "completed")
        skipped_total = sum(run.skipped_count for run in platform_runs if run.status == "completed")
        latest_imported = latest_run.imported_count if latest_run else 0
        if latest_run and latest_run.status == "completed" and latest_run.finished_at == latest_success_at:
            current_round_imported += latest_run.imported_count
        state = _platform_state(task, platform, latest_run, cursors[0] if cursors else None, platform_account_status.get(platform, "none"))
        error_msg = latest_run.error_message if latest_run and latest_run.status == "failed" and state == "failed" else None
        if state == "no_account":
            error_msg = f"无可用{platform}采集账号，请在采集中心添加账号并扫码登录"
        elif state == "refreshing":
            error_msg = f"{platform} Cookie 正在自动刷新，稍后将恢复采集"
        elif state == "expired":
            error_msg = f"{platform} 账号已过期，请前往采集中心重新扫码登录"
        platform_payload.append(
            CollectionPlatformStatus(
                platform=platform,
                state=state,
                latest_run=CollectionRunRead.model_validate(latest_run) if latest_run else None,
                latest_success_at=latest_success,
                next_run_at=min(platform_next) if platform_next else None,
                imported_total=imported_total,
                skipped_total=skipped_total,
                latest_imported=latest_imported,
                error_message=error_msg,
            )
        )

    total_imported = sum(run.imported_count for run in run_rows if run.status == "completed")
    today_imported = sum(
        run.imported_count
        for run in run_rows
        if run.status == "completed" and run.finished_at and run.finished_at.date() == today
    )
    if task.collection_state == "idle" and any(run.status == "running" for run in run_rows):
        state = "collecting"
    else:
        state = task.collection_state
    return CollectionStatusRead(
        task_id=task.id,
        enabled=task.collection_enabled,
        state=state,
        interval_seconds=task.collection_interval_seconds,
        current_round_imported=current_round_imported,
        today_imported=today_imported,
        total_imported=total_imported,
        latest_success_at=latest_success_at,
        next_run_at=next_run_at,
        platforms=platform_payload,
    )


@router.get("/feed")
def collection_feed(task_id: int, page_size: int = 30, db: Session = Depends(get_db)):
    _task_or_404(db, task_id)
    items = db.scalars(
        select(SourceItem)
        .where(SourceItem.task_id == task_id)
        .options(selectinload(SourceItem.media))
        .order_by(SourceItem.created_at.desc(), SourceItem.id.desc())
        .limit(min(page_size, 100))
    ).all()
    total = db.scalar(select(func.count(SourceItem.id)).where(SourceItem.task_id == task_id)) or 0
    return {"total": total, "items": [_serialize_item(item, db) for item in items]}


@router.post("/run-now")
def run_now(task_id: int, db: Session = Depends(get_db)):
    task = _task_or_404(db, task_id)
    if task.status != "running":
        raise HTTPException(409, "已完结任务不能采集")
    if not task.collection_enabled:
        task.collection_enabled = True
    if task.collection_state == "paused":
        task.collection_state = "queued"
    queued = enqueue_task_now(db, task)
    db.commit()
    return {"queued": queued, "collection_state": task.collection_state}


@router.post("/pause")
def pause_collection(task_id: int, db: Session = Depends(get_db)):
    task = _task_or_404(db, task_id)
    task.collection_state = "paused"
    db.commit()
    return {"collection_state": task.collection_state}


@router.post("/resume")
def resume_collection(task_id: int, db: Session = Depends(get_db)):
    task = _task_or_404(db, task_id)
    if task.status != "running":
        raise HTTPException(409, "已完结任务不能恢复持续监测")
    task.collection_enabled = True
    task.collection_state = "idle"
    queued = enqueue_task_now(db, task)
    db.commit()
    return {"queued": queued, "collection_state": task.collection_state}


@router.get("/stream")
async def collection_stream(task_id: int, after_id: int = 0):
    async def event_generator():
        last_id = after_id
        while True:
            with SessionLocal() as db:
                task = db.get(Task, task_id)
                if not task:
                    yield "event: error\ndata: {\"detail\":\"任务不存在\"}\n\n"
                    return
                events = latest_events(db, task_id, last_id)
                for event in events:
                    last_id = event.id
                    payload = {"id": event.id, "type": event.event_type, "payload": event.payload}
                    yield f"id: {event.id}\nevent: {event.event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@global_router.get("/feed")
def global_collection_feed(page_size: int = 20, db: Session = Depends(get_db)):
    """全局最新入库内容（跨任务跨平台），按 created_at desc。供采集中心"最新入库预览"使用。

    返回的每条 item 额外带 task_name 字段，便于前端区分来源。
    """
    items = db.scalars(
        select(SourceItem)
        .options(selectinload(SourceItem.media))
        .order_by(SourceItem.created_at.desc(), SourceItem.id.desc())
        .limit(min(page_size, 100))
    ).all()
    total = db.scalar(select(func.count(SourceItem.id))) or 0
    # 预取 task_name 映射，避免 N+1
    task_ids = {item.task_id for item in items}
    task_names: dict[int, str] = {}
    if task_ids:
        for task in db.scalars(select(Task).where(Task.id.in_(task_ids))).all():
            task_names[task.id] = task.name
    result = []
    for item in items:
        payload = _serialize_item(item, db).model_dump()
        payload["task_name"] = task_names.get(item.task_id, "")
        result.append(payload)
    return {"total": total, "items": result}
