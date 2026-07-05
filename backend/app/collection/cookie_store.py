# -*- coding: utf-8 -*-
"""采集账号 Cookie 仓库：DB 读写 + 状态流转。

collector adapter 通过 ``get_valid_cookie`` 取有效账号 Cookie；采集遇风控时调
``mark_pending_refresh`` 标记，由 backend cookie_refresher 后台任务按需刷新。
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CollectionAccount

__all__ = [
    "get_valid_cookie",
    "get_account",
    "mark_pending_refresh",
    "mark_valid",
    "mark_expired",
    "mark_login_pending",
    "list_accounts",
    "create_account",
    "delete_account",
]


def get_valid_cookie(db: Session, platform: str) -> Optional[CollectionAccount]:
    """取该平台 status=valid 的账号（多账号随机选一个）。

    返回 CollectionAccount（含 id，供 adapter 标记状态）；无可用账号返回 None。
    """
    accounts = db.scalars(
        select(CollectionAccount).where(
            CollectionAccount.platform == platform,
            CollectionAccount.status == "valid",
            CollectionAccount.cookie_str != "",
        )
    ).all()
    if not accounts:
        return None
    return random.choice(accounts)


def get_account(db: Session, account_id: int) -> Optional[CollectionAccount]:
    return db.get(CollectionAccount, account_id)


def list_accounts(db: Session, platform: Optional[str] = None) -> list[CollectionAccount]:
    stmt = select(CollectionAccount).order_by(CollectionAccount.platform, CollectionAccount.id)
    if platform:
        stmt = stmt.where(CollectionAccount.platform == platform)
    return list(db.scalars(stmt).all())


def create_account(
    db: Session,
    *,
    platform: str,
    cookie_str: str,
    cookie_dict: Optional[dict] = None,
    note: Optional[str] = None,
    validated_by: str = "qrcode",
) -> CollectionAccount:
    """新建采集账号（扫码登录成功后调用）。"""
    from app.collection.platforms._shared import convert_str_cookie_to_dict

    account = CollectionAccount(
        platform=platform,
        cookie_str=cookie_str,
        cookie_dict=cookie_dict or convert_str_cookie_to_dict(cookie_str),
        status="valid",
        last_validated_at=datetime.now(),
        validated_by=validated_by,
        note=note,
    )
    db.add(account)
    db.flush()
    return account


def mark_pending_refresh(db: Session, account_id: int) -> None:
    """标记账号 Cookie 疑似失效，待 backend playwright 刷新。"""
    db.execute(
        update(CollectionAccount)
        .where(CollectionAccount.id == account_id)
        .values(status="pending_refresh", updated_at=datetime.now())
    )


def mark_valid(db: Session, account_id: int, *, cookie_str: Optional[str] = None) -> None:
    """标记账号 Cookie 有效（pong 通过或刷新成功）。可顺带更新 cookie_str。"""
    values: dict = {"status": "valid", "last_validated_at": datetime.now(), "updated_at": datetime.now()}
    if cookie_str is not None:
        from app.collection.platforms._shared import convert_str_cookie_to_dict

        values["cookie_str"] = cookie_str
        values["cookie_dict"] = convert_str_cookie_to_dict(cookie_str)
    db.execute(update(CollectionAccount).where(CollectionAccount.id == account_id).values(**values))


def mark_expired(db: Session, account_id: int) -> None:
    """标记账号 SSO 也过期，需用户重新扫码登录。"""
    db.execute(
        update(CollectionAccount)
        .where(CollectionAccount.id == account_id)
        .values(status="expired", updated_at=datetime.now())
    )


def mark_login_pending(db: Session, account_id: Optional[int], *, platform: str) -> None:
    if account_id:
        db.execute(
            update(CollectionAccount)
            .where(CollectionAccount.id == account_id)
            .values(status="login_pending", updated_at=datetime.now())
        )


def delete_account(db: Session, account_id: int) -> bool:
    account = db.get(CollectionAccount, account_id)
    if not account:
        return False
    db.delete(account)
    return True
