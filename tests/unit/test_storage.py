"""SQLite降级存储测试"""
from __future__ import annotations

import pytest

from src.config import get_settings
from src.models import BenchmarkScore, RawCandidate, ScoredCandidate
from src.storage.sqlite_fallback import SQLiteFallback


@pytest.mark.asyncio
async def test_sqlite_fallback_roundtrip(tmp_path, monkeypatch):
    """写入后应能读取并标记同步"""

    get_settings.cache_clear()  # type: ignore[attr-defined]
    db_file = tmp_path / "fallback.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_file))

    fallback = SQLiteFallback()
    candidate = ScoredCandidate(
        raw=RawCandidate(title="SQLite", url="https://example.com", source="arxiv", abstract="demo"),
        score=BenchmarkScore(innovation=5, technical_depth=5, impact=5, data_quality=5, reproducibility=5),
    )

    await fallback.save([candidate])
    unsynced = await fallback.get_unsynced()
    assert len(unsynced) == 1

    await fallback.mark_synced([candidate.raw.url])
    await fallback.cleanup_old_records(days=0)
