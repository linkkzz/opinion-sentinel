from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def now() -> datetime:
    return datetime.now()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    analysis_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    analysis_state: Mapped[str] = mapped_column(String(32), default="not_started")
    collection_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    collection_state: Mapped[str] = mapped_column(String(32), default="idle", index=True)
    collection_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    items: Mapped[list[SourceItem]] = relationship(back_populates="task", cascade="all, delete-orphan")
    strategies: Mapped[list[StrategyVersion]] = relationship(back_populates="task", cascade="all, delete-orphan")
    reports: Mapped[list[ReportVersion]] = relationship(back_populates="task", cascade="all, delete-orphan")
    collection_cursors: Mapped[list[CollectionCursor]] = relationship(back_populates="task", cascade="all, delete-orphan")
    collection_runs: Mapped[list[CollectionRun]] = relationship(back_populates="task", cascade="all, delete-orphan")
    collection_events: Mapped[list[CollectionEvent]] = relationship(back_populates="task", cascade="all, delete-orphan")


class SourceItem(Base):
    __tablename__ = "source_items"
    __table_args__ = (UniqueConstraint("task_id", "dedupe_key", name="uq_task_item_dedupe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    author: Mapped[str] = mapped_column(String(200), default="未知")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    analysis_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_analysis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    task: Mapped[Task] = relationship(back_populates="items")
    media: Mapped[list[MediaAsset]] = relationship(back_populates="item", cascade="all, delete-orphan")
    analyses: Mapped[list[AnalysisRevision]] = relationship(
        back_populates="item", cascade="all, delete-orphan", foreign_keys="AnalysisRevision.item_id"
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id", ondelete="CASCADE"), index=True)
    media_type: Mapped[str] = mapped_column(String(16))
    original_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    item: Mapped[SourceItem] = relationship(back_populates="media")


class CollectionCursor(Base):
    __tablename__ = "collection_cursors"
    __table_args__ = (UniqueConstraint("task_id", "platform", "keyword", name="uq_collection_cursor_unit"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_external_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    task: Mapped[Task] = relationship(back_populates="collection_cursors")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    task: Mapped[Task] = relationship(back_populates="collection_runs")
    events: Mapped[list[CollectionEvent]] = relationship(back_populates="run", cascade="all, delete-orphan")


class CollectionEvent(Base):
    __tablename__ = "collection_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)

    task: Mapped[Task] = relationship(back_populates="collection_events")
    run: Mapped[CollectionRun | None] = relationship(back_populates="events")


class CollectionAccount(Base):
    """采集平台登录账号（Cookie 持久化）。

    status 取值：
      - valid: Cookie 有效，可被 collector 选用
      - pending_refresh: 检测到风控（pong 失败/432/errors），等待 backend playwright 刷新
      - expired: 刷新后仍无登录态（SSO 也过期），需用户重新扫码
      - login_pending: 扫码登录进行中
    """

    __tablename__ = "collection_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    cookie_str: Mapped[str] = mapped_column(Text, default="")
    cookie_dict: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="valid", index=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    validated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AnalysisRevision(Base):
    __tablename__ = "analysis_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id", ondelete="CASCADE"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    sentiment: Mapped[str] = mapped_column(String(16), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(16), default="ai")
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    item: Mapped[SourceItem] = relationship(back_populates="analyses", foreign_keys=[item_id])


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list)
    analyzed_count: Mapped[int] = mapped_column(Integer)
    ai_content: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    generation_status: Mapped[str] = mapped_column(String(32), default="completed", index=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    task: Mapped[Task] = relationship(back_populates="strategies")


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    ai_content: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    generation_status: Mapped[str] = mapped_column(String(32), default="completed", index=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    task: Mapped[Task] = relationship(back_populates="reports")
