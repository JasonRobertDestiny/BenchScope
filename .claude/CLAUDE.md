# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Note:** See `/CLAUDE.md` (root) for quick commands and architecture overview.
> See `/README.md` for comprehensive project documentation.

## Project Context

**BenchScope** = Benchmark Intelligence Agent for [MGX](https://mgx.dev)

Automated daily pipeline: Collect AI benchmark resources -> Score -> Store to Feishu -> Notify team.

**Current version:** v1.6.0 (Phase 1-6 complete)

## Key Specs & Design Docs

Located in `.claude/specs/benchmark-intelligence-agent/`:

| Doc | Purpose |
|-----|---------|
| `01-product-requirements.md` | PRD with scoring criteria and workflow |
| `02-system-architecture.md` | System design and data models |
| `CODEX-P18-NOTIFICATION-DEDUP-FIX.md` | Notification deduplication implementation |

## Module Responsibilities

| Module | What it does |
|--------|--------------|
| `src/collectors/` | 7 data sources (arXiv, GitHub, HuggingFace, HELM, TechEmpower, DBEngines, Twitter) |
| `src/prefilter/` | URL dedup + benchmark keyword filtering (40-60% noise removal) |
| `src/enhancer/` | GROBID PDF parsing for richer arXiv metadata |
| `src/scorer/` | GPT-4o-mini scoring with 5 dimensions + Redis cache |
| `src/storage/` | Feishu Bitable (primary) + SQLite (fallback) via StorageManager |
| `src/notifier/` | Feishu webhook interactive cards |

## Scoring Dimensions

| Dimension | Weight | Measures |
|-----------|--------|----------|
| Activity | 15% | GitHub stars, update frequency |
| Reproducibility | 30% | Code/data/docs availability |
| License | 15% | MIT/Apache/BSD compliance |
| Novelty | 15% | Innovation vs existing benchmarks |
| MGX Relevance | 25% | Multi-agent, code-gen, tool-use fit |

## Critical Implementation Notes

1. **Storage fallback:** If Feishu API fails, data goes to SQLite. `StorageManager.sync_from_sqlite()` handles recovery.

2. **Notification deduplication:** Uses `notification_history.db` with GitHub Actions artifact persistence. See P18 spec for details.

3. **PDF enhancement:** GROBID Docker container auto-starts if available. Disabled gracefully if Docker unavailable.

4. **Testing locally:** Use `SKIP_FEISHU_PUSH=1` to prevent notification spam during development.
