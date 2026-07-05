# -*- coding: utf-8 -*-
"""采集账号登录引擎：playwright 扫码登录 + 按需 Cookie 刷新。

登录与 Cookie 管理策略（weibo/login.py、kuaishou/login.py、
crawler_util.find_login_qrcode），改为 in-process 调用，通过 SSE 把二维码推给前端。

核心设计（对齐）：
  -用 show_qrcode(PIL 弹图) 作为唯一扫码入口；我们用前端 Modal
    (SSE 推 base64) 作为唯一扫码入口，playwright 始终 headless 后台运行，不弹浏览器窗口。
  - 用 launch()+new_context() 而非 launch_persistent_context()：每次全新 context，
    避免 user_data_dir 残留登录态跳过二维码页面。
  - refresh_cookie 用 new_context()+add_cookies() 注入旧 Cookie 刷新。

核心流程：
  - start_qrcode_login(platform): launch → new_context → goto 登录页 → 提二维码 →
    SSE 推前端 → 轮询登录态 → 成功后 weibo goto m.weibo.cn 转 mobile Cookie →
    提 Cookie 写 DB → SSE 通知前端
  - refresh_cookie(platform, account_id): launch → new_context → add_cookies(旧) →
    goto 平台首页 → 检查登录态 → 有效提新 Cookie 写回 / 无效 mark_expired
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import AsyncGenerator, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.config import settings
from app.core.database import SessionLocal
from app.collection.cookie_store import (
    create_account,
    get_account,
    mark_expired,
    mark_valid,
)
from app.collection.platforms._shared import (
    convert_str_cookie_to_dict,
    get_pc_user_agent,
    make_async_client,
)

logger = logging.getLogger("login_engine")

# 平台登录配置：登录页 URL、二维码选择器、登录态 Cookie 标志、Cookie 域过滤、首页 URL
_PLATFORM_LOGIN_CONFIG: Dict[str, dict] = {
    "微博": {
        "login_url": "https://passport.weibo.com/sso/signin?entry=miniblog&source=miniblog",
        "qrcode_selector": "xpath=//img[@class='w-full h-full']",
        "login_cookie_key": "SSOLoginState",  # 登录成功后出现的 cookie
        "cookie_urls": ["https://m.weibo.cn"],  # 搜索用 mobile 域 cookie
        "mobile_home": "https://m.weibo.cn",  # PC SSO 登录后需 goto 此页转 mobile cookie
        "cookie_domain": ".weibo.cn",
        "need_mobile_conversion": True,
    },
    "快手": {
        "login_url": "https://www.kuaishou.com",
        "qrcode_selector": "div.qrcode-img img",
        "login_cookie_key": "passToken",
        "cookie_urls": ["https://www.kuaishou.com"],
        "mobile_home": "https://www.kuaishou.com",
        "cookie_domain": ".kuaishou.com",
        "need_mobile_conversion": False,
        "click_login_button": True,  # 快手需先点"登录"按钮才出二维码
    },
    "bilibili": {
        "login_url": "https://www.bilibili.com",
        "qrcode_selector": "div.login-scan-box img",
        "login_cookie_key": "SESSDATA",  # 登录成功后出现的 cookie
        "cookie_urls": ["https://www.bilibili.com"],
        "mobile_home": "https://www.bilibili.com",
        "cookie_domain": ".bilibili.com",
        "need_mobile_conversion": False,
        "click_login_button": True,  # bilibili 需先点"登录"按钮才出二维码面板
        "click_login_selector": "xpath=//div[@class='right-entry__outside go-login-btn']//div",
    },
}

# per-platform 锁，防并发登录/刷新
_login_locks: Dict[str, asyncio.Lock] = {}

def _get_lock(platform: str) -> asyncio.Lock:
    if platform not in _login_locks:
        _login_locks[platform] = asyncio.Lock()
    return _login_locks[platform]

async def _launch_browser(playwright) -> Browser:
    """启动浏览器：优先系统 Chrome（反检测更好），失败回退 playwright 自带 chromium。

    始终 headless（由 settings.collection_login_headless 控制，默认 True），
    不弹浏览器窗口——前端 Modal 是唯一扫码入口。
    """
    headless = settings.collection_login_headless
    args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    try:
        return await playwright.chromium.launch(
            channel="chrome", headless=headless, args=args,
        )
    except Exception:
        return await playwright.chromium.launch(headless=headless, args=args)

async def _new_context(browser: Browser) -> BrowserContext:
    """创建全新浏览器 context（无 user_data_dir 残留）。"""
    return await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=get_pc_user_agent(),
    )

async def _extract_qrcode_base64(page: Page, selector: str) -> str:
    """从页面提取二维码图片 base64。用 get_attribute 替代 get_property。"""
    try:
        element = await page.wait_for_selector(selector=selector, timeout=15000)
        src = await element.get_attribute("src")
        if not src:
            return ""
        if src.startswith("data:image"):
            return src.split(",", 1)[1] if "," in src else src
        if src.startswith("http"):
            async with make_async_client() as client:
                resp = await client.get(src, headers={"User-Agent": get_pc_user_agent()})
                if resp.status_code == 200:
                    return base64.b64encode(resp.content).decode("utf-8")
            return ""
        # src 可能本身就是 base64
        return src
    except Exception as exc:
        logger.error(f"[login_engine] 提取二维码失败: {exc}")
        return ""

async def _check_logged_in(context: BrowserContext, login_cookie_key: str) -> bool:
    """轮询登录态：检查指定 cookie 是否出现。"""
    cookies = await context.cookies()
    cookie_dict = {c.get("name"): c.get("value") for c in cookies}
    return bool(cookie_dict.get(login_cookie_key))

async def _goto_and_maybe_convert(
    page: Page, context: BrowserContext, config: dict
) -> tuple[str, dict]:
    """登录成功后：weibo 需 goto m.weibo.cn 转 mobile cookie；提取目标域 cookie。"""
    if config["need_mobile_conversion"]:
        # 复刻mobile 首页同步 SSO cookie 到 mobile 域
        await page.goto(config["mobile_home"])
        await asyncio.sleep(3)
    cookies = await context.cookies(urls=config["cookie_urls"])
    from app.collection.platforms._shared import convert_cookies
    return convert_cookies(cookies)

async def start_qrcode_login(platform: str) -> AsyncGenerator[dict, None]:
    """扫码登录流程，yield SSE 事件 dict。

    事件类型：
      - {"event":"qrcode","data":{"image": base64}}
      - {"event":"success","data":{"account_id": id}}
      - {"event":"timeout","data":{}}
      - {"event":"error","data":{"message": str}}
    """
    if platform not in _PLATFORM_LOGIN_CONFIG:
        yield {"event": "error", "data": {"message": f"不支持的平台: {platform}"}}
        return

    config = _PLATFORM_LOGIN_CONFIG[platform]
    lock = _get_lock(platform)
    if lock.locked():
        yield {"event": "error", "data": {"message": f"{platform} 已有登录进行中，请稍后"}}
        return

    async with lock:
        async with async_playwright() as playwright:
            browser = await _launch_browser(playwright)
            context = await _new_context(browser)
            page = await context.new_page()
            try:
                await page.goto(config["login_url"], wait_until="domcontentloaded")
                await asyncio.sleep(2)

                # 需点击"登录"按钮才出二维码（快手/bilibili）
                if config.get("click_login_button"):
                    try:
                        selector = config.get("click_login_selector", "xpath=//p[text()='登录']")
                        await page.locator(selector).click(timeout=5000)
                        await asyncio.sleep(1)
                    except Exception:
                        pass  # 可能已在登录面板

                qr_base64 = await _extract_qrcode_base64(page, config["qrcode_selector"])
                if not qr_base64:
                    yield {"event": "error", "data": {"message": "未找到登录二维码，平台页面可能已改版"}}
                    return

                yield {"event": "qrcode", "data": {"image": qr_base64}}

                # 轮询登录态，最长 collection_login_timeout 秒
                deadline = asyncio.get_event_loop().time() + settings.collection_login_timeout
                logged_in = False
                while asyncio.get_event_loop().time() < deadline:
                    if await _check_logged_in(context, config["login_cookie_key"]):
                        logged_in = True
                        break
                    await asyncio.sleep(1)

                if not logged_in:
                    yield {"event": "timeout", "data": {}}
                    return

                # 登录成功 → weibo 转 mobile cookie → 提 Cookie 写 DB
                await asyncio.sleep(3)  # 等重定向完成
                cookie_str, cookie_dict = await _goto_and_maybe_convert(page, context, config)
                if not cookie_str:
                    yield {"event": "error", "data": {"message": "登录成功但未提取到 Cookie"}}
                    return

                with SessionLocal() as db:
                    account = create_account(
                        db,
                        platform=platform,
                        cookie_str=cookie_str,
                        cookie_dict=cookie_dict,
                        validated_by="qrcode",
                    )
                    db.commit()
                    account_id = account.id

                logger.info(f"[login_engine] {platform} 扫码登录成功，account_id={account_id}")
                yield {"event": "success", "data": {"account_id": account_id, "platform": platform}}
            finally:
                await context.close()
                await browser.close()

async def refresh_cookie(platform: str, account_id: int) -> bool:
    """按需刷新 Cookie：launch → new_context → add_cookies(旧) → goto 首页 → 提新 Cookie。

    复刻432 降级（client.py:89-91 goto+update_cookies）与
    kuaishou 被拦恢复（core.py:289-303 goto+sleep+update_cookies）。

    :return: True 刷新成功；False SSO 也过期，需重新扫码
    """
    if platform not in _PLATFORM_LOGIN_CONFIG:
        return False

    config = _PLATFORM_LOGIN_CONFIG[platform]
    lock = _get_lock(platform)
    async with lock:
        with SessionLocal() as db:
            account = get_account(db, account_id)
            if not account:
                return False
            old_cookie_str = account.cookie_str

        async with async_playwright() as playwright:
            browser = await _launch_browser(playwright)
            context = await _new_context(browser)
            page = await context.new_page()
            try:
                # 注入旧 Cookie（复刻login_by_cookies）
                if old_cookie_str:
                    cookie_dict = convert_str_cookie_to_dict(old_cookie_str)
                    cookie_list = [
                        {"name": k, "value": v, "domain": config["cookie_domain"], "path": "/"}
                        for k, v in cookie_dict.items()
                    ]
                    if cookie_list:
                        await context.add_cookies(cookie_list)

                # goto 平台首页，让浏览器用旧 SSO cookie 刷新 mobile 域 cookie
                await page.goto(config["mobile_home"], wait_until="domcontentloaded")
                await asyncio.sleep(3)

                if not await _check_logged_in(context, config["login_cookie_key"]):
                    # SSO 也过期，需重新扫码
                    with SessionLocal() as db:
                        mark_expired(db, account_id)
                        db.commit()
                    logger.warning(f"[login_engine] {platform} account {account_id} SSO 过期，需重新扫码")
                    return False

                # 登录态有效 → 提新 Cookie 写回 DB
                if config["need_mobile_conversion"]:
                    await page.goto(config["mobile_home"])
                    await asyncio.sleep(2)
                cookies = await context.cookies(urls=config["cookie_urls"])
                from app.collection.platforms._shared import convert_cookies
                new_cookie_str, new_cookie_dict = convert_cookies(cookies)
                if not new_cookie_str:
                    return False

                with SessionLocal() as db:
                    mark_valid(db, account_id, cookie_str=new_cookie_str)
                    db.commit()
                logger.info(f"[login_engine] {platform} account {account_id} Cookie 刷新成功")
                return True
            finally:
                await context.close()
                await browser.close()

async def validate_account_cookie(platform: str, account_id: int) -> bool:
    """用平台 client 的 pong 校验账号 Cookie 是否有效，无效则 mark_pending_refresh。"""
    from app.collection.platforms import get_platform_client
    from app.collection.cookie_store import mark_pending_refresh

    with SessionLocal() as db:
        account = get_account(db, account_id)
        if not account:
            return False
        client = get_platform_client(platform, account.cookie_str)
        ok = await client.pong()
        if not ok:
            mark_pending_refresh(db, account_id)
            db.commit()
        return ok
