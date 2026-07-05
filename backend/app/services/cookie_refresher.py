# -*- coding: utf-8 -*-
"""Cookie 按需刷新后台任务。

轮询 status=pending_refresh 的采集账号，调用 login_engine.refresh_cookie 用
playwright goto 平台首页刷新 Cookie。按需刷新策略（非定期预防）。
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import CollectionAccount

logger = logging.getLogger(__name__)

async def cookie_refresh_loop(stop_event: asyncio.Event) -> None:
    """后台循环：每 collection_cookie_refresh_interval 秒扫描 pending_refresh 账号。"""
    from app.collection.login_engine import refresh_cookie

    logger.info("[cookie_refresher] Cookie 刷新后台任务已启动")
    while not stop_event.is_set():
        try:
            pending: list[tuple[int, str]] = []
            with SessionLocal() as db:
                rows = db.scalars(
                    select(CollectionAccount).where(CollectionAccount.status == "pending_refresh")
                ).all()
                pending = [(r.id, r.platform) for r in rows]

            for account_id, platform in pending:
                try:
                    await refresh_cookie(platform, account_id)
                except Exception as exc:
                    logger.error(f"[cookie_refresher] 刷新 {platform}#{account_id} 失败: {exc}")
        except Exception as exc:
            logger.error(f"[cookie_refresher] 轮询异常: {exc}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.collection_cookie_refresh_interval)
        except asyncio.TimeoutError:
            pass
    logger.info("[cookie_refresher] Cookie 刷新后台任务已停止")
