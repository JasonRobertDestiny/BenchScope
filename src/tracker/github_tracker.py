"""GitHub Release 版本跟踪器"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx

from src.models import GitHubRelease

logger = logging.getLogger(__name__)


class GitHubReleaseTracker:
    """监控GitHub仓库的最新Release"""

    def __init__(
        self, db_path: str = "fallback.db", github_token: Optional[str] = None
    ) -> None:
        self.db_path = Path(db_path)
        self.github_token = github_token
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS github_releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_url TEXT NOT NULL,
                    tag_name TEXT NOT NULL,
                    published_at TIMESTAMP NOT NULL,
                    release_notes TEXT,
                    html_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_url, tag_name)
                )
                """
            )
            conn.commit()
        logger.debug("GitHub Release表检查完成")

    def _extract_owner_repo(self, repo_url: str) -> tuple[str, str] | None:
        pattern = r"github\.com/([^/]+)/([^/\.]+)"
        match = re.search(pattern, repo_url)
        if match:
            return match.group(1), match.group(2)
        logger.debug("无法解析GitHub仓库地址: %s", repo_url)
        return None

    def _build_headers(
        self, accept: str = "application/vnd.github+json"
    ) -> dict[str, str]:
        headers = {"Accept": accept}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    async def check_updates(self, repo_urls: List[str]) -> List[GitHubRelease]:
        """检查一组仓库是否有新Release"""

        if not repo_urls:
            return []

        new_releases: List[GitHubRelease] = []
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            for repo_url in repo_urls:
                release = await self._fetch_latest_release(client, repo_url)
                if not release:
                    continue
                if self._is_recorded(release):
                    continue
                self._store_release(release)
                new_releases.append(release)
                logger.info("发现新Release: %s %s", release.repo_url, release.tag_name)

        return new_releases

    async def _fetch_latest_release(
        self, client: httpx.AsyncClient, repo_url: str
    ) -> Optional[GitHubRelease]:
        owner_repo = self._extract_owner_repo(repo_url)
        if not owner_repo:
            return None

        owner, repo = owner_repo
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        try:
            resp = await client.get(api_url)
            if resp.status_code == 404:
                logger.debug("仓库无Release: %s", repo_url)
                return None
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("获取GitHub Release失败(%s): %s", repo_url, exc)
            return None

        data = resp.json()
        if not data:
            return None

        tag_name = data.get("tag_name")
        published_at = data.get("published_at")
        if not tag_name or not published_at:
            return None

        published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        notes = data.get("body") or "(无更新说明)"
        html_url = data.get("html_url", repo_url)

        return GitHubRelease(
            repo_url=repo_url,
            tag_name=tag_name,
            published_at=published_dt,
            release_notes=notes.strip(),
            html_url=html_url,
        )

    def _is_recorded(self, release: GitHubRelease) -> bool:
        query = (
            "SELECT 1 FROM github_releases WHERE repo_url = ? AND tag_name = ? LIMIT 1"
        )
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(query, (release.repo_url, release.tag_name)).fetchone()
            return row is not None

    def _store_release(self, release: GitHubRelease) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO github_releases (repo_url, tag_name, published_at, release_notes, html_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    release.repo_url,
                    release.tag_name,
                    release.published_at.isoformat(),
                    release.release_notes,
                    release.html_url,
                ),
            )
            conn.commit()
        logger.debug("记录GitHub Release: %s %s", release.repo_url, release.tag_name)
