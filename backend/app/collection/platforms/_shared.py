# -*- coding: utf-8 -*-
"""平台采集层共享工具：httpx 客户端工厂、Cookie 转换、UA 池、时间解析、异常。"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

__all__ = [
    "DataFetchError",
    "make_async_client",
    "convert_cookies",
    "convert_str_cookie_to_dict",
    "update_cookies_from_context",
    "launch_collection_browser",
    "get_pc_user_agent",
    "get_mobile_user_agent",
    "rfc2822_to_timestamp",
    "rfc2822_to_china_datetime",
    "get_current_timestamp",
    "parse_flexible_timestamp",
]


class DataFetchError(httpx.RequestError):
    """采集请求异常。继承 httpx.RequestError 以便 tenacity 重试识别。"""


def make_async_client(proxy: Optional[str] = None, **kwargs) -> httpx.AsyncClient:
    """创建统一配置的 httpx.AsyncClient。默认开启 SSL 验证、跟随重定向。"""
    kwargs.setdefault("verify", True)
    kwargs.setdefault("follow_redirects", True)
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


def convert_cookies(cookies: Optional[List[dict]]) -> Tuple[str, Dict[str, str]]:
    """把 playwright/browser_context.cookies() 返回的列表转为 (cookie_str, cookie_dict)。"""
    if not cookies:
        return "", {}
    pairs: List[Tuple[str, str]] = []
    for c in cookies:
        name = str(c.get("name") or "")
        value = str(c.get("value") or "")
        if name:
            pairs.append((name, value))
    cookies_str = ";".join([f"{n}={v}" for n, v in pairs])
    cookie_dict = {n: v for n, v in pairs}
    return cookies_str, cookie_dict


def convert_str_cookie_to_dict(cookie_str: str) -> Dict[str, str]:
    """把 "k1=v1; k2=v2" 字符串解析为 dict，跳过非键值对项。"""
    cookie_dict: Dict[str, str] = {}
    if not cookie_str:
        return cookie_dict
    for item in cookie_str.split(";"):
        item = item.strip()
        if not item:
            continue
        kv = item.split("=", 1)
        if len(kv) != 2:
            continue
        cookie_dict[kv[0]] = kv[1]
    return cookie_dict


# PC Chrome UA 池（Win/Mac/Linux，版本 109-123）。比原 20 条略精简但够用。
_PC_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

# 移动端 UA 池（iPhone / Android）。原仅 1 条，此处扩充降低指纹聚类。
_MOBILE_UA_LIST = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; MI 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; HUAWEI-P60) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]


def get_pc_user_agent() -> str:
    """随机返回一个 PC Chrome UA。"""
    return random.choice(_PC_UA_LIST)


def get_mobile_user_agent() -> str:
    """随机返回一个移动端 UA（iPhone/Android）。"""
    return random.choice(_MOBILE_UA_LIST)


# 通用补全请求头片段（浏览器常见字段，降低风控识别）。各平台 client 按需选用。
def common_browser_headers(ua: str, *, mobile: bool = False) -> Dict[str, str]:
    """返回含 UA + Accept + Accept-Language + Accept-Encoding 的基础头。"""
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if not mobile:
        # PC 浏览器 sec-ch-ua 系列客户端提示头
        headers.update(
            {
                "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
    return headers


def rfc2822_to_timestamp(rfc2822_time: str) -> int:
    """RFC2822 时间（weibo created_at，如 'Sat Dec 23 17:12:54 +0800 2023'）→ Unix 秒时间戳。"""
    rfc2822_format = "%a %b %d %H:%M:%S %z %Y"
    dt_object = datetime.strptime(rfc2822_time, rfc2822_format)
    return int(dt_object.timestamp())


def rfc2822_to_china_datetime(rfc2822_time: str) -> datetime:
    """RFC2822 时间 → 东八区 datetime。"""
    rfc2822_format = "%a %b %d %H:%M:%S %z %Y"
    dt_object = datetime.strptime(rfc2822_time, rfc2822_format)
    return dt_object.astimezone(timezone(timedelta(hours=8)))


def get_current_timestamp() -> int:
    """当前 13 位毫秒时间戳。"""
    return int(time.time() * 1000)


def parse_flexible_timestamp(value) -> Optional[datetime]:
    """灵活解析时间戳：支持 datetime、秒/毫秒数字、字符串数字、多种日期格式。"""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
    if number > 10_000_000_000:
        number = number // 1000
    return datetime.fromtimestamp(number)


# ---------------------------------------------------------------------------
# 浏览器采集工具（混合采集模式：httpx 发业务请求 + playwright 做风控恢复）
#  goto+update_cookies 432 恢复机制。
# ---------------------------------------------------------------------------

# stealth.js 路径（复制，注入反自动化检测）
_STEALTH_JS_PATH = Path(__file__).resolve().parent.parent / "libs" / "stealth.min.js"


async def update_cookies_from_context(
    context,
    client,
    urls: Optional[List[str]] = None,
) -> None:
    """从 playwright BrowserContext 提取最新 Cookie，写回 httpx client headers。

    update_cookies。
    浏览器 goto 后会吸收 server 轮换的 Set-Cookie（如 weibo _T_WM/SUB），此处同步到 httpx。
    """
    cookie_str, cookie_dict = convert_cookies(
        list(await context.cookies(urls=urls)) if urls else list(await context.cookies())
    )
    client.headers["Cookie"] = cookie_str
    client.cookie_str = cookie_str
    client.cookie_dict = cookie_dict


async def launch_collection_browser(playwright, *, headless: bool = True):
    """启动采集用 headless 浏览器 + 注入 stealth.js。

    复刻  标准模式：launch(channel="chrome") + new_context + add_init_script(stealth.js)。
    用 launch()+new_context() 而非 launch_persistent_context()，避免 user_data_dir 残留登录态。

    :return: (browser, context, page)
    """
    args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    try:
        browser = await playwright.chromium.launch(channel="chrome", headless=headless, args=args)
    except Exception:
        browser = await playwright.chromium.launch(headless=headless, args=args)

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=get_pc_user_agent(),
    )
    # 注入 stealth.js 抹掉 webdriver/自动化指纹（复刻 weibo/core.py:93）
    # 若文件不存在（如 git clone 后未复制），尝试自动复制
    _ensure_stealth_js()
    if _STEALTH_JS_PATH.exists():
        await context.add_init_script(path=str(_STEALTH_JS_PATH))
    page = await context.new_page()
    return browser, context, page


def _ensure_stealth_js() -> None:
    """stealth.js 不存在时尝试从  复制（部署环境需手动放置）。"""
    if _STEALTH_JS_PATH.exists():
        return
    # 尝试常见路径
    candidates = [
        Path(os.environ.get("STEALTH_JS_PATH", "")),
        Path("/app/libs/stealth.min.js"),  # Docker
    ]
    for src in candidates:
        if src.exists():
            _STEALTH_JS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _STEALTH_JS_PATH.write_bytes(src.read_bytes())
            return
