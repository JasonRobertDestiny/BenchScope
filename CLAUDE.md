# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

Python version: **3.11**. All commands use `.venv/bin/python`.

```bash
# Setup
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local  # Fill in credentials

# Run pipeline (end-to-end)
.venv/bin/python -m src.main

# Local testing (skip Feishu notifications)
SKIP_FEISHU_PUSH=1 .venv/bin/python -m src.main

# Lint / format
black . && ruff check .

# Tests
pytest -q                                    # All tests
pytest tests/ -v                             # Verbose
pytest tests/test_pdf_enhancer.py -v         # Single file
pytest tests/test_pdf_enhancer.py::test_name -v  # Single test

# Quick validation (checks code structure)
bash scripts/quick_validation.sh
```

## Architecture

BenchScope runs a daily pipeline via GitHub Actions (UTC 02:00):

```
main.py orchestrates:
  Collect → Prefilter → PDF Enhance → LLM Score → Store → Notify
```

**Data flow:**
1. `src/collectors/*` - Concurrent collection (arXiv, GitHub, HuggingFace, HELM, TechEmpower, DBEngines)
2. `src/prefilter/rule_filter.py` - URL dedup + benchmark heuristics (40-60% filtered)
3. `src/enhancer/pdf_enhancer.py` - GROBID PDF parsing for arXiv papers
4. `src/scorer/llm_scorer.py` - GPT-4o-mini 5-dimension scoring with Redis cache
5. `src/storage/storage_manager.py` - Feishu Bitable (primary) + SQLite (fallback)
6. `src/notifier/feishu_notifier.py` - Feishu webhook cards

**Key design:** Feishu is the durable "system of record"; SQLite is for degraded operation only.

## Config

- `config/sources.yaml` - Data source settings (keywords, time windows, limits)
- `.env.local` - Credentials (OPENAI_API_KEY, FEISHU_*, GITHUB_TOKEN, REDIS_URL)

## Code Conventions

- Business-logic comments in **Chinese**
- Function nesting ≤ 3 levels
- Magic numbers in `src/common/constants.py`
- Commit format: `type(scope): summary`

## Critical Constraints

1. Feishu API changes require backward-compatible migration
2. LLM scorer changes need sample input/output comparison
3. Notification dedup spec: `.claude/specs/benchmark-intelligence-agent/CODEX-P18-NOTIFICATION-DEDUP-FIX.md`
