# -*- coding: utf-8 -*-
"""采集 Adapter 测试：验证 pong 预检、风控标记、无 Cookie 失败、真实采集映射。

mock 平台 client 避免真实请求。用独立 in-memory sqlite 做 Cookie 仓库。
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_opinion_sentinel.db")
os.environ.setdefault("STORAGE_ROOT", "./test_storage")

from app.collection.adapters import get_adapter
from app.collection.adapters.weibo import WeiboAdapter
from app.collection.adapters.kuaishou import KuaishouAdapter
from app.collection.cookie_store import create_account
from app.collection.platforms._shared import DataFetchError
from app.core.database import Base, SessionLocal, engine


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_weibo_no_cookie_raises():
    """无采集账号 → 直接 raise，不产生任何数据。"""
    async def run():
        adapter = WeiboAdapter()
        await adapter.collect(keyword="食堂", since=None, until=None, limit=3)
    try:
        asyncio.run(run())
        assert False, "应抛 RuntimeError"
    except RuntimeError as e:
        assert "无可用" in str(e) and "采集账号" in str(e)


def test_kuaishou_no_cookie_raises():
    async def run():
        adapter = KuaishouAdapter()
        await adapter.collect(keyword="售后", since=None, until=None, limit=3)
    try:
        asyncio.run(run())
        assert False, "应抛 RuntimeError"
    except RuntimeError as e:
        assert "无可用" in str(e) and "采集账号" in str(e)


def test_weibo_pong_fail_marks_pending_refresh():
    """Cookie 存在但 pong 失败 → mark_pending_refresh + raise。"""
    async def run():
        with SessionLocal() as db:
            account = create_account(db, platform="微博", cookie_str="SUB=stale")
            db.commit()
            aid = account.id
        with patch("app.collection.adapters.weibo.WeiboClient") as MockClient:
            mock_inst = MockClient.return_value
            mock_inst.pong = AsyncMock(return_value=False)
            adapter = WeiboAdapter()
            try:
                await adapter.collect(keyword="食堂", since=None, until=None, limit=3)
            except RuntimeError as e:
                assert "失效" in str(e)
        with SessionLocal() as db:
            from app.models import CollectionAccount
            acc = db.get(CollectionAccount, aid)
            assert acc.status == "pending_refresh"
    asyncio.run(run())


def test_weibo_data_fetch_error_marks_pending_refresh():
    """搜索遇 DataFetchError（432 风控）→ mark_pending_refresh + raise。"""
    async def run():
        with SessionLocal() as db:
            account = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            aid = account.id
        with patch("app.collection.adapters.weibo.WeiboClient") as MockClient:
            mock_inst = MockClient.return_value
            mock_inst.pong = AsyncMock(return_value=True)
            mock_inst.get_note_by_keyword = AsyncMock(
                side_effect=DataFetchError("432 风控")
            )
            adapter = WeiboAdapter()
            try:
                await adapter.collect(keyword="食堂", since=None, until=None, limit=3)
            except RuntimeError as e:
                assert "风控" in str(e)
        with SessionLocal() as db:
            from app.models import CollectionAccount
            acc = db.get(CollectionAccount, aid)
            assert acc.status == "pending_refresh"
    asyncio.run(run())


def test_weibo_successful_collection_with_mocked_client():
    """pong 通过 → 搜索返回 mblog → 映射 RawCollectedItem，含可跳转 source_url。"""
    fake_search_data = {
        "cards": [
            {
                "card_type": 9,
                "mblog": {
                    "id": "123456",
                    "text": "食堂卫生需要加强管理",
                    "created_at": "Sat Dec 23 17:12:54 +0800 2023",
                    "attitudes_count": 50,
                    "comments_count": 28,
                    "reposts_count": 10,
                    "user": {"screen_name": "校园观察"},
                },
            },
            {
                "card_type": 11,  # 非 type9，应被过滤
            },
        ]
    }

    async def run():
        with SessionLocal() as db:
            create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
        with patch("app.collection.adapters.weibo.WeiboClient") as MockClient:
            mock_inst = MockClient.return_value
            mock_inst.pong = AsyncMock(return_value=True)
            mock_inst.get_note_by_keyword = AsyncMock(side_effect=[fake_search_data, {"cards": []}])
            adapter = WeiboAdapter()
            items = await adapter.collect(keyword="食堂", since=None, until=None, limit=3)
        return items
    items = asyncio.run(run())
    assert len(items) == 1
    item = items[0]
    assert item.platform == "微博"
    assert item.external_id == "123456"
    assert item.author == "校园观察"
    assert item.content == "食堂卫生需要加强管理"
    assert item.like_count == 50
    assert item.comment_count == 28
    assert item.share_count == 10
    assert item.source_url == "https://m.weibo.cn/detail/123456"
    assert item.publish_time is not None


def test_kuaishou_successful_collection_with_mocked_client():
    fake_search_data = {
        "visionSearchPhoto": {
            "feeds": [
                {
                    "photoId": "vid_001",
                    "caption": "售后排队太久",
                    "author": {"name": "车主反馈站"},
                    "likeCount": 100,
                    "viewCount": 5000,
                    "photo": {"id": "vid_001", "description": "售后排队太久，希望改善", "timestamp": 1703332374},
                }
            ],
            "pcursor": "no_more",
        }
    }

    async def run():
        with SessionLocal() as db:
            create_account(db, platform="快手", cookie_str="passToken=abc")
            db.commit()
        with patch("app.collection.adapters.kuaishou.KuaiShouClient") as MockClient:
            mock_inst = MockClient.return_value
            mock_inst.pong = AsyncMock(return_value=True)
            mock_inst.search_info_by_keyword = AsyncMock(return_value=fake_search_data)
            adapter = KuaishouAdapter()
            items = await adapter.collect(keyword="售后", since=None, until=None, limit=3)
        return items
    items = asyncio.run(run())
    assert len(items) == 1
    item = items[0]
    assert item.platform == "快手"
    assert item.external_id == "vid_001"
    assert item.author == "车主反馈站"
    assert item.like_count == 100
    assert item.view_count == 5000


def test_weibo_since_filter():
    """since 过滤掉 publish_time <= since 的条目。"""
    fake_data = {
        "cards": [
            {
                "card_type": 9,
                "mblog": {
                    "id": "1",
                    "text": "旧内容",
                    "created_at": "Sat Dec 23 17:12:54 +0800 2023",  # 2023-12-23
                    "user": {"screen_name": "x"},
                },
            }
        ]
    }
    since = datetime(2024, 1, 1)  # 比 2023-12-23 晚 → 应被过滤

    async def run():
        with SessionLocal() as db:
            create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
        with patch("app.collection.adapters.weibo.WeiboClient") as MockClient:
            mock_inst = MockClient.return_value
            mock_inst.pong = AsyncMock(return_value=True)
            mock_inst.get_note_by_keyword = AsyncMock(side_effect=[fake_data, {"cards": []}])
            adapter = WeiboAdapter()
            items = await adapter.collect(keyword="x", since=since, until=None, limit=3)
        return items
    items = asyncio.run(run())
    assert len(items) == 0  # 被过滤
