import asyncio
import logging

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AnalysisRevision, SourceItem, Task
from app.services.ollama import OllamaError, analyze_item

logger = logging.getLogger(__name__)


async def analysis_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        claimed: dict | None = None
        with SessionLocal() as db:
            item = db.scalar(
                select(SourceItem)
                .join(Task)
                .where(
                    Task.status == "running",
                    Task.analysis_enabled.is_(True),
                    SourceItem.analysis_status.in_(["pending", "failed"]),
                )
                .order_by(SourceItem.id)
                .limit(1)
            )
            if item:
                item.analysis_status = "analyzing"
                item.analysis_error = None
                item.task.analysis_state = "running"
                claimed = {"id": item.id, "title": item.title, "content": item.content, "platform": item.platform}
                db.commit()
            else:
                active_tasks = db.scalars(
                    select(Task).where(Task.status == "running", Task.analysis_enabled.is_(True))
                ).all()
                changed = False
                for task in active_tasks:
                    if task.analysis_state != "waiting":
                        task.analysis_state = "waiting"
                        changed = True
                if changed:
                    db.commit()

        if not claimed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.analysis_poll_seconds)
            except TimeoutError:
                pass
            continue

        try:
            result = await analyze_item(claimed["title"], claimed["content"], claimed["platform"])
            with SessionLocal() as db:
                item = db.get(SourceItem, claimed["id"])
                if not item:
                    continue
                latest_no = db.scalar(
                    select(func.coalesce(func.max(AnalysisRevision.revision_no), 0)).where(
                        AnalysisRevision.item_id == item.id
                    )
                )
                revision = AnalysisRevision(
                    item_id=item.id,
                    revision_no=int(latest_no) + 1,
                    sentiment=result["sentiment"],
                    risk_level=result["risk_level"],
                    confidence=result["confidence"],
                    reason=result["reason"],
                    topics=result["topics"],
                    source="ai",
                    model_name=settings.ollama_model,
                )
                db.add(revision)
                db.flush()
                item.current_analysis_id = revision.id
                item.analysis_status = "analyzed"
                db.commit()
        except OllamaError as exc:
            logger.warning("analysis failed for item %s: %s", claimed["id"], exc)
            with SessionLocal() as db:
                item = db.get(SourceItem, claimed["id"])
                if item:
                    item.analysis_status = "failed"
                    item.analysis_error = str(exc)
                    item.task.analysis_enabled = False
                    item.task.analysis_state = "error"
                    db.commit()
            await asyncio.sleep(settings.analysis_poll_seconds)
        except Exception:
            logger.exception("unexpected analysis worker error")
            await asyncio.sleep(settings.analysis_poll_seconds)

