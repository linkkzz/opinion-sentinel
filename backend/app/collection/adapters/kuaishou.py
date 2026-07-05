# -*- coding: utf-8 -*-
"""快手采集 Adapter：混合采集模式（httpx + playwright block 恢复）。

采集流程：
  1. 从 CollectionAccount 取 valid Cookie；无则 raise
  2. 启动 headless 浏览器 + 注入旧 Cookie + goto www.kuaishou.com 让浏览器吸收 Set-Cookie
  3. 从浏览器 context 同步最新 Cookie 到 httpx client
  4. pong 预检：Cookie 失效 → mark_pending_refresh + raise
  5. 分页搜索 visionSearchPhoto（pcursor 翻页）
  6. block 风控时：goto 首页 + sleep(20) + update_cookies 恢复
  7. 采集成功后回写最新 Cookie 到 DB
  8. finally 关闭浏览器
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

from app.collection.adapters.base import RawCollectedItem
from app.collection.cookie_store import get_valid_cookie, mark_pending_refresh, mark_valid
from app.collection.platforms._shared import DataFetchError, convert_str_cookie_to_dict, launch_collection_browser, parse_flexible_timestamp, update_cookies_from_context
from app.collection.platforms.kuaishou import KuaiShouClient
from app.core.config import settings
from app.core.database import SessionLocal

class KuaishouAdapter:
    platform = "快手"

    async def collect(
        self,
        *,
        keyword: str,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[RawCollectedItem]:
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
                # 注入旧 Cookie
                cookie_list = [
                    {"name": k, "value": v, "domain": ".kuaishou.com", "path": "/"}
                    for k, v in convert_str_cookie_to_dict(cookie_str).items()
                ]
                if cookie_list:
                    await context.add_cookies(cookie_list)

                await page.goto("https://www.kuaishou.com", wait_until="domcontentloaded")
                await asyncio.sleep(2)

                client = KuaiShouClient(cookie_str, playwright_page=page)
                await update_cookies_from_context(context, client, ["https://www.kuaishou.com"])

                # pong 预检
                if not await client.pong():
                    with SessionLocal() as db:
                        mark_pending_refresh(db, account_id)
                        db.commit()
                    raise RuntimeError(f"{self.platform} Cookie 已失效，已标记待刷新")

                # 分页搜索（最大 5 页，避免无限翻页）
                pcursor = ""
                max_pages = 5
                page_count = 0
                while len(results) < limit and page_count < max_pages:
                    try:
                        data = await client.search_info_by_keyword(keyword, pcursor)
                    except DataFetchError:
                        # block 恢复：goto 首页 + sleep(20) + update_cookies（复刻
                        await page.goto("https://www.kuaishou.com?isHome=1", wait_until="domcontentloaded")
                        await asyncio.sleep(20)
                        await update_cookies_from_context(context, client, ["https://www.kuaishou.com"])
                        # 重试一次当前页
                        data = await client.search_info_by_keyword(keyword, pcursor)

                    search_data = data.get("visionSearchPhoto") or {}
                    feeds = search_data.get("feeds") or []
                    if not feeds:
                        break
                    for feed in feeds:
                        item = self._feed_to_raw(feed, keyword)
                        if item and self._within_range(item, since, until):
                            results.append(item)
                        if len(results) >= limit:
                            break
                    pcursor = search_data.get("pcursor", "")
                    if not pcursor or pcursor == "no_more":
                        break
                    page_count += 1
                    await asyncio.sleep(settings.collection_request_sleep)

                # 回写最新 Cookie
                if results and client.cookie_str != cookie_str:
                    with SessionLocal() as db:
                        mark_valid(db, account_id, cookie_str=client.cookie_str)
                        db.commit()
            except DataFetchError as exc:
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
    def _feed_to_raw(feed: dict, keyword: str) -> Optional[RawCollectedItem]:
        """feed → RawCollectedItem。字段映射store/kuaishou/__init__.py:60-76。"""
        photo = feed.get("photo") or {}
        video_id = str(photo.get("id") or feed.get("photoId") or "")
        if not video_id:
            return None
        author_info = feed.get("author") or {}
        title = str(photo.get("caption") or feed.get("caption") or "")
        desc = str(photo.get("description") or "")
        content = desc or title
        if not content:
            return None
        return RawCollectedItem(
            platform="快手",
            external_id=video_id,
            title=(title or content)[:48],
            author=author_info.get("name", "未知"),
            publish_time=parse_flexible_timestamp(photo.get("timestamp")),
            content=content,
            source_url=photo.get("photoUrl") or feed.get("photoUrl"),
            like_count=max(0, int(feed.get("likeCount") or photo.get("likeCount") or 0)),
            comment_count=0,  # 搜索结果无评论数，需 detail 补（当前接受为 0）
            share_count=0,
            view_count=max(0, int(feed.get("viewCount") or photo.get("viewCount") or 0)),
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
