from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class RawCollectedItem:
    platform: str
    external_id: str
    title: str
    author: str
    publish_time: datetime | None
    content: str
    source_url: str | None = None
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0


class CollectionAdapter(Protocol):
    platform: str

    async def collect(
        self,
        *,
        keyword: str,
        since: datetime | None,
        until: datetime | None,
        limit: int,
    ) -> list[RawCollectedItem]:
        """Collect new items for one task keyword."""
