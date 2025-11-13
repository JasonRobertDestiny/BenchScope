"""GitHub Trending采集器"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import List

import httpx

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class GitHubCollector:
    """通过GitHub Search API抓取高star仓库"""

    def __init__(self) -> None:
        self.topics = constants.GITHUB_TOPICS
        self.min_stars = constants.GITHUB_MIN_STARS
        self.timeout = constants.GITHUB_TIMEOUT_SECONDS
        self.api_url = "https://api.github.com/search/repositories"
        self.per_page = 5
        self.token = os.getenv("GITHUB_TOKEN")

    async def collect(self) -> List[RawCandidate]:
        candidates: List[RawCandidate] = []

        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            tasks = [self._fetch_topic(client, topic) for topic in self.topics]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for topic, result in zip(self.topics, results, strict=False):
            if isinstance(result, Exception):
                logger.error("GitHub API 任务失败(%s): %s", topic, result)
                continue
            candidates.extend(result)

        logger.info("GitHub采集完成,候选总数%s", len(candidates))
        return candidates

    async def _fetch_topic(
        self, client: httpx.AsyncClient, topic: str
    ) -> List[RawCandidate]:
        """调用GitHub搜索API"""

        params = {
            "q": f"{topic} benchmark in:name,description,readme",
            "sort": "stars",
            "order": "desc",
            "per_page": self.per_page,
        }
        resp = await client.get(self.api_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])

        parsed: List[RawCandidate] = []
        for repo in items:
            stars = repo.get("stargazers_count", 0)
            if stars < self.min_stars:
                continue

            parsed.append(
                RawCandidate(
                    title=repo.get("full_name", ""),
                    url=repo.get("html_url", ""),
                    source="github",
                    abstract=repo.get("description"),
                    github_stars=stars,
                    github_url=repo.get("html_url"),
                    publish_date=self._parse_datetime(repo.get("pushed_at")),
                    raw_metadata={
                        "topic": topic,
                        "language": repo.get("language"),
                    },
                )
            )

        return parsed

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
