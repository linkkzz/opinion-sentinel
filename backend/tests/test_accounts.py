# -*- coding: utf-8 -*-
"""采集账号管理 API 测试。mock login_engine 避免真实浏览器启动。"""
import asyncio
import io
import os
from unittest.mock import AsyncMock, patch

os.environ["DATABASE_URL"] = "sqlite:///./test_opinion_sentinel.db"
os.environ["STORAGE_ROOT"] = "./test_storage"

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.collection.cookie_store import create_account, mark_pending_refresh
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_list_accounts_empty():
    with TestClient(app) as client:
        resp = client.get("/api/collection/accounts")
        assert resp.status_code == 200
        assert resp.json() == []


def test_list_accounts_with_data():
    with TestClient(app) as client:
        with SessionLocal() as db:
            create_account(db, platform="微博", cookie_str="SUB=abc", note="测试号")
            create_account(db, platform="快手", cookie_str="passToken=x")
            db.commit()
        resp = client.get("/api/collection/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # has_cookie 不泄露真实 cookie_str
        assert all("cookie_str" not in a for a in data)
        assert all(a["has_cookie"] for a in data)


def test_overview_returns_both_platforms():
    with TestClient(app) as client:
        with SessionLocal() as db:
            create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
        resp = client.get("/api/collection/accounts/overview")
        assert resp.status_code == 200
        data = resp.json()
        platforms = {d["platform"] for d in data}
        assert platforms == {"微博", "快手", "bilibili"}
        wb = next(d for d in data if d["platform"] == "微博")
        assert wb["account_count"] == 1
        assert wb["valid_count"] == 1
        assert wb["account_status"] == "valid"
        ks = next(d for d in data if d["platform"] == "快手")
        assert ks["account_status"] == "none"
        assert ks["account_count"] == 0


def test_overview_status_pending_refresh():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            mark_pending_refresh(db, a.id)
            db.commit()
        resp = client.get("/api/collection/accounts/overview")
        wb = next(d for d in resp.json() if d["platform"] == "微博")
        assert wb["account_status"] == "pending_refresh"
        assert wb["valid_count"] == 0


def test_delete_account():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            aid = a.id
        resp = client.delete(f"/api/collection/accounts/{aid}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # 再删返回 404
        resp = client.delete(f"/api/collection/accounts/{aid}")
        assert resp.status_code == 404


def test_validate_account_calls_pong():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            aid = a.id
        with patch("app.api.accounts.validate_account_cookie", new=AsyncMock(return_value=True)):
            resp = client.post(f"/api/collection/accounts/{aid}/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


def test_validate_account_marks_pending_when_invalid():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            aid = a.id
        # validate_account_cookie 内部 pong 失败会 mark_pending_refresh
        with patch("app.collection.platforms.get_platform_client") as mock_gpc:
            mock_client = AsyncMock()
            mock_client.pong = AsyncMock(return_value=False)
            mock_gpc.return_value = mock_client
            resp = client.post(f"/api/collection/accounts/{aid}/validate")
        assert resp.json()["valid"] is False
        with SessionLocal() as db:
            from app.models import CollectionAccount
            acc = db.get(CollectionAccount, aid)
            assert acc.status == "pending_refresh"


def test_manual_refresh():
    with TestClient(app) as client:
        with SessionLocal() as db:
            a = create_account(db, platform="微博", cookie_str="SUB=abc")
            db.commit()
            aid = a.id
        with patch("app.api.accounts.refresh_cookie", new=AsyncMock(return_value=True)):
            resp = client.post(f"/api/collection/accounts/{aid}/refresh")
        assert resp.status_code == 200
        assert resp.json()["refreshed"] is True


def test_login_unsupported_platform():
    with TestClient(app) as client:
        resp = client.get("/api/collection/accounts/login", params={"platform": "小红书"})
        assert resp.status_code == 400


def test_login_sse_streams_events():
    """mock start_qrcode_login，验证 SSE 事件流格式（GET，EventSource 兼容）。"""
    async def fake_login(platform):
        yield {"event": "qrcode", "data": {"image": "fake_base64"}}
        yield {"event": "success", "data": {"account_id": 1, "platform": platform}}

    with TestClient(app) as client:
        with patch("app.api.accounts.start_qrcode_login", side_effect=fake_login):
            resp = client.get("/api/collection/accounts/login", params={"platform": "微博"})
        assert resp.status_code == 200
        body = resp.text
        assert "event: qrcode" in body
        assert "event: success" in body
        assert "fake_base64" in body


def test_global_collection_feed_returns_task_name():
    """全局 feed 返回跨任务最新入库内容，含 task_name。"""
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={
            "name": "全局feed测试", "keywords": ["食堂"], "platforms": ["微博"],
        }).json()["id"]
        with SessionLocal() as db:
            from app.models import SourceItem
            from datetime import datetime
            db.add(SourceItem(
                task_id=task_id, platform="微博", title="全局feed条目",
                author="测试", content="内容", dedupe_key="g-feed-1",
                publish_time=datetime.now(), created_at=datetime.now(),
            ))
            db.commit()
        resp = client.get("/api/collection/feed", params={"page_size": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        item = next(i for i in data["items"] if i["title"] == "全局feed条目")
        assert item["task_name"] == "全局feed测试"
        assert item["platform"] == "微博"
