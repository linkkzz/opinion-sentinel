from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Platform = Literal["微博", "小红书", "快手", "抖音", "微信公众号", "其他"]
Sentiment = Literal["positive", "neutral", "negative"]
RiskLevel = Literal["low", "medium", "high"]


class TaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1)
    platforms: list[Platform] = Field(min_length=1)
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None

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


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    analysis_enabled: bool
    analysis_state: str
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


class ManualAnalysisUpdate(BaseModel):
    sentiment: Sentiment
    risk_level: RiskLevel
    reason: str = Field(min_length=1)
    topics: list[str] = []
    change_note: str = Field(min_length=1, max_length=500)


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
