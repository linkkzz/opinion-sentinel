from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import StrategyVersion, Task
from app.schemas import ContentUpdate, StrategyRead
from app.services.ollama import OllamaError, generate_strategy
from app.services.snapshots import current_evidence, evidence_as_text, evidence_hash

router = APIRouter(prefix="/tasks/{task_id}/strategies", tags=["应对策略"])


def _strategy_state(db: Session, task_id: int) -> dict:
    evidence = current_evidence(db, task_id)
    if not evidence:
        return {"state": "unavailable", "eligible": False, "reason": "至少需要一条已研判数据", "analyzed_count": 0}
    snapshot = evidence_hash(evidence)
    running = db.scalar(
        select(StrategyVersion)
        .where(StrategyVersion.task_id == task_id, StrategyVersion.generation_status == "generating")
        .order_by(StrategyVersion.version_no.desc())
        .limit(1)
    )
    if running:
        return {
            "state": "generating",
            "eligible": False,
            "reason": "应对策略正在生成中",
            # 生成期间继续进入的新研判数据属于下一版策略，当前两端应展示
            # 这条生成记录创建时已经锁定的研判数量。
            "analyzed_count": running.analyzed_count,
            "strategy_id": running.id,
            "snapshot_hash": running.snapshot_hash,
        }
    latest = db.scalar(
        select(StrategyVersion)
        .where(StrategyVersion.task_id == task_id, StrategyVersion.generation_status == "completed")
        .order_by(StrategyVersion.version_no.desc())
        .limit(1)
    )
    if latest and latest.snapshot_hash == snapshot:
        return {"state": "ready", "eligible": False, "reason": "暂无新增或变更的研判结果", "analyzed_count": len(evidence), "strategy_id": latest.id, "snapshot_hash": snapshot}
    return {"state": "available", "eligible": True, "reason": "存在新的研判结果", "analyzed_count": len(evidence), "snapshot_hash": snapshot}


@router.get("", response_model=list[StrategyRead])
def list_strategies(task_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(StrategyVersion).where(StrategyVersion.task_id == task_id).order_by(StrategyVersion.version_no.desc())
    ).all()


@router.get("/eligibility")
def strategy_eligibility(task_id: int, db: Session = Depends(get_db)):
    return _strategy_state(db, task_id)


@router.get("/status")
def strategy_status(task_id: int, db: Session = Depends(get_db)):
    if not db.get(Task, task_id):
        raise HTTPException(404, "任务不存在")
    return _strategy_state(db, task_id)


@router.post("", response_model=StrategyRead)
async def create_strategy(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    state = _strategy_state(db, task_id)
    if state["state"] == "generating":
        raise HTTPException(409, "应对策略正在生成中，请勿重复提交")
    if state["state"] == "ready":
        raise HTTPException(409, "暂无新增或变更的研判结果")
    if state["state"] != "available":
        raise HTTPException(409, state["reason"])
    evidence = current_evidence(db, task_id)
    snapshot = state["snapshot_hash"]
    max_version = db.scalar(
        select(func.coalesce(func.max(StrategyVersion.version_no), 0)).where(StrategyVersion.task_id == task_id)
    )
    strategy = StrategyVersion(
        task_id=task_id,
        version_no=int(max_version) + 1,
        snapshot_hash=snapshot,
        evidence=[{"item_id": x["item_id"], "analysis_id": x["analysis_id"]} for x in evidence],
        analyzed_count=len(evidence),
        ai_content="",
        content="",
        generation_status="generating",
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    try:
        content = await generate_strategy(task.name, evidence_as_text(evidence))
    except OllamaError as exc:
        strategy.generation_status = "failed"
        strategy.generation_error = str(exc)
        db.commit()
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        strategy.generation_status = "failed"
        strategy.generation_error = str(exc)
        db.commit()
        raise HTTPException(500, "应对策略生成失败") from exc
    strategy.ai_content = content
    strategy.content = content
    strategy.generation_status = "completed"
    strategy.generation_error = None
    db.commit()
    db.refresh(strategy)
    return strategy


@router.put("/{strategy_id}", response_model=StrategyRead)
def update_strategy(task_id: int, strategy_id: int, payload: ContentUpdate, db: Session = Depends(get_db)):
    strategy = db.get(StrategyVersion, strategy_id)
    if not strategy or strategy.task_id != task_id:
        raise HTTPException(404, "策略不存在")
    if strategy.generation_status != "completed":
        raise HTTPException(409, "应对策略尚未生成完成，不能编辑")
    strategy.content = payload.content
    strategy.is_manually_edited = strategy.content != strategy.ai_content
    db.commit()
    db.refresh(strategy)
    return strategy
