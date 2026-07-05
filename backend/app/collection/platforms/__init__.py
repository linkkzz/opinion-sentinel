# -*- coding: utf-8 -*-
"""平台采集 Client 注册中心。

微博 / 快手为首批二开接入平台（纯 HTTP，无浏览器依赖）。get_platform_client 按
中文平台名返回对应 client 实例；Cookie 由调用方（adapter）从 CollectionAccount 注入。
"""

from __future__ import annotations

from typing import Union

from .bilibili import BilibiliClient
from .kuaishou import KuaiShouClient
from .weibo import WeiboClient

SUPPORTED_PLATFORMS = {"微博", "快手", "bilibili"}

PlatformClient = Union[WeiboClient, KuaiShouClient, BilibiliClient]


def get_platform_client(platform: str, cookie_str: str, **kwargs) -> PlatformClient:
    """按平台名构造采集 client。

    :param platform: 平台名（微博 / 快手 / bilibili）
    :param cookie_str: 平台域 Cookie 字符串（由 CollectionAccount 提供，bilibili 可空）
    :raises ValueError: 平台未支持
    """
    if platform == "微博":
        return WeiboClient(cookie_str, **kwargs)
    if platform == "快手":
        return KuaiShouClient(cookie_str, **kwargs)
    if platform == "bilibili":
        return BilibiliClient(cookie_str, **kwargs)
    raise ValueError(f"{platform} 暂未支持持续监测，当前仅支持：微博、快手、bilibili")


__all__ = [
    "SUPPORTED_PLATFORMS",
    "PlatformClient",
    "get_platform_client",
    "WeiboClient",
    "KuaiShouClient",
    "BilibiliClient",
]
