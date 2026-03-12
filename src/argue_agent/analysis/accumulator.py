from __future__ import annotations

import asyncio
import logging

from argue_agent.analysis.models import TranscriptSegment, Utterance

logger = logging.getLogger(__name__)


class SentenceAccumulator:
    """将流式转录片段累积为完整的语句。

    当收到 utterance end 标记时，将累积的文本作为一个完整语句发出。
    """

    def __init__(
        self,
        transcript_queue: asyncio.Queue[TranscriptSegment | None],
        utterance_queue: asyncio.Queue[Utterance],
    ) -> None:
        self.transcript_queue = transcript_queue
        self.utterance_queue = utterance_queue
        self._buffer: list[str] = []
        self._current_speaker: int | None = None

    async def run(self) -> None:
        while True:
            segment = await self.transcript_queue.get()
            if segment is None:
                break

            # utterance end 标记 (空文本 + is_final)
            if not segment.text and segment.is_final:
                await self._flush()
                continue

            if segment.is_final:
                self._buffer.append(segment.text)
                if segment.speaker is not None:
                    self._current_speaker = segment.speaker

    async def _flush(self) -> None:
        if not self._buffer:
            return

        text = "".join(self._buffer).strip()
        if not text:
            self._buffer.clear()
            return

        speaker = f"speaker_{self._current_speaker}" if self._current_speaker is not None else "opponent"
        utterance = Utterance(text=text, speaker=speaker)
        await self.utterance_queue.put(utterance)
        logger.info("完整语句: [%s] %s", speaker, text)

        self._buffer.clear()
        self._current_speaker = None
