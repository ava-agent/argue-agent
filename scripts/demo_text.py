#!/usr/bin/env python3
"""文本模式演示 - 跳过音频，直接输入文本测试完整管道。

用法: python scripts/demo_text.py
"""

import asyncio
import sys
from pathlib import Path

# 确保能找到 src 包
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from argue_agent.analysis.extractor import ArgumentExtractor
from argue_agent.analysis.models import Utterance, VerdictLevel
from argue_agent.search.ddg_search import DDGSearcher
from argue_agent.verdict.synthesizer import VerdictSynthesizer

VERDICT_COLORS = {
    VerdictLevel.VERIFIED: "\033[92m",      # 绿色
    VerdictLevel.MOSTLY_TRUE: "\033[92m",
    VerdictLevel.QUESTIONABLE: "\033[93m",   # 黄色
    VerdictLevel.MOSTLY_FALSE: "\033[91m",   # 红色
    VerdictLevel.FALSE: "\033[91m",
    VerdictLevel.UNVERIFIABLE: "\033[90m",   # 灰色
}
RESET = "\033[0m"


async def process_text(
    text: str,
    extractor: ArgumentExtractor,
    searcher: DDGSearcher,
    synthesizer: VerdictSynthesizer,
) -> None:
    utterance = Utterance(text=text, speaker="opponent")

    print("\n⏳ 正在分析论点...")
    extraction = await extractor.extract(utterance)

    if not extraction.claims:
        print("ℹ️  未检测到可验证的论点")
        return

    print(f"📌 主要论点: {extraction.main_argument}")
    print(f"🔍 检测到 {len(extraction.claims)} 个可验证论点:\n")

    for i, claim in enumerate(extraction.claims, 1):
        print(f"  [{i}] {claim.normalized_claim}")
        print(f"      类型: {claim.claim_type.value} | 置信度: {claim.confidence:.0%}")
        print(f"      搜索词: {', '.join(claim.search_queries)}")

        print("      ⏳ 搜索验证中...")
        evidence = await searcher.search(claim)

        verdict = await synthesizer.synthesize(claim, evidence)

        color = VERDICT_COLORS.get(verdict.verdict, "")
        print(f"      {color}判定: {verdict.verdict.value} ({verdict.confidence:.0%}){RESET}")
        print(f"      📋 {verdict.summary}")
        if verdict.suggested_rebuttal:
            print(f"      💬 反驳建议: {verdict.suggested_rebuttal}")

        if verdict.evidence:
            print(f"      📎 参考来源 ({len(verdict.evidence)} 条):")
            for ev in verdict.evidence[:3]:
                support = "✅" if ev.supports_claim else "❌"
                print(f"         {support} {ev.source_title}")

        print()


async def main() -> None:
    print("=" * 60)
    print("  Argue Agent - 实时辩论助手 (文本模式)")
    print("=" * 60)
    print("输入对方的发言，系统会自动提取论点并搜索验证。")
    print("输入 'quit' 或 'q' 退出。\n")

    extractor = ArgumentExtractor()
    searcher = DDGSearcher()
    synthesizer = VerdictSynthesizer()

    while True:
        try:
            text = input("🎤 对方说: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not text or text.lower() in ("quit", "q", "exit"):
            break

        await process_text(text, extractor, searcher, synthesizer)

    print("\n👋 再见！")


if __name__ == "__main__":
    asyncio.run(main())
