"""GitHub Trending采集器"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

import httpx
from bs4 import BeautifulSoup

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class GitHubCollector:
    """抓取GitHub Trending页面并提取高star仓库"""

    def __init__(self) -> None:
        self.topics = constants.GITHUB_TOPICS
        self.base_url = constants.GITHUB_TRENDING_URL
        self.timeout = constants.GITHUB_TIMEOUT_SECONDS
        self.min_stars = constants.GITHUB_MIN_STARS

    async def collect(self) -> List[RawCandidate]:
        """遍历设定话题,返回候选列表"""

        candidates: List[RawCandidate] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [self._fetch_topic(client, topic) for topic in self.topics]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for topic, result in zip(self.topics, results, strict=False):
            if isinstance(result, Exception):
                logger.error("GitHub Trending 任务失败(%s): %s", topic, result)
                continue
            candidates.extend(result)

        logger.info("GitHub采集完成,候选总数%s", len(candidates))
        return candidates

    async def _fetch_topic(
        self, client: httpx.AsyncClient, topic: str
    ) -> List[RawCandidate]:
        """并发抓取单个主题,提升整体吞吐"""

        url = f"{self.base_url}/{topic}?since=daily&spoken_language_code=en"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:  # noqa: BLE001
            logger.warning("GitHub Trending 超时: %s", topic)
            raise exc
        except httpx.HTTPStatusError as exc:  # noqa: BLE001
            logger.error("GitHub Trending 响应异常(%s): %s", topic, exc)
            raise exc

        return self._parse_html(resp.text, topic)

    def _parse_html(self, html: str, topic: str) -> List[RawCandidate]:
        """解析Trending页面HTML"""

        soup = BeautifulSoup(html, "html.parser")
        repos = soup.find_all("article", class_="Box-row")
        parsed: List[RawCandidate] = []

        for repo in repos:
            title_tag = repo.find("h2")
            if not title_tag:
                continue

            repo_name = title_tag.get_text(strip=True).replace(" ", "")
            repo_url = f"https://github.com/{repo_name}"

            stars = self._extract_stars(repo)
            if stars < self.min_stars:
                continue

            description_tag = repo.find("p")
            description = description_tag.get_text(strip=True) if description_tag else ""

            parsed.append(
                RawCandidate(
                    title=repo_name,
                    url=repo_url,
                    source="github",
                    abstract=description,
                    github_stars=stars,
                    github_url=repo_url,
                    publish_date=datetime.now(),
                    raw_metadata={"topic": topic},
                )
            )

        return parsed

    def _extract_stars(self, repo_node) -> int:
        """解析star文本为整数"""

        star_span = repo_node.find("svg", {"aria-label": "star"})
        if star_span:
            next_span = star_span.find_next("span")
            if next_span:
                return self._normalize_star_text(next_span.get_text(strip=True))

        # Trending页面也会在特定类中放置star
        alt_span = repo_node.find("span", class_="d-inline-block float-sm-right")
        if alt_span:
            return self._normalize_star_text(alt_span.get_text(strip=True))

        return 0

    @staticmethod
    def _normalize_star_text(text: str) -> int:
        """将1.2k等形式转换为整数"""

        cleaned = text.lower().replace(",", "")
        if cleaned.endswith("k"):
            return int(float(cleaned[:-1]) * 1000)
        if cleaned.endswith("m"):
            return int(float(cleaned[:-1]) * 1_000_000)
        try:
            return int(cleaned)
        except ValueError:
            logger.debug("无法解析star数: %s", text)
            return 0
