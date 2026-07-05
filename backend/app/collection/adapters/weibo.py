# -*- coding: utf-8 -*-
"""微博采集 Adapter：混合采集模式（httpx + playwright 风控恢复）。

采集流程（复刻 MediaCrawler weibo/core.py:69-190 混合模式）：
  1. 从 CollectionAccount 取 valid Cookie；无则 raise
  2. 启动 headless 浏览器 + 注入旧 Cookie + goto m.weibo.cn 让浏览器吸收 Set-Cookie
  3. 从浏览器 context 同步最新 Cookie 到 httpx client（update_cookies）
  4. pong 预检：Cookie 失效 → mark_pending_refresh + raise
  5. 分页搜索，WeiboClient 持有 playwright_page，432 时自动 goto+update_cookies 恢复
  6. 采集成功后回写最新 Cookie 到 DB
  7. finally 关闭浏览器
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

from app.collection.adapters.base import RawCollectedItem
from app.collection.cookie_store import get_valid_cookie, mark_pending_refresh, mark_valid
from app.collection.platforms._shared import DataFetchError, launch_collection_browser, rfc2822_to_timestamp, update_cookies_from_context
from app.collection.platforms.weibo import WeiboClient
from app.collection.platforms.weibo_field import SearchType
from app.collection.platforms.weibo_help import filter_search_result_card
from app.core.config import settings
from app.core.database import SessionLocal


class WeiboAdapter:
    platform = "微博"

    async def collect(
        self,
        *,
        keyword: str,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[RawCollectedItem]:
        # 取有效 Cookie
        with SessionLocal() as db:
            account = get_valid_cookie(db, self.platform)
            if not account:
                raise RuntimeError(f"无可用{self.platform}采集账号，请在采集中心添加账号并扫码登录")
            cookie_str = account.cookie_str
            account_id = account.id

        results: list[RawCollectedItem] = []
        async with async_playwright() as playwright:
            browser, context, page = await launch_collection_browser(
                playwright, headless=settings.collection_login_headless
            )
            try:
                # 注入旧 Cookie 到浏览器（复刻 weibo/login.py:124-132 login_by_cookies）
                from app.collection.platforms._shared import convert_str_cookie_to_dict
                cookie_list = [
                    {"name": k, "value": v, "domain": ".weibo.cn", "path": "/"}
                    for k, v in convert_str_cookie_to_dict(cookie_str).items()
                ]
                if cookie_list:
                    await context.add_cookies(cookie_list)

                # goto m.weibo.cn 让浏览器吸收 server 轮换的 Set-Cookie（cookie 保鲜核心）
                await page.goto("https://m.weibo.cn", wait_until="domcontentloaded")
                await asyncio.sleep(2)

                # 创建 client 并持有 playwright_page（432 恢复依赖）
                client = WeiboClient(cookie_str, playwright_page=page)
                # 从浏览器同步最新 Cookie 到 httpx headers
                await update_cookies_from_context(context, client, ["https://m.weibo.cn"])

                # pong 预检
                if not await client.pong():
                    with SessionLocal() as db:
                        mark_pending_refresh(db, account_id)
                        db.commit()
                    raise RuntimeError(f"{self.platform} Cookie 已失效，已标记待刷新")

                # 分页搜索（最大 5 页，避免无限翻页）
                page_num = 1
                max_pages = 5
                while len(results) < limit and page_num <= max_pages:
                    data = await client.get_note_by_keyword(keyword, page_num, SearchType.DEFAULT)
                    cards = filter_search_result_card(data.get("cards", []))
                    if not cards:
                        break
                    for card in cards:
                        mblog = card.get("mblog")
                        if not mblog:
                            continue
                        item = self._mblog_to_raw(mblog, keyword)
                        if item and self._within_range(item, since, until):
                            results.append(item)
                        if len(results) >= limit:
                            break
                    page_num += 1
                    await asyncio.sleep(settings.collection_request_sleep)

                # 采集成功后回写最新 Cookie 到 DB（浏览器吸收的新 cookie）
                if results and client.cookie_str != cookie_str:
                    with SessionLocal() as db:
                        mark_valid(db, account_id, cookie_str=client.cookie_str)
                        db.commit()
            except DataFetchError as exc:
                # 432 风控 5 次重试仍失败 → 标记刷新
                with SessionLocal() as db:
                    mark_pending_refresh(db, account_id)
                    db.commit()
                if results:
                    return results[:limit]
                raise RuntimeError(f"{self.platform} 采集遇风控：{exc}") from exc
            finally:
                await context.close()
                await browser.close()

        return results[:limit]

    @staticmethod
    def _mblog_to_raw(mblog: dict, keyword: str) -> Optional[RawCollectedItem]:
        """mblog → RawCollectedItem。字段映射复刻 store/weibo/__init__.py:86-106。"""
        note_id = str(mblog.get("id") or "")
        if not note_id:
            return None
        content_html = mblog.get("text", "")
        content = re.sub(r"<.*?>", "", content_html)
        user_info = mblog.get("user") or {}
        try:
            publish_time = datetime.fromtimestamp(rfc2822_to_timestamp(mblog.get("created_at") or ""))
        except Exception:
            publish_time = None
        return RawCollectedItem(
            platform="微博",
            external_id=note_id,
            title=content[:48] if content else "无标题",
            author=user_info.get("screen_name", "未知"),
            publish_time=publish_time,
            content=content,
            source_url=f"https://m.weibo.cn/detail/{note_id}",
            like_count=max(0, int(mblog.get("attitudes_count", 0) or 0)),
            comment_count=max(0, int(mblog.get("comments_count", 0) or 0)),
            share_count=max(0, int(mblog.get("reposts_count", 0) or 0)),
            view_count=0,  # weibo 不提供播放量
        )

    @staticmethod
    def _within_range(item: RawCollectedItem, since: Optional[datetime], until: Optional[datetime]) -> bool:
        if item.publish_time is None:
            return True
        if since and item.publish_time <= since:
            return False
        if until and item.publish_time > until:
            return False
        return True
