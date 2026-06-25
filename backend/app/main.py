import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import items, reports, strategies, tasks
from app.core.config import settings
from app.core.database import Base, apply_lightweight_migrations, engine
from app.services.analysis_worker import analysis_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations()
    stop_event = asyncio.Event()
    worker = asyncio.create_task(analysis_loop(stop_event))
    yield
    stop_event.set()
    await worker


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks.router, prefix=settings.api_prefix)
app.include_router(items.router, prefix=settings.api_prefix)
app.include_router(strategies.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
settings.storage_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.storage_root), name="media")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": settings.app_name}
