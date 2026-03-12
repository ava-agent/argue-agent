from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlencode

import websockets

from argue_agent.analysis.models import TranscriptSegment
from argue_agent.config import settings
from argue_agent.stt.base import BaseSTT

logger = logging.getLogger(__name__)

UTTERANCE_END = TranscriptSegment(text="", is_final=True, confidence=0.0)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramSTT(BaseSTT):
    def __init__(
        self, transcript_queue: asyncio.Queue[TranscriptSegment | None]
    ) -> None:
        super().__init__(transcript_queue)
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._recv_task: asyncio.Task | None = None

    async def connect(self) -> None:
        params = {
            "model": "nova-3",
            "language": settings.stt_language,
            "smart_format": "true",
            "interim_results": "true",
            "utterance_end_ms": str(settings.stt_utterance_end_ms),
            "endpointing": str(settings.stt_endpointing_ms),
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
        }
        url = f"{DEEPGRAM_WS_URL}?{urlencode(params)}"
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._recv_task = asyncio.create_task(self._receive_loop())
        logger.info("Deepgram WebSocket 已连接")

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                msg_type = data.get("type", "")

                if msg_type == "Results":
                    alt = data["channel"]["alternatives"][0]
                    text = alt.get("transcript", "")
                    if text:
                        words = alt.get("words", [])
                        segment = TranscriptSegment(
                            text=text,
                            is_final=data.get("is_final", False),
                            confidence=alt.get("confidence", 0.0),
                            speaker=words[0].get("speaker") if words else None,
                        )
                        await self.transcript_queue.put(segment)

                elif msg_type == "UtteranceEnd":
                    await self.transcript_queue.put(UTTERANCE_END)

        except websockets.ConnectionClosed:
            logger.info("Deepgram 连接已关闭")
        except Exception:
            logger.exception("Deepgram 接收错误")

    async def send_audio(self, audio_chunk: bytes) -> None:
        if self._ws:
            await self._ws.send(audio_chunk)

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
