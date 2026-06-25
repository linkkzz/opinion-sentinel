from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AnalysisRevision, SourceItem, Task
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(Task).order_by(Task.created_at.desc())).all()


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    if task.start_time and task.end_time and task.start_time > task.end_time:
        raise HTTPException(422, "开始时间不能晚于结束时间")
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    task.status = "completed"
    task.analysis_enabled = False
    task.analysis_state = "stopped"
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/reopen", response_model=TaskRead)
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    task.status = "running"
    task.analysis_state = "paused"
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.get("/{task_id}/stats")
def task_stats(task_id: int, db: Session = Depends(get_db)):
    if not db.get(Task, task_id):
        raise HTTPException(404, "任务不存在")
    total = db.scalar(select(func.count(SourceItem.id)).where(SourceItem.task_id == task_id)) or 0
    analyzed = db.scalar(
        select(func.count(SourceItem.id)).where(SourceItem.task_id == task_id, SourceItem.analysis_status == "analyzed")
    ) or 0
    risk_rows = db.execute(
        select(AnalysisRevision.risk_level, func.count(SourceItem.id))
        .join(SourceItem, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(SourceItem.task_id == task_id)
        .group_by(AnalysisRevision.risk_level)
    ).all()
    sentiment_rows = db.execute(
        select(AnalysisRevision.sentiment, func.count(SourceItem.id))
        .join(SourceItem, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(SourceItem.task_id == task_id)
        .group_by(AnalysisRevision.sentiment)
    ).all()
    platform_rows = db.execute(
        select(SourceItem.platform, func.count(SourceItem.id))
        .where(SourceItem.task_id == task_id)
        .group_by(SourceItem.platform)
    ).all()
    engagement = db.execute(
        select(
            func.coalesce(func.sum(SourceItem.like_count), 0),
            func.coalesce(func.sum(SourceItem.comment_count), 0),
            func.coalesce(func.sum(SourceItem.share_count), 0),
            func.coalesce(func.sum(SourceItem.interaction_count), 0),
            func.coalesce(func.sum(SourceItem.view_count), 0),
        ).where(SourceItem.task_id == task_id)
    ).one()
    trend_rows = db.execute(
        select(func.date(SourceItem.publish_time), func.count(SourceItem.id))
        .where(SourceItem.task_id == task_id, SourceItem.publish_time.is_not(None))
        .group_by(func.date(SourceItem.publish_time))
        .order_by(func.date(SourceItem.publish_time))
    ).all()
    analysis_rows = db.execute(
        select(
            SourceItem.publish_time,
            AnalysisRevision.risk_level,
            AnalysisRevision.sentiment,
            AnalysisRevision.topics,
        )
        .join(AnalysisRevision, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(SourceItem.task_id == task_id)
    ).all()
    risk_trend: dict[str, Counter] = defaultdict(Counter)
    sentiment_trend: dict[str, Counter] = defaultdict(Counter)
    topics: Counter = Counter()
    for publish_time, risk_level, sentiment, topic_list in analysis_rows:
        if publish_time:
            date_key = publish_time.strftime("%Y-%m-%d")
            risk_trend[date_key][risk_level] += 1
            sentiment_trend[date_key][sentiment] += 1
        topics.update(topic_list or [])
    return {
        "total": total,
        "analyzed": analyzed,
        "pending": total - analyzed,
        "analysis_rate": round(analyzed / total * 100, 1) if total else 0,
        "risks": dict(risk_rows),
        "sentiments": dict(sentiment_rows),
        "platforms": dict(platform_rows),
        "engagement": {
            "likes": int(engagement[0]),
            "comments": int(engagement[1]),
            "shares": int(engagement[2]),
            "interactions": int(engagement[3]),
            "views": int(engagement[4]),
        },
        "trend": [{"date": str(date), "count": count} for date, count in trend_rows],
        "risk_trend": [
            {"date": date, "low": values["low"], "medium": values["medium"], "high": values["high"]}
            for date, values in sorted(risk_trend.items())
        ],
        "sentiment_trend": [
            {"date": date, "positive": values["positive"], "neutral": values["neutral"], "negative": values["negative"]}
            for date, values in sorted(sentiment_trend.items())
        ],
        "topics": [{"name": name, "value": value} for name, value in topics.most_common(16)],
    }


@router.get("/overview/dashboard")
def dashboard_overview(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Task.id))) or 0
    completed = db.scalar(select(func.count(Task.id)).where(Task.status == "completed")) or 0
    data_total = db.scalar(select(func.count(SourceItem.id))) or 0
    high_risk = db.scalar(
        select(func.count(SourceItem.id))
        .join(AnalysisRevision, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(AnalysisRevision.risk_level == "high")
    ) or 0
    analyzed = db.scalar(
        select(func.count(SourceItem.id)).where(SourceItem.analysis_status == "analyzed")
    ) or 0
    negative = db.scalar(
        select(func.count(SourceItem.id))
        .join(AnalysisRevision, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(AnalysisRevision.sentiment == "negative")
    ) or 0
    engagement = db.execute(
        select(
            func.coalesce(func.sum(SourceItem.interaction_count), 0),
            func.coalesce(func.sum(SourceItem.view_count), 0),
        )
    ).one()
    return {
        "tasks": total,
        "running": total - completed,
        "completed": completed,
        "data_total": data_total,
        "analyzed": analyzed,
        "analysis_rate": round(analyzed / data_total * 100, 1) if data_total else 0,
        "high_risk": high_risk,
        "negative": negative,
        "interactions": int(engagement[0]),
        "views": int(engagement[1]),
        "generated_at": datetime.now(),
    }
