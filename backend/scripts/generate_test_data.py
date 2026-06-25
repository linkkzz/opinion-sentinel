"""Add non-destructive competition demo tasks covering several workflow states."""

import hashlib
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import AnalysisRevision, ReportVersion, SourceItem, StrategyVersion, Task  # noqa: E402
from app.services.snapshots import current_evidence, evidence_hash  # noqa: E402

random.seed(20260620)
PLATFORMS = ["微博", "小红书", "抖音", "微信公众号", "快手"]

TASK_CASES = [
    {
        "name": "新能源汽车质量争议监测",
        "keywords": ["新能源汽车", "质量争议", "售后服务", "召回"],
        "topics": ["产品质量", "售后服务", "品牌回应", "用户权益", "召回进展"],
        "count": 30, "analyzed": 20, "status": "running", "strategy": True, "report": False,
    },
    {
        "name": "高校招聘公平性讨论",
        "keywords": ["校园招聘", "就业公平", "招聘流程"],
        "topics": ["校园招聘", "就业公平", "信息公开", "学生诉求", "企业回应"],
        "count": 24, "analyzed": 11, "status": "running", "strategy": False, "report": False,
    },
    {
        "name": "城市音乐节服务舆情",
        "keywords": ["城市音乐节", "票务", "现场服务", "交通保障"],
        "topics": ["票务服务", "现场秩序", "交通保障", "游客体验", "主办方回应"],
        "count": 28, "analyzed": 28, "status": "completed", "strategy": True, "report": True,
    },
    {
        "name": "国产游戏上线口碑监测",
        "keywords": ["国产游戏", "服务器", "玩家口碑", "版本更新"],
        "topics": ["玩家口碑", "服务器稳定", "内容质量", "版本更新", "客服响应"],
        "count": 26, "analyzed": 26, "status": "completed", "strategy": True, "report": True,
        "manual": True,
    },
]

TITLE_PATTERNS = [
    "网友集中讨论{topic}问题", "官方发布{topic}最新说明", "体验用户反馈{topic}有所改善",
    "自媒体梳理{topic}事件时间线", "相关话题热度持续上升", "专家建议完善{topic}机制",
    "评论区关注后续处理结果", "当事方回应网络质疑", "多平台出现相似讨论", "最新处置进展获得关注",
]
CONTENT_PATTERNS = [
    "相关信息发布后引发网友讨论，部分用户希望尽快公开调查过程和后续处理结果。",
    "官方账号发布情况说明，表示已经成立工作组，并将持续公布处置进展。",
    "多名体验用户分享实际情况，正面评价与质疑声音同时存在，话题仍在传播。",
    "有账号转发未经核实的信息，评论区出现误读，需要及时澄清并提供权威依据。",
    "当前讨论逐渐从事件本身转向长期机制建设，公众更关注信息透明度和执行效果。",
]


def add_case(db, case: dict) -> bool:
    if db.query(Task).filter(Task.name == case["name"]).first():
        return False
    task = Task(
        name=case["name"], keywords=case["keywords"], platforms=PLATFORMS,
        description=f"围绕{case['name']}开展多平台持续监测与风险研判。",
        status=case["status"], analysis_enabled=False,
        analysis_state="stopped" if case["status"] == "completed" else "paused",
        start_time=datetime.now() - timedelta(days=12),
    )
    db.add(task)
    db.flush()
    start = datetime.now() - timedelta(days=9)
    for index in range(case["count"]):
        topic = case["topics"][index % len(case["topics"])]
        title = TITLE_PATTERNS[index % len(TITLE_PATTERNS)].format(topic=topic)
        external_id = f"test-{task.id}-{index + 1:03d}"
        item = SourceItem(
            task_id=task.id, platform=PLATFORMS[index % len(PLATFORMS)], external_id=external_id,
            title=title, author=f"测试账号{index + 1:02d}",
            publish_time=start + timedelta(hours=index * 8 + random.randint(0, 4)),
            content=CONTENT_PATTERNS[index % len(CONTENT_PATTERNS)],
            source_url=f"https://example.com/test/{task.id}/{index + 1}",
            like_count=(likes := random.randint(20, 4200)),
            comment_count=(comments := random.randint(5, 1200)),
            share_count=(shares := random.randint(2, 900)),
            view_count=random.randint(1000, 150000),
            interaction_count=likes + comments + shares,
            dedupe_key=hashlib.sha256(external_id.encode()).hexdigest(),
            analysis_status="analyzed" if index < case["analyzed"] else "pending",
        )
        db.add(item)
        db.flush()
        if index < case["analyzed"]:
            sentiment = ["negative", "neutral", "positive", "neutral", "positive"][index % 5]
            risk = ["high", "medium", "low", "medium", "low", "low"][index % 6]
            revision = AnalysisRevision(
                item_id=item.id, revision_no=1, sentiment=sentiment, risk_level=risk,
                confidence=round(random.uniform(.76, .96), 2),
                reason=f"该信息涉及{topic}，综合传播量、内容敏感度和回应情况判定为{risk}风险。",
                topics=[topic, case["topics"][(index + 1) % len(case["topics"])]],
                source="ai", model_name="test-data-generator",
            )
            db.add(revision)
            db.flush()
            item.current_analysis_id = revision.id
    db.commit()
    evidence = current_evidence(db, task.id)
    snapshot = evidence_hash(evidence)
    if case["strategy"]:
        strategy_text = f"""一、态势判断
当前“{case['name']}”已形成跨平台讨论，主要关注点集中在{case['topics'][0]}、{case['topics'][1]}和{case['topics'][2]}。

二、立即行动
1. 核实高风险信息并统一回应口径。
2. 针对核心质疑发布可验证的事实材料。
3. 建立重点账号和高传播内容清单，持续跟踪情绪变化。

三、短期处置
在三日内公布阶段性进展，邀请利益相关方参与沟通，并根据反馈完善长期机制。

四、监测指标
持续监测负面占比、高风险增量、平台声量和权威回应后的评论变化。"""
        db.add(StrategyVersion(
            task_id=task.id, version_no=1, snapshot_hash=snapshot,
            evidence=[{"item_id": x["item_id"], "analysis_id": x["analysis_id"]} for x in evidence],
            analyzed_count=len(evidence), ai_content=strategy_text, content=strategy_text,
            is_manually_edited=bool(case.get("manual")),
        ))
    if case["report"]:
        report_text = f"""一、任务概况
本任务围绕“{case['name']}”开展持续监测，共收录并完成研判{len(evidence)}条有效信息。

二、数据概览
信息覆盖微博、小红书、抖音、微信公众号和快手，讨论焦点主要集中在{case['topics'][0]}和{case['topics'][1]}。

三、舆情态势
事件经历关注上升、集中回应和趋于平稳三个阶段，权威信息发布后整体风险得到控制。

四、处置意见
建议继续保留常态化反馈渠道，定期公布改进成果，并对高风险信息保持跟踪监测。

五、总结
当前任务已完成阶段性处置，相关材料与研判结果归档留存。"""
        db.add(ReportVersion(
            task_id=task.id, version_no=1, snapshot_hash=snapshot,
            ai_content=report_text,
            content=report_text + ("\n\n人工审核意见：报告内容已复核，建议归档。" if case.get("manual") else ""),
            is_manually_edited=bool(case.get("manual")),
        ))
    db.commit()
    return True


def main():
    Base.metadata.create_all(bind=engine)
    created = 0
    with SessionLocal() as db:
        for case in TASK_CASES:
            created += int(add_case(db, case))
    print(f"测试数据准备完成：新增 {created} 个任务。重复运行不会重复创建。")


if __name__ == "__main__":
    main()
