import asyncio
import json
from typing import Any

import httpx

from app.core.config import settings


class OllamaError(RuntimeError):
    pass


async def _generate(prompt: str, *, structured: bool = False) -> str:
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    if structured:
        payload["format"] = "json"
    last_error: Exception | None = None
    # 本机 Ollama 不应经过系统 HTTP 代理；模型首次加载或短暂重启时的
    # 502/503/504通常是瞬时错误，先重试再暂停分析任务。
    async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds, trust_env=False) as client:
        for attempt in range(5):
            try:
                response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {502, 503, 504} or attempt == 4:
                    detail = exc.response.text.strip()[:300]
                    suffix = f"：{detail}" if detail else ""
                    raise OllamaError(f"Ollama 返回 {exc.response.status_code}{suffix}") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 4:
                    raise OllamaError(f"无法连接本地 Ollama：{exc}") from exc
            await asyncio.sleep(min(2 ** attempt, 8))
        else:
            raise OllamaError(f"无法连接本地 Ollama：{last_error}")
    text = response.json().get("response", "").strip()
    if not text:
        raise OllamaError("Ollama 返回了空内容")
    return text


async def analyze_item(title: str, content: str, platform: str) -> dict[str, Any]:
    prompt = f"""
你是一名严谨的中文舆情分析员。分析下面一条社交平台信息。
风险等级需要综合内容敏感度、传播影响、紧迫性和可信度；负面不等于高风险。
只返回 JSON，不要返回 Markdown。字段必须为：
sentiment: positive、neutral、negative 三选一；
risk_level: low、medium、high 三选一；
confidence: 0到1之间的小数；
reason: 简洁的中文判断依据；
topics: 1到5个中文主题标签数组。

平台：{platform}
标题：{title}
正文：{content[:6000]}
""".strip()
    try:
        data = json.loads(await _generate(prompt, structured=True))
    except (json.JSONDecodeError, TypeError) as exc:
        raise OllamaError("Ollama 未返回合法 JSON") from exc
    if data.get("sentiment") not in {"positive", "neutral", "negative"}:
        raise OllamaError("Ollama 返回了无效情感值")
    if data.get("risk_level") not in {"low", "medium", "high"}:
        raise OllamaError("Ollama 返回了无效风险等级")
    data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    data["reason"] = str(data.get("reason", ""))
    data["topics"] = [str(value) for value in data.get("topics", [])][:5]
    return data


async def generate_strategy(task_name: str, evidence_text: str) -> str:
    prompt = f"""
你是一名资深舆情处置专家。请基于已经完成研判的数据，为“{task_name}”生成可执行的应对策略。
必须包含：态势判断、风险重点、立即行动（24小时内）、短期行动（3天内）、沟通口径、持续监测指标。
不得编造材料中不存在的事实。使用清晰的中文分级标题和条目。

研判材料：
{evidence_text[:14000]}
""".strip()
    return await _generate(prompt)


async def generate_report(task_name: str, summary: str, strategy: str) -> str:
    prompt = f"""
你是一名舆情报告撰写专家。请生成“{task_name}”任务的正式归档报告。
必须包含：一、任务概况；二、数据概览；三、舆情态势；四、主要风险；五、典型信息；
六、处置建议；七、总结。不得编造未提供的数据，语言正式、简洁。

统计与材料：
{summary[:12000]}

现有应对策略：
{strategy[:6000]}
""".strip()
    return await _generate(prompt)
