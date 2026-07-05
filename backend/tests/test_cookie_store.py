# -*- coding: utf-8 -*-
"""cookie_store 单元测试：用独立 in-memory sqlite，不依赖全局 DB 配置。"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.collection.cookie_store import (
    create_account,
    delete_account,
    get_valid_cookie,
    list_accounts,
    mark_expired,
    mark_pending_refresh,
    mark_valid,
)


def _fresh_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_get_valid_cookie_returns_none_when_empty():
    with _fresh_db() as db:
        assert get_valid_cookie(db, "微博") is None


def test_create_and_get_valid_cookie():
    with _fresh_db() as db:
        a = create_account(db, platform="微博", cookie_str="SUB=abc", note="测试号")
        db.commit()
        acc = get_valid_cookie(db, "微博")
        assert acc is not None
        assert acc.id == a.id
        assert acc.cookie_str == "SUB=abc"
        assert acc.status == "valid"


def test_get_valid_cookie_skips_pending_refresh():
    with _fresh_db() as db:
        a1 = create_account(db, platform="微博", cookie_str="SUB=abc")
        a2 = create_account(db, platform="微博", cookie_str="SUB=xyz")
        db.commit()
        mark_pending_refresh(db, a1.id)
        db.commit()
        acc = get_valid_cookie(db, "微博")
        assert acc is not None
        assert acc.id == a2.id, "pending_refresh 账号不应被选用"


def test_get_valid_cookie_returns_none_when_all_pending():
    with _fresh_db() as db:
        a1 = create_account(db, platform="微博", cookie_str="SUB=abc")
        db.commit()
        mark_pending_refresh(db, a1.id)
        db.commit()
        assert get_valid_cookie(db, "微博") is None


def test_mark_valid_restores_and_updates_cookie():
    with _fresh_db() as db:
        a = create_account(db, platform="微博", cookie_str="old=1")
        db.commit()
        mark_pending_refresh(db, a.id)
        db.commit()
        assert get_valid_cookie(db, "微博") is None
        mark_valid(db, a.id, cookie_str="new=2")
        db.commit()
        acc = get_valid_cookie(db, "微博")
        assert acc is not None
        assert acc.cookie_str == "new=2"
        assert acc.cookie_dict == {"new": "2"}


def test_mark_expired():
    with _fresh_db() as db:
        a = create_account(db, platform="快手", cookie_str="passToken=x")
        db.commit()
        mark_expired(db, a.id)
        db.commit()
        assert get_valid_cookie(db, "快手") is None
        db.refresh(a)
        assert a.status == "expired"


def test_list_accounts_filter_by_platform():
    with _fresh_db() as db:
        create_account(db, platform="微博", cookie_str="a=1")
        create_account(db, platform="微博", cookie_str="b=2")
        create_account(db, platform="快手", cookie_str="c=3")
        db.commit()
        assert len(list_accounts(db)) == 3
        assert len(list_accounts(db, "微博")) == 2
        assert len(list_accounts(db, "快手")) == 1


def test_delete_account():
    with _fresh_db() as db:
        a = create_account(db, platform="微博", cookie_str="a=1")
        db.commit()
        assert delete_account(db, a.id) is True
        db.commit()
        assert get_valid_cookie(db, "微博") is None
        assert delete_account(db, 999) is False


def test_get_valid_cookie_random_among_multiple():
    """多账号随机选用，验证不总是返回同一个。"""
    with _fresh_db() as db:
        for i in range(5):
            create_account(db, platform="微博", cookie_str=f"SUB={i}")
        db.commit()
        picked = {get_valid_cookie(db, "微博").cookie_str for _ in range(30)}
        assert len(picked) >= 2, "多账号应随机选用，不应总返回同一个"
