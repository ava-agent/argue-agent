# Argue Agent Maintenance Guide

## Project State

- Repository: `ava-agent/argue-agent`
- Public URL: `https://argue.rxcloud.group`
- Stack: FastAPI, Pydantic, Volcengine Ark/OpenAI-compatible SDK, DuckDuckGo/Tavily search, optional Deepgram STT
- Product: realtime debate/fact-checking assistant.

## Before Editing

- Keep Ark, Tavily, and Deepgram keys in local `.env` or platform secrets.
- Be careful with search-provider behavior; local DuckDuckGo and Vercel Tavily paths differ.
- Do not commit `.venv/`, `.playwright-mcp/`, generated recordings, caches, or filled `.env`.

## Useful Commands

- Install: `pip install -e .`
- Run local app: `python -m argue_agent`
- Text pipeline demo: `python scripts/demo_text.py`
- Vercel entry point: `api/index.py`

## Deployment Notes

- Vercel deployment is configured through `vercel.json`.
- Public domain should stay aligned with `https://argue.rxcloud.group`.
- Validate text mode, browser speech mode, extraction, evidence search, and verdict rendering before release.
