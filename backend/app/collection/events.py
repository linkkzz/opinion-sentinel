from __future__ import annotations

from app.models import CollectionEvent, CollectionRun, SourceItem


def status_event(task_id: int, event_type: str, payload: dict, run_id: int | None = None) -> CollectionEvent:
    return CollectionEvent(task_id=task_id, run_id=run_id, event_type=event_type, payload=payload)


def source_item_event(item: SourceItem) -> CollectionEvent:
    return CollectionEvent(
        task_id=item.task_id,
        event_type="source_item.created",
        payload={
            "item_id": item.id,
            "platform": item.platform,
            "title": item.title,
            "author": item.author,
            "publish_time": item.publish_time.isoformat() if item.publish_time else None,
        },
    )


def run_event(run: CollectionRun, event_type: str) -> CollectionEvent:
    return CollectionEvent(
        task_id=run.task_id,
        run_id=run.id,
        event_type=event_type,
        payload={
            "run_id": run.id,
            "platform": run.platform,
            "keyword": run.keyword,
            "status": run.status,
            "imported_count": run.imported_count,
            "skipped_count": run.skipped_count,
            "error_message": run.error_message,
        },
    )
