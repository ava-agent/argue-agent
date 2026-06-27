# Argue Agent Triage - 2026-06-27

## Repository

- GitHub: `ava-agent/argue-agent`
- Public URL: `https://argue.rxcloud.group`

## Actions Taken

- Added `AGENTS.md` with project state, command entry points, secret handling, and deployment notes.

## Validation

- Passed: `git diff --check`
- Passed: refreshed global inventory readiness check reports readiness 100.

## Follow-Up

- Add automated tests for claim extraction and verdict synthesis with mocked LLM/search responses.
- Ignore or clean local `.playwright-mcp/` if it is only a QA artifact.
