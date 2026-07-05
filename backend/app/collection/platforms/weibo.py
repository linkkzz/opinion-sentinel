# -*- coding: utf-8 -*-
"""微博移动端 API Client（m.weibo.cn）。混合采集模式。

有 playwright_page 时 432 风控自动恢复（goto+update_cookies）；无时抛异常交上层刷新。
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from ._shared import (
    DataFetchError,
    common_browser_headers,
    convert_str_cookie_to_dict,
    get_mobile_user_agent,
    make_async_client,
    update_cookies_from_context,
)
from .weibo_field import SearchType

class WeiboClient:
    """微博 m.weibo.cn 移动端 API 客户端。

    :param playwright_page: 可选，传入后 432 风控时自动 goto+update_cookies 恢复。
        恢复机制。
    """

    def __init__(
        self,
        cookie_str: str,
        *,
        proxy: Optional[str] = None,
        timeout: int = 60,
        user_agent: Optional[str] = None,
        playwright_page=None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self._host = "https://m.weibo.cn"
        self.cookie_urls = [self._host]
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.user_agent = user_agent or get_mobile_user_agent()
        self.playwright_page = playwright_page
        self.headers = self._build_headers()

    def _build_headers(self) -> Dict[str, str]:
        """构造移动端请求头（补全 Accept 系列字段）。"""
        headers = common_browser_headers(self.user_agent, mobile=True)
        headers.update(
            {
                "Origin": "https://m.weibo.cn",
                "Referer": "https://m.weibo.cn",
                "Content-Type": "application/json;charset=UTF-8",
                "Cookie": self.cookie_str,
            }
        )
        return headers

    def set_cookies(self, cookie_str: str) -> None:
        """Cookie 刷新后热更新（无需重建 client）。"""
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.headers["Cookie"] = cookie_str

    async def update_cookies(self, context, urls: Optional[List[str]] = None) -> None:
        """从浏览器 context 同步最新 Cookie 到 httpx headers。update_cookies。"""
        await update_cookies_from_context(context, self, urls or self.cookie_urls)

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(3), reraise=True)
    async def request(self, method: str, url: str, **kwargs) -> Union[Dict, httpx.Response]:
        """统一请求入口。432 风控时：有 page 则 goto+update_cookies 恢复后重试，无则抛异常。"""
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        return_response = kwargs.pop("return_response", False)
        if return_response:
            return response

        try:
            data: Dict = response.json()
        except (json.decoder.JSONDecodeError, ValueError):
            # weibo 432 风控：返回非 JSON HTML
            if self.playwright_page:
                # 复刻首页 + sleep(2) + update_cookies → 触发重试
                await self.playwright_page.goto(self._host)
                await asyncio.sleep(2)
                await self.update_cookies(self.playwright_page.context)
                raise DataFetchError(
                    f"weibo 432 风控，已 goto+update_cookies 恢复，重试中：status={response.status_code}",
                    request=response.request,
                )
            raise DataFetchError(
                f"weibo 请求返回非 JSON（疑似 432 风控，Cookie 可能失效）：status={response.status_code}",
                request=response.request,
            )

        ok_code = data.get("ok")
        if ok_code == 0:
            raise DataFetchError(data.get("msg", "weibo response ok=0"), request=response.request)
        if ok_code != 1:
            raise DataFetchError(data.get("msg", "weibo unknown error"), request=response.request)
        return data.get("data", {})

    async def get(self, uri: str, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"
        return await self.request(
            method="GET",
            url=f"{self._host}{final_uri}",
            headers=headers or self.headers,
        )

    async def pong(self) -> bool:
        """校验登录态是否有效。"""
        try:
            resp_data: Dict = await self.request(
                method="GET", url=f"{self._host}/api/config", headers=self.headers
            )
            return bool(resp_data.get("login"))
        except Exception:
            return False

    async def get_note_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        search_type: SearchType = SearchType.DEFAULT,
    ) -> Dict:
        """关键词搜索微博（m.weibo.cn/api/container/getIndex）。无签名，纯 HTTP。"""
        uri = "/api/container/getIndex"
        containerid = f"100103type={search_type.value}&q={keyword}"
        params = {"containerid": containerid, "page_type": "searchall", "page": page}
        return await self.get(uri, params)

    async def get_note_comments(self, mid_id: str, max_id: int, max_id_type: int = 0) -> Dict:
        uri = "/comments/hotflow"
        params: Dict = {"id": mid_id, "mid": mid_id, "max_id_type": max_id_type}
        if max_id > 0:
            params["max_id"] = max_id
        headers = copy.copy(self.headers)
        headers["Referer"] = f"https://m.weibo.cn/detail/{mid_id}"
        return await self.get(uri, params, headers=headers)

    async def get_note_info_by_id(self, note_id: str) -> Dict:
        """获取长微博全文（解析详情页 $render_data）。"""
        url = f"{self._host}/detail/{note_id}"
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request("GET", url, timeout=self.timeout, headers=self.headers)
            if response.status_code != 200:
                raise DataFetchError(f"get weibo detail err: {response.text}", request=response.request)
            match = re.search(r"var \$render_data = (\[.*?\])\[0\]", response.text, re.DOTALL)
            if match:
                render_data = json.loads(match.group(1))
                note_detail = render_data[0].get("status")
                return {"mblog": note_detail}
            return {}
