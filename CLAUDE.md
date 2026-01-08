# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow: Dual-Agent (Hard Rule)

This repo uses a dual-agent workflow.

- **Claude Code**: analysis, specs/instructions for Codex, running tests/validation, reviewing results.
- **Codex**: implements code changes per instruction docs.
- **Claude Code must not directly modify code**, especially `*.py` files.

Instruction docs live in: `.claude/specs/benchmark-intelligence-agent/CODEX-*.md`

## Quick Commands

Python version: **3.11**.

### Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run pipeline (end-to-end)

```bash
.venv/bin/python -m src.main
```

### Quick validation

```bash
bash scripts/quick_validation.sh
```

### Lint / format

```bash
black .
ruff check .
```

### Tests

```bash
pytest -q
pytest tests/unit -v
pytest tests/unit/test_something.py -v
```

## Big Picture Architecture

BenchScope (Benchmark Intelligence Agent) runs a daily pipeline:

1. Collect candidates from multiple sources
2. Rule-based prefiltering (including URL heuristics)
3. LLM + rules scoring
4. Store results to Feishu Bitable (primary) with SQLite fallback
5. Send Feishu notifications/cards for top candidates

Primary entrypoint: `src/main.py`.

Core modules:

- `src/collectors/*`: source collectors (arXiv, GitHub, HuggingFace, HELM, etc.)
- `src/prefilter/rule_filter.py`: URL dedup + benchmark heuristics (filters early)
- `src/scorer/*`: LLM scoring + any domain scorer(s)
- `src/storage/*`: Feishu Bitable as primary store, SQLite fallback; `StorageManager` coordinates switching
- `src/notifier/feishu_notifier.py`: Feishu webhook notifications (interactive cards)
- `src/api/feishu_callback.py`: Feishu callbacks (if enabled/used)

Key design: Feishu is the durable “system of record”; SQLite is for degraded operation.

## Config & Environment

- Source configuration: `config/sources.yaml`
- Local env vars: `.env.local` (copy from `.env.example`)

Feishu + LLM require credentials (see `.env.example`).

## Repo Conventions (Non-negotiables)

- Key business-logic comments should be in **Chinese**.
- Keep nesting ≤ 3 levels in Python functions.
- Avoid magic numbers; prefer `src/common/constants.py` or config.

## Notification Deduplication

Notification deduplication relies on `notification_history.db` and GitHub Actions persistence/validation logic.
See the recent Phase 17/18 spec docs in `.claude/specs/benchmark-intelligence-agent/` (e.g. `CODEX-PHASE17-NOTIFICATION-DEDUP.md`, `CODEX-P18-NOTIFICATION-DEDUP-FIX.md`).
