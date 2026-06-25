import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import AnalysisRevision, SourceItem, StrategyVersion, Task  # noqa: E402
from app.services.snapshots import current_evidence, evidence_hash  # noqa: E402


SAMPLES = [
    ("微博", "校园食堂卫生问题引发关注", "有同学发布食堂后厨卫生照片，希望学校尽快核查并公开处理结果。", "negative", "high", "食品卫生话题传播较快，需要及时核实回应。"),
    ("小红书", "学校连夜开展食堂专项检查", "校方发布情况说明，已成立专项工作组并邀请学生代表共同监督。", "positive", "low", "积极回应有助于缓解质疑。"),
    ("微信公众号", "关于校园餐饮服务的情况通报", "学校公布检查结果、整改措施及后续监督渠道。", "neutral", "low", "权威信息发布，当前风险可控。"),
    ("抖音", "探访整改后的校园食堂", "视频展示食堂整改后的消毒流程和食品留样制度。", "positive", "low", "正向现场内容获得较多认可。"),
    ("微博", "网友质疑通报避重就轻", "部分网友认为通报缺少责任人员处理细节，讨论仍在持续。", "negative", "medium", "质疑集中在信息透明度，存在舆情反复可能。"),
    ("快手", "家长谈校园食品安全", "家长希望建立长期公开机制，而不仅是一次性整改。", "neutral", "medium", "诉求较为理性，但需要持续回应。"),
    ("小红书", "学生代表参加食堂监督会议", "学生代表分享监督会议内容，表示整改措施正在逐项落实。", "positive", "low", "第三方视角增强了整改信息可信度。"),
    ("微博", "旧照片被误传为本次事件", "经核实网传照片拍摄于其他地区，但仍有账号继续转发。", "negative", "high", "不实信息持续传播，需快速澄清并提供证据。"),
    ("微信公众号", "食品安全知识科普", "学校推出食品安全公开课，介绍采购、留样和追溯流程。", "positive", "low", "科普内容有助于建立长期信任。"),
    ("抖音", "食堂整改直播回放", "直播回应了学生关心的价格、卫生和反馈机制等问题。", "neutral", "medium", "互动回应充分，但部分问题仍需后续落实。"),
    ("微博", "话题热度开始下降", "相关讨论量较昨日下降，多数关注转向整改效果。", "neutral", "low", "传播热度下降，进入持续观察阶段。"),
    ("小红书", "校园食堂一周体验记录", "学生记录整改后一周就餐体验，整体评价有所改善。", "positive", "low", "用户体验反馈转好，风险趋于平稳。"),
]


def main():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Task).count():
            print("数据库中已有任务，未重复写入演示数据。")
            return
        task = Task(
            name="校园食品安全舆情监测",
            keywords=["校园食堂", "食品安全", "餐饮整改"],
            platforms=["微博", "小红书", "快手", "抖音", "微信公众号"],
            description="持续监测校园食品安全事件传播态势与公众反馈。",
            analysis_state="waiting",
            analysis_enabled=True,
        )
        db.add(task)
        db.flush()
        base_time = datetime.now() - timedelta(days=6)
        for index, (platform, title, content, sentiment, risk, reason) in enumerate(SAMPLES, 1):
            item = SourceItem(
                task_id=task.id, platform=platform, external_id=f"demo-{index:03d}", title=title,
                author=f"示例账号{index:02d}", publish_time=base_time + timedelta(hours=index * 11), content=content,
                source_url=f"https://example.com/opinion/{index}",
                like_count=(likes := random.randint(50, 2200)),
                comment_count=(comments := random.randint(10, 600)),
                share_count=(shares := random.randint(5, 400)),
                view_count=random.randint(2000, 80000),
                interaction_count=likes + comments + shares,
                dedupe_key=f"demo-{index:059d}", analysis_status="analyzed",
            )
            db.add(item)
            db.flush()
            revision = AnalysisRevision(
                item_id=item.id, revision_no=1, sentiment=sentiment, risk_level=risk,
                confidence=round(random.uniform(.78, .96), 2), reason=reason,
                topics=["校园食品安全", "整改回应"], source="ai", model_name="demo",
            )
            db.add(revision)
            db.flush()
            item.current_analysis_id = revision.id
        db.commit()
        evidence = current_evidence(db, task.id)
        strategy = StrategyVersion(
            task_id=task.id, version_no=1, snapshot_hash=evidence_hash(evidence),
            evidence=[{"item_id": x["item_id"], "analysis_id": x["analysis_id"]} for x in evidence],
            analyzed_count=len(evidence), ai_content="""一、态势判断
事件已由单点卫生质疑转向对整改透明度和长期监督机制的讨论，整体热度开始下降，但旧图误传仍是当前主要风险。

二、立即行动（24小时内）
1. 发布旧图溯源证据与权威澄清，统一各平台回应口径。
2. 补充责任落实、整改进度及学生监督机制细节。
3. 对高风险传播账号和核心质疑点实施小时级监测。

三、短期行动（3天内）
组织学生代表、家长代表开展开放日，通过现场直播展示采购、留样与消毒流程；每日发布整改清单进度。

四、持续监测指标
重点监测负面占比、高风险信息增量、旧图传播量及权威回应后的评论情绪变化。""",
            content="""一、态势判断
事件已由单点卫生质疑转向对整改透明度和长期监督机制的讨论，整体热度开始下降，但旧图误传仍是当前主要风险。

二、立即行动（24小时内）
1. 发布旧图溯源证据与权威澄清，统一各平台回应口径。
2. 补充责任落实、整改进度及学生监督机制细节。
3. 对高风险传播账号和核心质疑点实施小时级监测。

三、短期行动（3天内）
组织学生代表、家长代表开展开放日，通过现场直播展示采购、留样与消毒流程；每日发布整改清单进度。

四、持续监测指标
重点监测负面占比、高风险信息增量、旧图传播量及权威回应后的评论情绪变化。""",
        )
        db.add(strategy)
        db.commit()
        print(f"已创建演示任务 #{task.id}，包含 {len(SAMPLES)} 条舆情数据。")


if __name__ == "__main__":
    main()
