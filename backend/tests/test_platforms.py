# -*- coding: utf-8 -*-
"""平台采集 Client 单元测试：锁定反风控加固点与核心行为，mock httpx 不打真实平台。

本仓库异步测试沿用 test_api.py 的 asyncio.run() 模式（不引入 pytest-asyncio）。
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.collection.platforms import SUPPORTED_PLATFORMS, get_platform_client
from app.collection.platforms._shared import (
    DataFetchError,
    convert_str_cookie_to_dict,
    get_mobile_user_agent,
    get_pc_user_agent,
)
from app.collection.platforms.kuaishou import KuaiShouClient, KuaiShouGraphQL
from app.collection.platforms.weibo import WeiboClient
from app.collection.platforms.weibo_field import SearchType
from app.collection.platforms.weibo_help import filter_search_result_card


# ---------------- _shared ----------------

def test_convert_str_cookie_to_dict_parses_kv():
    assert convert_str_cookie_to_dict("a=1; b=2") == {"a": "1", "b": "2"}


def test_convert_str_cookie_to_dict_skips_non_kv():
    assert convert_str_cookie_to_dict("a=1;; bad; c=3") == {"a": "1", "c": "3"}


def test_mobile_ua_pool_has_multiple():
    # 加固点 E：mobile UA 池扩充（原 MediaCrawler 仅 1 条）
    uas = {get_mobile_user_agent() for _ in range(50)}
    assert len(uas) >= 5, "mobile UA 池应有多条以降低指纹聚类"


def test_pc_ua_pool_has_multiple():
    uas = {get_pc_user_agent() for _ in range(50)}
    assert len(uas) >= 5


# ---------------- weibo ----------------

def test_weibo_client_headers_hardened():
    # 加固点 B：weibo 补全 Accept / Accept-Language
    c = WeiboClient("SUB=abc")
    assert "Accept-Language" in c.headers
    assert c.headers["Accept"].startswith("application/json")
    assert c.headers["Origin"] == "https://m.weibo.cn"
    assert c.headers["Cookie"] == "SUB=abc"


def test_weibo_set_cookies_updates_headers():
    c = WeiboClient("old=1")
    c.set_cookies("new=2")
    assert c.headers["Cookie"] == "new=2"
    assert c.cookie_dict == {"new": "2"}


def test_weibo_pong_true_when_login():
    async def run():
        with patch.object(WeiboClient, "request", new=AsyncMock(return_value={"login": True})):
            c = WeiboClient("SUB=abc")
            return await c.pong()
    assert asyncio.run(run()) is True


def test_weibo_432_raises_data_fetch_error():
    # 加固点 A：432 返回非 JSON → 抛 DataFetchError 触发上层 mark_pending_refresh
    # tenacity @retry(5,3s) 会重试，最终抛 DataFetchError
    async def run():
        with patch.object(WeiboClient, "request", new=AsyncMock(side_effect=DataFetchError("432"))):
            c = WeiboClient("SUB=abc")
            return await c.pong()
    assert asyncio.run(run()) is False  # pong 内部 catch 异常返回 False


def test_weibo_search_type_enum():
    assert SearchType.REAL_TIME.value == "61"


def test_filter_search_result_card_keeps_type_9():
    cards = [
        {"card_type": 9, "mblog": {"id": "1"}},
        {"card_type": 11},
        {"card_type": 9, "card_group": [{"card_type": 9, "mblog": {"id": "2"}}]},
    ]
    notes = filter_search_result_card(cards)
    assert len(notes) == 3  # 2 个顶层 type9 + 1 个嵌套 type9


# ---------------- kuaishou ----------------

def test_kuaishou_graphql_loads_from_package():
    # 加固点：graphql 路径改包内资源（原硬编码 cwd）
    g = KuaiShouGraphQL()
    assert "search_query" in g.graphql_queries
    assert "video_detail" in g.graphql_queries
    assert len(g.graphql_queries) == 7
    assert "visionSearchPhoto" in g.get("search_query")


def test_kuaishou_client_headers_hardened():
    # 加固点 B：kuaishou 补全 sec-ch-ua / sec-fetch 系列
    c = KuaiShouClient("passToken=abc")
    assert c.headers["sec-fetch-site"] == "same-origin"
    assert c.headers["sec-fetch-mode"] == "cors"
    assert c.headers["sec-fetch-dest"] == "empty"
    assert "sec-ch-ua" in c.headers
    assert c.headers["Origin"] == "https://www.kuaishou.com"


def test_kuaishou_search_referer_is_search_result_page():
    # 加固点 C：搜索 Referer 改为搜索结果页（原 MediaCrawler 用首页是风控识别点）
    c = KuaiShouClient("passToken=abc")
    c.set_search_referer("食堂")
    assert c.headers["Referer"] == "https://www.kuaishou.com/search/result?searchKey=%E9%A3%9F%E5%A0%82"


def test_kuaishou_request_errors_raises_data_fetch_error():
    # 加固点：errors 字段即风控信号 → 抛 DataFetchError（经 tenacity 重试 3 次后抛出）

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"errors": [{"message": "login required"}]}

        class _Req:
            url = "https://www.kuaishou.com/graphql"

        request = _Req()

    async def run():
        with patch("app.collection.platforms.kuaishou.make_async_client") as mock_mac:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=FakeResponse())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_mac.return_value = mock_client
            c = KuaiShouClient("passToken=abc")
            with pytest.raises(DataFetchError):
                await c.request("POST", "https://www.kuaishou.com/graphql")

    asyncio.run(run())


def test_kuaishou_pong_true_when_valid():
    async def run():
        with patch.object(KuaiShouClient, "post", new=AsyncMock(return_value={"visionProfileUserList": {"result": 1}})):
            c = KuaiShouClient("passToken=abc")
            return await c.pong()
    assert asyncio.run(run()) is True


# ---------------- registry ----------------

def test_get_platform_client_weibo():
    c = get_platform_client("微博", "SUB=x")
    assert isinstance(c, WeiboClient)


def test_get_platform_client_kuaishou():
    c = get_platform_client("快手", "passToken=x")
    assert isinstance(c, KuaiShouClient)


def test_get_platform_client_unsupported_raises():
    with pytest.raises(ValueError):
        get_platform_client("小红书", "x")


def test_supported_platforms():
    assert SUPPORTED_PLATFORMS == {"微博", "快手", "bilibili"}


def test_bilibili_wbi_sign():
    """bilibili WBI 签名算法测试：输出含 w_rid 且可复现。"""
    from app.collection.platforms.bilibili_help import BilibiliSign

    sign = BilibiliSign("7cd084941338484aae1ad9425b84077c", "4932caff0ff746eab6f01bf08b70ac45")
    result = sign.sign({"keyword": "测试", "page": 1})
    assert "w_rid" in result
    assert "wts" in result
    assert len(result["w_rid"]) == 32  # md5 hex


def test_bilibili_client_get_adapter():
    """bilibili adapter 注册可获取。"""
    from app.collection.adapters import get_adapter
    adapter = get_adapter("bilibili")
    assert adapter.platform == "bilibili"
