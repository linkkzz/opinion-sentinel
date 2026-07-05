from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Platform = Literal["微博", "小红书", "快手", "bilibili", "抖音", "微信公众号", "其他"]
Sentiment = Literal["positive", "neutral", "negative"]
RiskLevel = Literal["low", "medium", "high"]


class TaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1)
    platforms: list[Platform] = Field(min_length=1)
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None
    collection_enabled: bool = True
    collection_interval_seconds: int = Field(default=300, ge=60)

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("开始时间不能晚于结束时间")
        return self


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    keywords: list[str] | None = None
    platforms: list[Platform] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None
    collection_enabled: bool | None = None
    collection_interval_seconds: int | None = Field(default=None, ge=60)


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    analysis_enabled: bool
    analysis_state: str
    collection_enabled: bool
    collection_state: str
    collection_interval_seconds: int
    created_at: datetime
    updated_at: datetime


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    revision_no: int
    sentiment: str
    risk_level: str
    confidence: float | None
    reason: str
    topics: list[str]
    source: str
    model_name: str | None
    change_note: str | None
    created_at: datetime


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    media_type: str
    original_name: str
    storage_path: str


class SourceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    platform: str
    external_id: str | None
    title: str
    author: str
    publish_time: datetime | None
    content: str
    source_url: str | None
    like_count: int
    comment_count: int
    share_count: int
    view_count: int
    interaction_count: int
    analysis_status: str
    analysis_error: str | None
    created_at: datetime
    current_analysis: AnalysisRead | None = None
    media: list[MediaRead] = []


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    platform: str
    keyword: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    imported_count: int
    skipped_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class CollectionPlatformStatus(BaseModel):
    platform: str
    state: str
    latest_run: CollectionRunRead | None = None
    latest_success_at: datetime | None = None
    next_run_at: datetime | None = None
    imported_total: int = 0
    skipped_total: int = 0
    latest_imported: int = 0
    error_message: str | None = None


class CollectionStatusRead(BaseModel):
    task_id: int
    enabled: bool
    state: str
    interval_seconds: int
    current_round_imported: int
    today_imported: int
    total_imported: int
    latest_success_at: datetime | None
    next_run_at: datetime | None
    platforms: list[CollectionPlatformStatus]


class ManualAnalysisUpdate(BaseModel):
    sentiment: Sentiment
    risk_level: RiskLevel
    reason: str = Field(min_length=1)
    topics: list[str] = []
    change_note: str = Field(min_length=1, max_length=500)


class CollectionAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: str
    status: str
    last_validated_at: datetime | None
    validated_by: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime
    has_cookie: bool

    @classmethod
    def from_account(cls, account) -> "CollectionAccountRead":
        return cls(
            id=account.id,
            platform=account.platform,
            status=account.status,
            last_validated_at=account.last_validated_at,
            validated_by=account.validated_by,
            note=account.note,
            created_at=account.created_at,
            updated_at=account.updated_at,
            has_cookie=bool(account.cookie_str),
        )


class CollectionAccountOverview(BaseModel):
    """采集中心仪表盘单平台概览。"""
    platform: str
    account_status: str  # valid / pending_refresh / expired / none
    account_count: int
    valid_count: int
    today_imported: int
    total_imported: int
    total_skipped: int
    last_success_at: datetime | None
    recent_runs: list[dict] = []  # 最近 N 轮采集


class LoginRequest(BaseModel):
    platform: str


class StrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    version_no: int
    analyzed_count: int
    content: str
    generation_status: str
    generation_error: str | None
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime


class ContentUpdate(BaseModel):
    content: str = Field(min_length=1)


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    version_no: int
    content: str
    generation_status: str
    generation_error: str | None
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime
