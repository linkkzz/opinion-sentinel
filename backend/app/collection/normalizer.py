from __future__ import annotations

import hashlib

from app.collection.adapters.base import RawCollectedItem


def dedupe_key(platform: str, external_id: str) -> str:
    return hashlib.sha256(f"{platform}:{external_id}".encode("utf-8")).hexdigest()


def normalize_item(item: RawCollectedItem) -> dict:
    like_count = max(0, int(item.like_count or 0))
    comment_count = max(0, int(item.comment_count or 0))
    share_count = max(0, int(item.share_count or 0))
    view_count = max(0, int(item.view_count or 0))
    return {
        "platform": item.platform,
        "external_id": item.external_id,
        "title": item.title[:500] if item.title else "无标题",
        "author": item.author[:200] if item.author else "未知",
        "publish_time": item.publish_time,
        "content": item.content,
        "source_url": item.source_url,
        "like_count": like_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "view_count": view_count,
        "interaction_count": like_count + comment_count + share_count,
        "dedupe_key": dedupe_key(item.platform, item.external_id),
        "analysis_status": "pending",
    }
