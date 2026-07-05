# -*- coding: utf-8 -*-
"""采集账号管理路由：列表 / 扫码登录(SSE) / 删除 / 校验 / 手动刷新 / 仪表盘概览。"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collection.cookie_store import (
    delete_account,
    get_account,
    list_accounts,
    mark_pending_refresh,
)
from app.collection.login_engine import refresh_cookie, start_qrcode_login, validate_account_cookie
from app.core.database import get_db, SessionLocal
from app.models import CollectionAccount, CollectionRun
from app.schemas import (
    CollectionAccountOverview,
    CollectionAccountRead,
)

router = APIRouter(prefix="/collection/accounts", tags=["采集账号"])

_SUPPORTED = {"微博", "快手", "bilibili"}


@router.get("", response_model=list[CollectionAccountRead])
def list_all(db: Session = Depends(get_db)):
    return [CollectionAccountRead.from_account(a) for a in list_accounts(db)]


@router.get("/overview", response_model=list[CollectionAccountOverview])
def overview(db: Session = Depends(get_db)):
    """采集中心仪表盘：各平台账号健康度 + 采集概览 + 最近轮次。"""
    today = datetime.now().date()
    result: list[CollectionAccountOverview] = []
    for platform in ["微博", "快手", "bilibili"]:
        accounts = list_accounts(db, platform)
        valid_count = sum(1 for a in accounts if a.status == "valid")
        if not accounts:
            account_status = "none"
        elif any(a.status == "expired" for a in accounts):
            account_status = "expired"
        elif any(a.status == "pending_refresh" for a in accounts):
            account_status = "pending_refresh"
        else:
            account_status = "valid"

        runs = db.scalars(
            select(CollectionRun)
            .where(CollectionRun.platform == platform)
            .order_by(CollectionRun.created_at.desc())
            .limit(10)
        ).all()
        total_imported = db.scalar(
            select(func.coalesce(func.sum(CollectionRun.imported_count), 0)).where(
                CollectionRun.platform == platform, CollectionRun.status == "completed"
            )
        ) or 0
        total_skipped = db.scalar(
            select(func.coalesce(func.sum(CollectionRun.skipped_count), 0)).where(
                CollectionRun.platform == platform, CollectionRun.status == "completed"
            )
        ) or 0
        today_imported = db.scalar(
            select(func.coalesce(func.sum(CollectionRun.imported_count), 0)).where(
                CollectionRun.platform == platform,
                CollectionRun.status == "completed",
                func.date(CollectionRun.finished_at) == today,
            )
        ) or 0
        last_success = db.scalar(
            select(func.max(CollectionRun.finished_at)).where(
                CollectionRun.platform == platform, CollectionRun.status == "completed"
            )
        )
        recent = [
            {
                "id": r.id,
                "status": r.status,
                "imported": r.imported_count,
                "skipped": r.skipped_count,
                "keyword": r.keyword,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error": r.error_message,
            }
            for r in runs
        ]
        result.append(
            CollectionAccountOverview(
                platform=platform,
                account_status=account_status,
                account_count=len(accounts),
                valid_count=valid_count,
                today_imported=int(today_imported),
                total_imported=int(total_imported),
                total_skipped=int(total_skipped),
                last_success_at=last_success,
                recent_runs=recent,
            )
        )
    return result


@router.get("/login")
async def login(platform: str):
    """扫码登录 SSE 流。前端用 EventSource（仅支持 GET）接收 qrcode/success/timeout/error 事件。

    platform 从 query param 读取：/api/collection/accounts/login?platform=微博
    """
    if platform not in _SUPPORTED:
        raise HTTPException(400, f"不支持的平台，当前仅支持：{', '.join(_SUPPORTED)}")

    async def event_stream():
        try:
            async for event in start_qrcode_login(platform):
                yield f"event: {event['event']}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'message': f'登录引擎异常: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{account_id}")
def remove(account_id: int, db: Session = Depends(get_db)):
    if not delete_account(db, account_id):
        raise HTTPException(404, "账号不存在")
    db.commit()
    return {"ok": True}


@router.post("/{account_id}/validate")
async def validate(account_id: int):
    """用 client.pong 校验 Cookie 有效性，无效则 mark_pending_refresh。"""
    with SessionLocal() as db:
        account = get_account(db, account_id)
        if not account:
            raise HTTPException(404, "账号不存在")
        platform = account.platform

    ok = await validate_account_cookie(platform, account_id)
    return {"valid": ok, "platform": platform}


@router.post("/{account_id}/refresh")
async def manual_refresh(account_id: int):
    """手动触发 Cookie 刷新（backend playwright goto 平台首页）。"""
    with SessionLocal() as db:
        account = get_account(db, account_id)
        if not account:
            raise HTTPException(404, "账号不存在")
        platform = account.platform

    ok = await refresh_cookie(platform, account_id)
    return {"refreshed": ok, "platform": platform}
