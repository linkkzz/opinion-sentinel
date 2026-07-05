# -*- coding: utf-8 -*-
# 基于 MediaCrawler 二开的 bilibili 采集 Client。
#
# 原始项目：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/client.py
# 原始版权：Copyright (c) 2025 relakkes@gmail.com
# 许可：NON-COMMERCIAL LEARNING LICENSE 1.1（仅供学习研究，禁止商用）。
#
# 二开改动：
#   - 去除 playwright_page / ProxyRefreshMixin 依赖，改为纯 httpx
#   - get_wbi_keys 去掉 localStorage 路径，永远走 nav 接口 fallback（公开 API 无需登录态）
#   - pong() 失败不 raise，返回 False（免登录优先：不登录也能采基础数据）
"""bilibili API Client（api.bilibili.com）。纯 HTTP + WBI 签名，无浏览器依赖。

bilibili 风控松、搜索 API 无需签名验证身份（仅需 WBI 参数签名），不登录也能返回
基础数据（标题/作者/播放量/发布时间）。登录后有完整互动数（点赞/投币/收藏）。
"""
from __future__ import annotations

import json
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx

from ._shared import DataFetchError, common_browser_headers, convert_str_cookie_to_dict, get_pc_user_agent, make_async_client
from .bilibili_help import BilibiliSign


class BilibiliClient:
    """bilibili API 客户端。

    搜索 API: ``/x/web-interface/wbi/search/type``，需 WBI 签名（w_rid）。
    nav 接口: ``/x/web-interface/nav``，返回 wbi_img 配置 + isLogin 状态。
    """

    def __init__(
        self,
        cookie_str: str = "",
        *,
        proxy: Optional[str] = None,
        timeout: int = 30,
        user_agent: Optional[str] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self._host = "https://api.bilibili.com"
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.user_agent = user_agent or get_pc_user_agent()
        self.headers = self._build_headers()
        self._wbi_keys: Optional[Tuple[str, str]] = None

    def _build_headers(self) -> Dict[str, str]:
        headers = common_browser_headers(self.user_agent, mobile=False)
        # bilibili 会返回 brotli 压缩，httpx 无 brotli 解码器时改用 gzip only
        headers["Accept-Encoding"] = "gzip, deflate"
        headers.update(
            {
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com",
                "Cookie": self.cookie_str,
            }
        )
        return headers

    def set_cookies(self, cookie_str: str) -> None:
        self.cookie_str = cookie_str
        self.cookie_dict = convert_str_cookie_to_dict(cookie_str)
        self.headers["Cookie"] = cookie_str

    async def request(self, method: str, url: str, **kwargs) -> Dict:
        """统一请求入口。code != 0 抛 DataFetchError。"""
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        try:
            data: Dict = response.json()
        except (json.JSONDecodeError, ValueError):
            raise DataFetchError(
                f"bilibili 请求返回非 JSON：status={response.status_code}",
                request=response.request,
            )
        if data.get("code") != 0:
            raise DataFetchError(
                f"bilibili API error: code={data.get('code')} message={data.get('message', '')}",
                request=response.request,
            )
        return data.get("data", {})

    async def get_wbi_keys(self) -> Tuple[str, str]:
        """获取 WBI 签名所需的 img_key 和 sub_key。

        纯 httpx：调 nav 接口取 wbi_img.img_url / sub_url。
        nav 接口未登录时 code=-101 但仍返回 wbi_img 数据，故不走 request()。
        结果缓存避免重复请求。
        """
        if self._wbi_keys:
            return self._wbi_keys
        async with make_async_client(proxy=self.proxy) as client:
            response = await client.get(
                f"{self._host}/x/web-interface/nav", timeout=self.timeout, headers=self.headers
            )
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            raise DataFetchError(
                f"bilibili nav 接口返回非 JSON：status={response.status_code}",
                request=response.request,
            )
        wbi_img = data.get("data", {}).get("wbi_img", {})
        img_url: str = wbi_img.get("img_url", "")
        sub_url: str = wbi_img.get("sub_url", "")
        if not img_url or not sub_url:
            raise DataFetchError(f"bilibili nav 接口未返回 wbi_img：{data}", request=response.request)
        img_key = img_url.rsplit("/", 1)[1].split(".")[0]
        sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
        self._wbi_keys = (img_key, sub_key)
        return img_key, sub_key

    async def _sign_params(self, params: Optional[Dict]) -> Optional[Dict]:
        """对 params 做 WBI 签名。"""
        if not params:
            return params
        img_key, sub_key = await self.get_wbi_keys()
        return BilibiliSign(img_key, sub_key).sign(params)

    async def get(self, uri: str, params: Optional[Dict] = None, enable_sign: bool = True) -> Dict:
        """GET 请求，可选 WBI 签名。"""
        if enable_sign and params:
            params = await self._sign_params(params)
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def pong(self) -> bool:
        """校验登录态。调 nav 接口判 isLogin。失败返回 False（免登录优先）。"""
        try:
            async with make_async_client(proxy=self.proxy) as client:
                response = await client.get(
                    f"{self._host}/x/web-interface/nav", timeout=self.timeout, headers=self.headers
                )
            data = response.json().get("data", {})
            return bool(data.get("isLogin"))
        except Exception:
            return False

    async def search_video_by_keyword(self, keyword: str, page: int = 1, page_size: int = 20) -> Dict:
        """关键词搜索视频。GET /x/web-interface/wbi/search/type，需 WBI 签名。

        :return: data.result 视频列表
        """
        uri = "/x/web-interface/wbi/search/type"
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "order": "",
            "pubtime_begin_s": 0,
            "pubtime_end_s": 0,
        }
        return await self.get(uri, params, enable_sign=True)
