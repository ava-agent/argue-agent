from __future__ import annotations

import json
import logging

import httpx
from openai import AsyncOpenAI

from argue_agent.analysis.models import ArgumentExtraction, Utterance
from argue_agent.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """你是一个辩论分析专家。你的任务是从对方的发言中提取可以验证的事实性论点。

重点关注：
1. 事实断言（具体的数据、日期、事件、人物等可以查证的陈述）
2. 统计数据（"90%的人..."、"增长了3倍"等数字型声明）
3. 因果关系（"A导致了B"、"因为X所以Y"等因果型声明）
4. 引用他人观点（"某某专家说..."、"研究表明..."等引用型声明）

忽略：
- 纯粹的主观意见（"我觉得这样更好"）
- 反问句
- 常识性内容（不需要验证的）

对每个论点，生成1-3个适合搜索引擎验证的中文查询词。

以JSON格式返回，结构如下：
{
  "claims": [
    {
      "original_text": "原始发言中的相关片段",
      "normalized_claim": "规范化表述的论点",
      "claim_type": "factual/statistical/causal/quote",
      "search_queries": ["搜索查询1", "搜索查询2"],
      "confidence": 0.8
    }
  ],
  "main_argument": "对方的主要论点一句话概括"
}

如果发言中没有可验证的论点，返回空的claims列表。"""


class ArgumentExtractor:
    def __init__(self) -> None:
        # 创建不使用代理的 httpx 客户端
        http_client = httpx.AsyncClient(proxy=None)
        self.client = AsyncOpenAI(
            api_key=settings.glm_api_key,
            base_url=settings.glm_base_url,
            http_client=http_client,
        )
        self.context_window: list[Utterance] = []
        self.max_context = settings.extraction_context_window

    async def extract(self, utterance: Utterance) -> ArgumentExtraction:
        self.context_window.append(utterance)
        if len(self.context_window) > self.max_context:
            self.context_window.pop(0)

        context_text = "\n".join(
            f"[{u.speaker}]: {u.text}" for u in self.context_window
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.glm_model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"对话上下文：\n{context_text}\n\n"
                            f"请分析最新的发言：\n[{utterance.speaker}]: {utterance.text}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            return ArgumentExtraction.model_validate(data)

        except Exception:
            logger.exception("论点提取失败")
            return ArgumentExtraction()
