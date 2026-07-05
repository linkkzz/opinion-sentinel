from __future__ import annotations

import asyncio
import logging

from app.collection.repository import claim_next_run
from app.collection.runner import run_collection
from app.collection.scheduler import schedule_due_runs
from app.core.config import settings
from app.core.database import Base, apply_lightweight_migrations, engine, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def collection_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        with SessionLocal() as db:
            schedule_due_runs(db)
            db.commit()
            run = claim_next_run(db)
            db.commit()
            if run:
                await run_collection(db, run)
                db.commit()
        await asyncio.sleep(settings.collection_poll_seconds)


async def main() -> None:
    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations()
    stop_event = asyncio.Event()
    logger.info("collector worker started")
    await collection_loop(stop_event)


if __name__ == "__main__":
    asyncio.run(main())
