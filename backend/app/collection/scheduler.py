from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.collection.repository import enqueue_due_runs


def schedule_due_runs(db: Session, now: datetime | None = None) -> int:
    return enqueue_due_runs(db, now)
