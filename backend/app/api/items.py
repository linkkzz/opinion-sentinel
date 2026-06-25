from pathlib import Path

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import AnalysisRevision, SourceItem, Task
from app.schemas import AnalysisRead, ManualAnalysisUpdate, MediaRead, SourceItemRead
from app.services.importer import import_excel

router = APIRouter(tags=["舆情数据"])


def _serialize_item(item: SourceItem, db: Session) -> SourceItemRead:
    current = db.get(AnalysisRevision, item.current_analysis_id) if item.current_analysis_id else None
    payload = SourceItemRead.model_validate(item).model_dump()
    payload["current_analysis"] = AnalysisRead.model_validate(current) if current else None
    payload["media"] = []
    for media in item.media:
        try:
            relative = Path(media.storage_path).resolve().relative_to(settings.storage_root.resolve()).as_posix()
        except ValueError:
            relative = Path(media.storage_path).name
        data = MediaRead.model_validate(media).model_dump()
        data["storage_path"] = f"/media/{relative}"
        payload["media"].append(data)
    return SourceItemRead(**payload)


@router.post("/tasks/{task_id}/import")
async def import_items(
    task_id: int,
    excel: UploadFile = File(...),
    media_zip: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if not excel.filename or not excel.filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "请上传 .xlsx 文件")
    try:
        result = await import_excel(db, task_id, excel, media_zip)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return result


@router.get("/tasks/{task_id}/items")
def list_items(
    task_id: int,
    page: int = 1,
    page_size: int = 20,
    analysis_status: str | None = None,
    db: Session = Depends(get_db),
):
    if not db.get(Task, task_id):
        raise HTTPException(404, "任务不存在")
    conditions = [SourceItem.task_id == task_id]
    if analysis_status:
        conditions.append(SourceItem.analysis_status == analysis_status)
    total = db.scalar(select(func.count(SourceItem.id)).where(*conditions)) or 0
    items = db.scalars(
        select(SourceItem)
        .where(*conditions)
        .options(selectinload(SourceItem.media))
        .order_by(SourceItem.publish_time.desc(), SourceItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(min(page_size, 100))
    ).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_serialize_item(x, db) for x in items]}


@router.get("/import-template")
def download_import_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "舆情数据"
    sheet.append(["平台", "标题", "发布人", "发布时间", "正文", "源链接", "点赞量", "评论量", "转发量", "阅读/播放量", "图片文件", "视频文件"])
    sheet.append([
        "微博", "示例舆情标题", "示例用户", "2026-06-20 10:30:00",
        "这里填写需要进行舆情研判的正文内容。", "https://example.com/post/1", 80, 28, 20, 2600,
        "image001.jpg,image002.jpg", "video001.mp4",
    ])
    platform_validation = DataValidation(type="list", formula1='"微博,小红书,快手,抖音,微信公众号"')
    sheet.add_data_validation(platform_validation)
    platform_validation.add("A2:A500")
    for column, width in zip("ABCDEFGHIJKL", [14, 28, 16, 22, 60, 38, 12, 12, 12, 16, 32, 24]):
        sheet.column_dimensions[column].width = width
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="opinion-import-template.xlsx"'}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@router.get("/items/{item_id}", response_model=SourceItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(SourceItem).where(SourceItem.id == item_id).options(selectinload(SourceItem.media)))
    if not item:
        raise HTTPException(404, "数据不存在")
    return _serialize_item(item, db)


@router.put("/items/{item_id}/analysis", response_model=AnalysisRead)
def revise_analysis(item_id: int, payload: ManualAnalysisUpdate, db: Session = Depends(get_db)):
    item = db.get(SourceItem, item_id)
    if not item:
        raise HTTPException(404, "数据不存在")
    latest_no = db.scalar(
        select(func.coalesce(func.max(AnalysisRevision.revision_no), 0)).where(AnalysisRevision.item_id == item_id)
    )
    revision = AnalysisRevision(
        item_id=item_id,
        revision_no=int(latest_no) + 1,
        sentiment=payload.sentiment,
        risk_level=payload.risk_level,
        reason=payload.reason,
        topics=payload.topics,
        source="human",
        change_note=payload.change_note,
    )
    db.add(revision)
    db.flush()
    item.current_analysis_id = revision.id
    item.analysis_status = "analyzed"
    item.analysis_error = None
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/items/{item_id}/analysis-history", response_model=list[AnalysisRead])
def analysis_history(item_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(AnalysisRevision).where(AnalysisRevision.item_id == item_id).order_by(AnalysisRevision.revision_no.desc())
    ).all()


@router.post("/tasks/{task_id}/analysis/start")
def start_analysis(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status != "running":
        raise HTTPException(409, "已完结任务不能启动分析")
    task.analysis_enabled = True
    task.analysis_state = "running"
    db.commit()
    return {"analysis_enabled": True, "analysis_state": task.analysis_state}


@router.post("/tasks/{task_id}/analysis/stop")
def stop_analysis(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    task.analysis_enabled = False
    task.analysis_state = "paused"
    db.commit()
    return {"analysis_enabled": False, "analysis_state": task.analysis_state}
