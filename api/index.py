"""Argue Agent - Vercel Serverless API

POST /api/analyze  { "text": "对方的发言" }
→ { "input_text", "main_argument", "claims": [...] }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from http.server import BaseHTTPRequestHandler

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────

GLM_API_KEY = os.environ.get("ARGUE_GLM_API_KEY", "")
GLM_BASE_URL = os.environ.get(
    "ARGUE_GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
)
GLM_MODEL = os.environ.get("ARGUE_GLM_MODEL", "glm-4-flash")
TAVILY_API_KEY = os.environ.get("ARGUE_TAVILY_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# ── Prompts ─────────────────────────────────────────────

EXTRACTION_PROMPT = """你是一个辩论分析专家。你的任务是从对方的发言中提取可以验证的事实性论点。

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

VERDICT_PROMPT = """你是一个事实核查专家。根据搜索结果对论点进行判定。

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


# ── LLM helpers ─────────────────────────────────────────


def _make_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=GLM_API_KEY,
        base_url=GLM_BASE_URL,
        http_client=httpx.AsyncClient(proxy=None),
    )


async def extract_claims(text: str) -> dict:
    client = _make_client()
    try:
        resp = await client.chat.completions.create(
            model=GLM_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"请分析以下发言：\n{text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        logger.exception("extract_claims failed")
        return {"claims": [], "main_argument": ""}


async def _tavily_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Search using Tavily API (designed for AI agents)."""
    try:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
                "include_answer": False,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "source_title": r.get("title", ""),
                "source_url": r.get("url", ""),
                "relevant_excerpt": r.get("content", "")[:500],
                "supports_claim": True,
            }
            for r in data.get("results", [])
        ]
    except Exception:
        logger.exception("tavily search failed: %s", query)
        return []


async def search_evidence(queries: list[str]) -> list[dict]:
    if not TAVILY_API_KEY:
        logger.warning("ARGUE_TAVILY_API_KEY not set, skipping search")
        return []
    async with httpx.AsyncClient() as client:
        tasks = [_tavily_search(client, q) for q in queries[:2]]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
    all_ev: list[dict] = []
    seen: set[str] = set()
    for results in results_lists:
        if isinstance(results, Exception):
            continue
        for ev in results:
            if ev["source_url"] not in seen:
                seen.add(ev["source_url"])
                all_ev.append(ev)
    return all_ev


async def synthesize_verdict(claim: dict, evidence: list[dict]) -> dict:
    if not evidence:
        return {
            "verdict": "unverifiable", "confidence": 0.0,
            "summary": "未找到相关搜索结果，无法验证",
            "suggested_rebuttal": "无法找到相关资料来验证这个说法，建议要求对方提供信息来源。",
            "evidence": [],
        }
    client = _make_client()
    ev_text = "\n".join(
        f"[来源{i+1}] {e['source_title']}\n链接: {e['source_url']}\n内容: {e['relevant_excerpt']}"
        for i, e in enumerate(evidence)
    )
    try:
        resp = await client.chat.completions.create(
            model=GLM_MODEL,
            messages=[
                {"role": "system", "content": VERDICT_PROMPT},
                {"role": "user", "content": f"待验证论点: {claim['normalized_claim']}\n原始发言: {claim.get('original_text','')}\n\n搜索结果:\n{ev_text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        analyzed = list(evidence)
        for ea in data.get("evidence_analysis", []):
            idx = ea.get("source_index", -1)
            if 0 <= idx < len(analyzed):
                analyzed[idx] = {**analyzed[idx], "supports_claim": ea.get("supports_claim", True)}
        return {
            "verdict": data.get("verdict", "unverifiable"),
            "confidence": data.get("confidence", 0.5),
            "summary": data.get("summary", ""),
            "suggested_rebuttal": data.get("suggested_rebuttal", ""),
            "evidence": analyzed[:5],
        }
    except Exception:
        logger.exception("synthesize_verdict failed")
        return {"verdict": "unverifiable", "confidence": 0.0, "summary": "判定过程出错", "suggested_rebuttal": "", "evidence": []}


async def save_to_supabase(input_text: str, main_argument: str, claims: list[dict]) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/argue_analyses",
                json={"input_text": input_text, "main_argument": main_argument, "claims": claims},
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                timeout=5.0,
            )
    except Exception:
        logger.exception("supabase save failed")


async def process_claim(claim: dict) -> dict:
    evidence = await search_evidence(claim.get("search_queries", []))
    verdict = await synthesize_verdict(claim, evidence)
    return {
        "original_text": claim.get("original_text", ""),
        "normalized_claim": claim.get("normalized_claim", ""),
        "claim_type": claim.get("claim_type", "factual"),
        "claim_confidence": claim.get("confidence", 0.5),
        **verdict,
    }


async def run_extract(text: str) -> dict:
    """Step 1: Extract claims only (fast ~1-2s)."""
    if not GLM_API_KEY:
        return {"error": "GLM API Key 未配置"}
    extraction = await extract_claims(text)
    claims = extraction.get("claims", [])
    claims = [c for c in claims if c.get("confidence", 0) >= 0.5][:3]
    return {"input_text": text, "main_argument": extraction.get("main_argument", ""), "claims": claims}


async def run_verdict(claim_data: dict) -> dict:
    """Step 2: Search + synthesize verdict for one claim (~2-4s)."""
    if not GLM_API_KEY:
        return {"error": "GLM API Key 未配置"}
    return await process_claim(claim_data)


async def run_pipeline(text: str) -> dict:
    """Full pipeline (backward compatible)."""
    if not GLM_API_KEY:
        return {"error": "GLM API Key 未配置"}

    extraction = await extract_claims(text)
    claims = extraction.get("claims", [])

    if not claims:
        await save_to_supabase(text, extraction.get("main_argument", ""), [])
        return {"input_text": text, "main_argument": extraction.get("main_argument", ""), "claims": []}

    claims = [c for c in claims if c.get("confidence", 0) >= 0.5][:3]
    processed = list(await asyncio.gather(*[process_claim(c) for c in claims]))
    main_arg = extraction.get("main_argument", "")
    await save_to_supabase(text, main_arg, processed)
    return {"input_text": text, "main_argument": main_arg, "claims": processed}


# ── Vercel Handler ──────────────────────────────────────


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._json(400, {"error": "Invalid JSON"})
            return

        step = body.get("step", "full")

        if step == "verdict":
            claim_data = body.get("claim")
            if not claim_data:
                self._json(400, {"error": "缺少 claim 数据"})
                return
            try:
                result = asyncio.run(run_verdict(claim_data))
            except Exception as e:
                logger.exception("verdict error")
                self._json(500, {"error": str(e)})
                return
            self._json(200, result)
            return

        text = body.get("text", "").strip()
        if not text:
            self._json(400, {"error": "请输入文本"})
            return

        try:
            if step == "extract":
                result = asyncio.run(run_extract(text))
            else:
                result = asyncio.run(run_pipeline(text))
        except Exception as e:
            logger.exception("pipeline error")
            self._json(500, {"error": str(e)})
            return

        if "error" in result and len(result) == 1:
            self._json(500, result)
        else:
            self._json(200, result)

    def do_GET(self):
        self._json(200, {"status": "ok", "service": "argue-agent"})

    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
