from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ReportVersion, StrategyVersion, Task
from app.schemas import ContentUpdate, ReportRead
from app.services.ollama import OllamaError, generate_report
from app.services.reports import render_report_pdf
from app.services.snapshots import current_evidence, evidence_as_text, evidence_hash

router = APIRouter(prefix="/tasks/{task_id}/reports", tags=["任务报告"])


def _report_state(db: Session, task: Task) -> dict:
    if task.status != "completed":
        return {"state": "unavailable", "reason": "任务完结后才能生成报告", "report_id": None}
    evidence = current_evidence(db, task.id)
    if not evidence:
        return {"state": "unavailable", "reason": "至少需要一条已研判数据", "report_id": None}
    snapshot = evidence_hash(evidence)
    running = db.scalar(
        select(ReportVersion)
        .where(ReportVersion.task_id == task.id, ReportVersion.generation_status == "generating")
        .order_by(ReportVersion.version_no.desc())
        .limit(1)
    )
    if running:
        return {"state": "generating", "reason": "任务报告正在生成中", "report_id": None, "snapshot_hash": snapshot}
    latest = db.scalar(
        select(ReportVersion)
        .where(ReportVersion.task_id == task.id, ReportVersion.generation_status == "completed")
        .order_by(ReportVersion.version_no.desc())
        .limit(1)
    )
    if latest and latest.snapshot_hash == snapshot:
        return {"state": "ready", "reason": "当前任务报告已生成", "report_id": latest.id, "snapshot_hash": snapshot}
    return {"state": "available", "reason": "可以生成任务报告", "report_id": None, "snapshot_hash": snapshot}


@router.get("", response_model=list[ReportRead])
def list_reports(task_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(ReportVersion).where(ReportVersion.task_id == task_id).order_by(ReportVersion.version_no.desc())
    ).all()


@router.get("/status")
def report_status(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return _report_state(db, task)


@router.post("", response_model=ReportRead)
async def create_report(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    state = _report_state(db, task)
    if state["state"] == "generating":
        raise HTTPException(409, "任务报告正在生成中，请勿重复提交")
    if state["state"] == "ready":
        raise HTTPException(409, "当前任务报告已生成，无需重复生成")
    if state["state"] != "available":
        raise HTTPException(409, state["reason"])
    evidence = current_evidence(db, task_id)
    max_version = db.scalar(
        select(func.coalesce(func.max(ReportVersion.version_no), 0)).where(ReportVersion.task_id == task_id)
    )
    report = ReportVersion(
        task_id=task_id,
        version_no=int(max_version) + 1,
        snapshot_hash=state["snapshot_hash"],
        ai_content="",
        content="",
        generation_status="generating",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    latest_strategy = db.scalar(
        select(StrategyVersion)
        .where(StrategyVersion.task_id == task_id, StrategyVersion.generation_status == "completed")
        .order_by(StrategyVersion.version_no.desc())
        .limit(1)
    )
    strategy_text = latest_strategy.content if latest_strategy else "尚未生成应对策略"
    summary = f"已研判数据共{len(evidence)}条。\n" + evidence_as_text(evidence)
    try:
        content = await generate_report(task.name, summary, strategy_text)
    except OllamaError as exc:
        report.generation_status = "failed"
        report.generation_error = str(exc)
        db.commit()
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        report.generation_status = "failed"
        report.generation_error = str(exc)
        db.commit()
        raise HTTPException(500, "任务报告生成失败") from exc
    report.ai_content = content
    report.content = content
    report.generation_status = "completed"
    report.generation_error = None
    db.commit()
    db.refresh(report)
    return report


@router.put("/{report_id}", response_model=ReportRead)
def update_report(task_id: int, report_id: int, payload: ContentUpdate, db: Session = Depends(get_db)):
    report = db.get(ReportVersion, report_id)
    if not report or report.task_id != task_id:
        raise HTTPException(404, "报告不存在")
    if report.generation_status != "completed":
        raise HTTPException(409, "任务报告尚未生成完成，不能编辑")
    report.content = payload.content
    report.is_manually_edited = report.content != report.ai_content
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}/pdf")
def download_report(task_id: int, report_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    report = db.get(ReportVersion, report_id)
    if not task or not report or report.task_id != task_id:
        raise HTTPException(404, "报告不存在")
    if report.generation_status != "completed":
        raise HTTPException(409, "任务报告尚未生成完成，不能导出")
    output = render_report_pdf(task, report)
    return FileResponse(output, media_type="application/pdf", filename=f"{task.name}-舆情报告-v{report.version_no}.pdf")
