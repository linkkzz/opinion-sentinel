# -*- coding: utf-8 -*-
# 基于 MediaCrawler 二开的快手采集 Client。
#
# 原始项目：https://github.com/NanmiCoder/MediaCrawler
# 原始版权：Copyright (c) 2025 relakkes@gmail.com
# 许可：NON-COMMERCIAL LEARNING LICENSE 1.1（仅供学习研究，禁止商用）。
#
# 二开改动：
#   - 混合采集模式：httpx 发业务请求 + 可选 playwright_page 做 block 风控恢复
#   - 补 request 级 @retry + 补全 sec-ch-ua / sec-fetch 系列请求头
#   - 搜索 Referer 改为搜索结果页（原 core.py:320 用首页，与真实浏览器不符）
#   - GraphQL 文件路径从 cwd 相对路径改为包内资源路径
"""快手 GraphQL API Client（www.kuaishou.com/graphql）。混合采集模式。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from ._shared import (
    DataFetchError,
    common_browser_headers,
    convert_str_cookie_to_dict,
    get_pc_user_agent,
    make_async_client,
    update_cookies_from_context,
)

_GRAPHQL_DIR = Path(__file__).parent / "kuaishou_graphql"


class KuaiShouGraphQL:
    """GraphQL 查询语句加载器。从包内 kuaishou_graphql/ 目录读取 .graphql 文件。"""

    def __init__(self) -> None:
        self.graphql_queries: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        files = [
            "search_query.graphql",
            "video_detail.graphql",
            "comment_list.graphql",
            "vision_profile.graphql",
            "vision_profile_photo_list.graphql",
            "vision_profile_user_list.graphql",
            "vision_sub_comment_list.graphql",
        ]
        for name in files:
            query_name = name.split(".")[0]
            with (_GRAPHQL_DIR / name).open("r", encoding="utf-8") as f:
                self.graphql_queries[query_name] = f.read()

    def get(self, query_name: str) -> str:
        return self.graphql_queries.get(query_name, "")


class KuaiShouClient:
    """快手 GraphQL 客户端。

    :param playwright_page: 可选，传入后 block 风控时由 adapter 层 goto+update_cookies 恢复。
    """

    def __init__(
        self,
        cookie_str: str,
        *,
        proxy: Optional[str] = None,
        timeout: int = 10,
        user_agent: Optional[str] = None,
        playwright_page=None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self._host = "https://www.kuaishou.com/graphql"
        self._rest_host = "https://www.kuaishou.com"
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.user_agent = user_agent or get_pc_user_agent()
        self.playwright_page = playwright_page
        self.graphql = KuaiShouGraphQL()
        self.headers = self._build_headers()

    def _build_headers(self) -> Dict[str, str]:
        headers = common_browser_headers(self.user_agent, mobile=False)
        headers.update(
            {
                "Origin": "https://www.kuaishou.com",
                "Referer": "https://www.kuaishou.com",
                "Content-Type": "application/json;charset=UTF-8",
                "Cookie": self.cookie_str,
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
            }
        )
        return headers

    def set_cookies(self, cookie_str: str) -> None:
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.headers["Cookie"] = cookie_str

    async def update_cookies(self, context, urls: Optional[List[str]] = None) -> None:
        """从浏览器 context 同步最新 Cookie。复刻 client.update_cookies。"""
        await update_cookies_from_context(context, self, urls or [self._rest_host])

    def set_search_referer(self, keyword: str) -> None:
        """搜索时把 Referer 改为搜索结果页。"""
        from urllib.parse import quote
        self.headers["Referer"] = f"{self._rest_host}/search/result?searchKey={quote(keyword)}"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5), reraise=True)
    async def request(self, method: str, url: str, **kwargs) -> Dict:
        """统一请求入口。补 @retry（原 kuaishou 无重试）。errors 字段即风控信号。"""
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        try:
            data: Dict = response.json()
        except (json.decoder.JSONDecodeError, ValueError):
            raise DataFetchError(
                f"kuaishou 请求返回非 JSON（疑似风控）：status={response.status_code}",
                request=response.request,
            )
        if data.get("errors"):
            raise DataFetchError(
                f"kuaishou graphql errors: {data.get('errors')}", request=response.request
            )
        return data.get("data", {})

    async def post(self, data: dict) -> Dict:
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            method="POST", url=self._host, data=json_str, headers=self.headers
        )

    async def pong(self) -> bool:
        """校验登录态。复刻 kuaishou/client.py:115-135。"""
        try:
            post_data = {
                "operationName": "visionProfileUserList",
                "variables": {"ftype": 1},
                "query": self.graphql.get("vision_profile_user_list"),
            }
            res = await self.post(post_data)
            return res.get("visionProfileUserList", {}).get("result") == 1
        except Exception:
            return False

    async def search_info_by_keyword(
        self, keyword: str, pcursor: str, search_session_id: str = ""
    ) -> Dict:
        """关键词搜索视频。复刻 kuaishou/client.py:145-165。"""
        self.set_search_referer(keyword)
        post_data = {
            "operationName": "visionSearchPhoto",
            "variables": {
                "keyword": keyword,
                "pcursor": pcursor,
                "page": "search",
                "searchSessionId": search_session_id,
            },
            "query": self.graphql.get("search_query"),
        }
        return await self.post(post_data)

    async def get_video_info(self, photo_id: str) -> Dict:
        """视频详情（可补 comment_count / share_count）。复刻 kuaishou/client.py:167-178。"""
        post_data = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": photo_id, "page": "search"},
            "query": self.graphql.get("video_detail"),
        }
        return await self.post(post_data)
