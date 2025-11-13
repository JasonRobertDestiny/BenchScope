"""版本跟踪器测试"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import asyncio
import pytest

from src.models import ArxivVersion, GitHubRelease
from src.tracker.arxiv_tracker import ArxivVersionTracker
from src.tracker.github_tracker import GitHubReleaseTracker


class _DummyClient:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_extract_owner_repo(tmp_path):
    tracker = GitHubReleaseTracker(db_path=str(tmp_path / "releases.db"))
    assert tracker._extract_owner_repo("https://github.com/openai/gpt") == ("openai", "gpt")
    assert tracker._extract_owner_repo("invalid") is None


def test_extract_arxiv_id(tmp_path):
    tracker = ArxivVersionTracker(db_path=str(tmp_path / "arxiv.db"))
    assert tracker._extract_arxiv_id("https://arxiv.org/abs/2311.04355v1") == "2311.04355"
    assert tracker._extract_arxiv_id("https://example.com") is None


@pytest.mark.asyncio
async def test_github_tracker_dedup(monkeypatch, tmp_path):
    tracker = GitHubReleaseTracker(db_path=str(tmp_path / "releases.db"))

    release = GitHubRelease(
        repo_url="https://github.com/openai/gpt",
        tag_name="v1.0.0",
        published_at=datetime.now(timezone.utc),
        release_notes="Initial",
        html_url="https://github.com/openai/gpt/releases/tag/v1.0.0",
    )

    async_mock = AsyncMock(return_value=release)
    monkeypatch.setattr(tracker, "_fetch_latest_release", async_mock)
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: _DummyClient())

    first = await tracker.check_updates([release.repo_url])
    assert len(first) == 1
    second = await tracker.check_updates([release.repo_url])
    assert second == []


@pytest.mark.asyncio
async def test_arxiv_tracker_records(monkeypatch, tmp_path):
    tracker = ArxivVersionTracker(db_path=str(tmp_path / "arxiv.db"))
    version = ArxivVersion(
        arxiv_id="2311.04355",
        version="v2",
        updated_at=datetime.now(timezone.utc),
        summary="Update",
        url="https://arxiv.org/abs/2311.04355v2",
    )

    async_mock = AsyncMock(return_value=version)
    monkeypatch.setattr(tracker, "_fetch_latest_version", async_mock)

    urls = ["https://arxiv.org/abs/2311.04355"]
    first = await tracker.check_updates(urls)
    assert len(first) == 1
    second = await tracker.check_updates(urls)
    assert second == []
