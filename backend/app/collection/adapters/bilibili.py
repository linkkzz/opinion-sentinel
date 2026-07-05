# -*- coding: utf-8 -*-
"""bilibili 采集 Adapter：纯 HTTP 搜索 + WBI 签名。

bilibili 风控松、无需浏览器恢复。免登录优先：无账号也能采基础数据
（标题/作者/播放量/发布时间/弹幕数），有账号补完整互动数（点赞/收藏）。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Optional

from app.collection.adapters.base import RawCollectedItem
from app.collection.cookie_store import get_valid_cookie
from app.collection.platforms._shared import DataFetchError, parse_flexible_timestamp
from app.collection.platforms.bilibili import BilibiliClient
from app.core.config import settings
from app.core.database import SessionLocal


class BilibiliAdapter:
    platform = "bilibili"

    async def collect(
        self,
        *,
        keyword: str,
        since: Optional[datetime],
        until: Optional[datetime],
        limit: int,
    ) -> list[RawCollectedItem]:
        # 取 Cookie（可选：有 valid 账号则登录态，无则匿名采基础数据）
        cookie_str = ""
        with SessionLocal() as db:
            account = get_valid_cookie(db, self.platform)
            if account:
                cookie_str = account.cookie_str

        client = BilibiliClient(cookie_str)

        # 分页搜索（最大 5 页 = 100 条，避免无限翻页）
        results: list[RawCollectedItem] = []
        page = 1
        page_size = 20
        max_pages = 5
        try:
            while len(results) < limit and page <= max_pages:
                data = await client.search_video_by_keyword(keyword, page, page_size)
                video_list = data.get("result")
                if not video_list:
                    break
                for video in video_list:
                    item = self._video_to_raw(video, keyword)
                    if item and self._within_range(item, since, until):
                        results.append(item)
                    if len(results) >= limit:
                        break
                page += 1
                await asyncio.sleep(settings.collection_request_sleep)
        except DataFetchError as exc:
            if results:
                return results[:limit]
            raise RuntimeError(f"{self.platform} 采集失败：{exc}") from exc

        return results[:limit]

    @staticmethod
    def _video_to_raw(video: dict, keyword: str) -> Optional[RawCollectedItem]:
        """bilibili 搜索结果 → RawCollectedItem。

        搜索 API 字段：aid/bvid/title/author/mid/play(播放)/video_review(弹幕)/
        review(评论)/favorites(收藏)/pubdate(发布时间戳)/pic/arcurl/duration。
        """
        bvid = str(video.get("bvid") or "")
        aid = str(video.get("aid") or "")
        if not bvid and not aid:
            return None
        title_html = video.get("title", "")
        # 搜索结果 title 含 <em class="keyword"> 高亮标签
        title = re.sub(r"<.*?>", "", title_html).strip()
        author = video.get("author", "未知")
        pubdate = video.get("pubdate")
        publish_time = parse_flexible_timestamp(pubdate) if pubdate else None
        source_url = f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}"
        return RawCollectedItem(
            platform="bilibili",
            external_id=bvid or aid,
            title=title[:80] if title else "无标题",
            author=author,
            publish_time=publish_time,
            content=title,
            source_url=source_url,
            view_count=max(0, int(video.get("play", 0) or 0)),
            comment_count=max(0, int(video.get("review", 0) or 0)),
            share_count=max(0, int(video.get("video_review", 0) or 0)),
            like_count=max(0, int(video.get("favorites", 0) or 0)),
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
