from __future__ import annotations

import asyncio
import logging

from duckduckgo_search import DDGS

from argue_agent.analysis.models import Claim, Evidence
from argue_agent.config import settings

logger = logging.getLogger(__name__)


class DDGSearcher:
    def __init__(self) -> None:
        self.max_results = settings.search_max_results_per_query

    async def search(self, claim: Claim) -> list[Evidence]:
        queries = claim.search_queries[: settings.search_max_queries_per_claim]
        tasks = [self._search_one(q) for q in queries]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_evidence: list[Evidence] = []
        seen_urls: set[str] = set()

        for results in results_lists:
            if isinstance(results, Exception):
                logger.warning("搜索失败: %s", results)
                continue
            for ev in results:
                if ev.source_url not in seen_urls:
                    seen_urls.add(ev.source_url)
                    all_evidence.append(ev)

        return all_evidence

    async def _search_one(self, query: str) -> list[Evidence]:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, self._sync_search, query)
        return results

    def _sync_search(self, query: str) -> list[Evidence]:
        evidence: list[Evidence] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="cn-zh", max_results=self.max_results):
                    evidence.append(
                        Evidence(
                            source_title=r.get("title", ""),
                            source_url=r.get("href", ""),
                            relevant_excerpt=r.get("body", ""),
                            supports_claim=True,  # 由 synthesizer 判定
                        )
                    )
        except Exception:
            logger.exception("DuckDuckGo 搜索出错: %s", query)
        return evidence
