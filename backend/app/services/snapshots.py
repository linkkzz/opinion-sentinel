import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRevision, SourceItem


def current_evidence(db: Session, task_id: int) -> list[dict]:
    rows = db.execute(
        select(SourceItem, AnalysisRevision)
        .join(AnalysisRevision, SourceItem.current_analysis_id == AnalysisRevision.id)
        .where(SourceItem.task_id == task_id, SourceItem.analysis_status == "analyzed")
        .order_by(SourceItem.id)
    ).all()
    return [
        {
            "item_id": item.id,
            "analysis_id": analysis.id,
            "title": item.title,
            "platform": item.platform,
            "content": item.content[:1200],
            "sentiment": analysis.sentiment,
            "risk_level": analysis.risk_level,
            "reason": analysis.reason,
        }
        for item, analysis in rows
    ]


def evidence_hash(evidence: list[dict]) -> str:
    identity = [(row["item_id"], row["analysis_id"]) for row in evidence]
    payload = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_as_text(evidence: list[dict]) -> str:
    return "\n\n".join(
        f"[{row['item_id']}] {row['platform']}｜{row['title']}\n"
        f"情感：{row['sentiment']}；风险：{row['risk_level']}；依据：{row['reason']}\n"
        f"正文摘要：{row['content']}"
        for row in evidence
    )

