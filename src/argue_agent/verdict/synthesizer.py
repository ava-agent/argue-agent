from __future__ import annotations

import json
import logging

import httpx
from openai import AsyncOpenAI

from argue_agent.analysis.models import Claim, Evidence, FactVerdict, VerdictLevel
from argue_agent.config import settings

logger = logging.getLogger(__name__)

VERDICT_SYSTEM_PROMPT = """你是一个事实核查专家。根据搜索结果对论点进行判定。

判定等级：
- verified: 搜索结果充分支持该论点
- mostly_true: 基本正确，但有细节偏差
- questionable: 证据不足或存在矛盾
- mostly_false: 大部分内容不准确
- false: 明确错误
- unverifiable: 无法通过现有搜索结果验证

以JSON格式返回：
{
  "verdict": "判定等级",
  "confidence": 0.8,
  "summary": "一句话总结判定结果",
  "suggested_rebuttal": "如果论点有问题，给出反驳建议；如果论点正确，给出确认说明",
  "evidence_analysis": [
    {
      "source_index": 0,
      "supports_claim": true,
      "reason": "为什么支持/反驳"
    }
  ]
}"""


class VerdictSynthesizer:
    def __init__(self) -> None:
        # 创建不使用代理的 httpx 客户端
        http_client = httpx.AsyncClient(proxy=None)
        self.client = AsyncOpenAI(
            api_key=settings.glm_api_key,
            base_url=settings.glm_base_url,
            http_client=http_client,
        )

    async def synthesize(
        self, claim: Claim, evidence: list[Evidence]
    ) -> FactVerdict:
        if not evidence:
            return FactVerdict(
                claim=claim,
                verdict=VerdictLevel.UNVERIFIABLE,
                confidence=0.0,
                summary="未找到相关搜索结果，无法验证",
                suggested_rebuttal="无法找到相关资料来验证这个说法，建议要求对方提供信息来源。",
            )

        evidence_text = "\n".join(
            f"[来源{i + 1}] {e.source_title}\n链接: {e.source_url}\n内容: {e.relevant_excerpt}"
            for i, e in enumerate(evidence)
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.glm_model,
                messages=[
                    {"role": "system", "content": VERDICT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"待验证论点: {claim.normalized_claim}\n"
                            f"原始发言: {claim.original_text}\n\n"
                            f"搜索结果:\n{evidence_text}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            # 根据 LLM 分析结果更新 evidence 的 supports_claim
            analyzed_evidence = list(evidence)
            for ea in data.get("evidence_analysis", []):
                idx = ea.get("source_index", -1)
                if 0 <= idx < len(analyzed_evidence):
                    analyzed_evidence[idx] = analyzed_evidence[idx].model_copy(
                        update={"supports_claim": ea.get("supports_claim", True)}
                    )

            verdict_str = data.get("verdict", "unverifiable")
            try:
                verdict = VerdictLevel(verdict_str)
            except ValueError:
                verdict = VerdictLevel.UNVERIFIABLE

            return FactVerdict(
                claim=claim,
                verdict=verdict,
                confidence=data.get("confidence", 0.5),
                evidence=analyzed_evidence,
                summary=data.get("summary", ""),
                suggested_rebuttal=data.get("suggested_rebuttal", ""),
            )

        except Exception:
            logger.exception("判定合成失败")
            return FactVerdict(
                claim=claim,
                verdict=VerdictLevel.UNVERIFIABLE,
                confidence=0.0,
                summary="判定过程出错",
                suggested_rebuttal="",
            )
