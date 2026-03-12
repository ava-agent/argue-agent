from __future__ import annotations

import struct
import logging

logger = logging.getLogger(__name__)


def float32_to_int16(float32_bytes: bytes) -> bytes:
    """将浏览器 Web Audio API 输出的 Float32 PCM 转换为 Int16 PCM。

    浏览器 AudioWorklet 输出的是 Float32 [-1.0, 1.0]，
    Deepgram 需要的是 Int16 [-32768, 32767]。
    """
    n_samples = len(float32_bytes) // 4
    float_samples = struct.unpack(f"<{n_samples}f", float32_bytes)
    int_samples = []
    for s in float_samples:
        clamped = max(-1.0, min(1.0, s))
        int_samples.append(int(clamped * 32767))
    return struct.pack(f"<{n_samples}h", *int_samples)
