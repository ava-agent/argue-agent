from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from argue_agent.analysis.accumulator import SentenceAccumulator
from argue_agent.analysis.extractor import ArgumentExtractor
from argue_agent.analysis.models import TranscriptSegment, Utterance, FactVerdict
from argue_agent.audio.processor import float32_to_int16
from argue_agent.config import settings
from argue_agent.search.ddg_search import DDGSearcher
from argue_agent.stt.deepgram_stt import DeepgramSTT
from argue_agent.verdict.synthesizer import VerdictSynthesizer

logger = logging.getLogger(__name__)

app = FastAPI(title="Argue Agent - 实时辩论助手")

STATIC_DIR = Path(__file__).parent / "web" / "static"


@app.get("/")
async def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("客户端已连接")

    # 各阶段队列
    transcript_queue: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue(maxsize=100)
    utterance_queue: asyncio.Queue[Utterance] = asyncio.Queue(maxsize=20)

    # 组件
    stt = DeepgramSTT(transcript_queue)
    accumulator = SentenceAccumulator(transcript_queue, utterance_queue)
    extractor = ArgumentExtractor()
    searcher = DDGSearcher()
    synthesizer = VerdictSynthesizer()

    stt_connected = False

    async def send_json(msg_type: str, data: dict) -> None:
        try:
            await ws.send_json({"type": msg_type, **data})
        except Exception:
            pass

    async def process_utterances() -> None:
        """从 utterance 队列取出完整语句，执行 提取→搜索→判定 管道。"""
        while True:
            utterance = await utterance_queue.get()

            # 发送转录文本到前端
            await send_json("transcript", {
                "text": utterance.text,
                "speaker": utterance.speaker,
            })

            # 论点提取
            extraction = await extractor.extract(utterance)
            if not extraction.claims:
                continue

            await send_json("extraction", {
                "main_argument": extraction.main_argument,
                "claim_count": len(extraction.claims),
            })

            # 逐个论点搜索验证
            for claim in extraction.claims:
                if claim.confidence < settings.extraction_confidence_threshold:
                    continue

                await send_json("checking", {
                    "claim": claim.normalized_claim,
                })

                evidence = await searcher.search(claim)
                verdict = await synthesizer.synthesize(claim, evidence)

                await send_json("verdict", {
                    "claim": verdict.claim.normalized_claim,
                    "verdict": verdict.verdict.value,
                    "confidence": verdict.confidence,
                    "summary": verdict.summary,
                    "rebuttal": verdict.suggested_rebuttal,
                    "evidence_count": len(verdict.evidence),
                    "evidence": [
                        {
                            "title": e.source_title,
                            "url": e.source_url,
                            "supports": e.supports_claim,
                        }
                        for e in verdict.evidence[:5]
                    ],
                })

    # 启动后台任务
    accumulator_task = asyncio.create_task(accumulator.run())
    processor_task = asyncio.create_task(process_utterances())

    try:
        # 连接 Deepgram
        if settings.deepgram_api_key:
            try:
                await stt.connect()
                stt_connected = True
                await send_json("status", {"message": "语音识别已连接"})
            except Exception:
                logger.exception("Deepgram 连接失败")
                await send_json("status", {"message": "语音识别连接失败，仅文本模式可用"})
        else:
            await send_json("status", {"message": "未配置 Deepgram Key，仅文本模式可用"})

        # 接收客户端消息
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # 二进制音频数据
            if "bytes" in message and message["bytes"]:
                audio_data = message["bytes"]
                if stt_connected:
                    pcm_data = float32_to_int16(audio_data)
                    await stt.send_audio(pcm_data)

            # 文本消息 (手动输入模式)
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "text_input":
                        utterance = Utterance(
                            text=data["text"],
                            speaker="opponent",
                        )
                        await utterance_queue.put(utterance)
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        logger.info("客户端断开连接")
    except Exception:
        logger.exception("WebSocket 处理出错")
    finally:
        if stt_connected:
            await stt.close()
        await transcript_queue.put(None)  # 停止 accumulator
        accumulator_task.cancel()
        processor_task.cancel()
        logger.info("连接清理完成")
