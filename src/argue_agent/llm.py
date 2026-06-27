from __future__ import annotations

import json
import re

import httpx
from openai import AsyncOpenAI

from argue_agent.config import settings


def create_ark_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
        http_client=httpx.AsyncClient(proxy=None),
    )


def parse_model_json(content: str) -> dict:
    normalized = content.strip()
    normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*```$", "", normalized)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", normalized)
        if not match:
            raise ValueError("Model response did not include a JSON object")
        return json.loads(match.group(0))
