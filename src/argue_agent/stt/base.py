from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from argue_agent.analysis.models import TranscriptSegment


class BaseSTT(ABC):
    """STT 抽象接口。"""

    def __init__(self, transcript_queue: asyncio.Queue[TranscriptSegment | None]) -> None:
        self.transcript_queue = transcript_queue

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...
