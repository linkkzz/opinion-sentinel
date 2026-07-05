from __future__ import annotations

from app.collection.adapters import get_adapter
from app.collection.repository import cursor_for_run, fail_run, finish_run, insert_items
from app.core.config import settings
from app.models import CollectionRun
from sqlalchemy.orm import Session


async def run_collection(db: Session, run: CollectionRun) -> None:
    cursor = cursor_for_run(db, run)
    since = cursor.last_external_time or cursor.last_success_at if cursor else None
    task = run.task
    until = task.end_time if task else None
    try:
        adapter = get_adapter(run.platform)
        raw_items = await adapter.collect(keyword=run.keyword, since=since, until=until, limit=settings.collection_batch_size)
        imported, skipped, latest_external_time = insert_items(db, run.task_id, raw_items)
        finish_run(db, run, imported, skipped, latest_external_time)
    except Exception as exc:
        fail_run(db, run, str(exc))
