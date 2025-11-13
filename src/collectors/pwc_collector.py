"""Papers with Code 采集器"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

import httpx

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class PwCCollector:
    """通过Papers with Code API抓取Agent相关论文"""

    def __init__(self) -> None:
        self.base_url = constants.PWC_API_BASE
        self.timeout = constants.PWC_TIMEOUT_SECONDS
        self.keywords = constants.PWC_QUERY_KEYWORDS
        self.page_size = constants.PWC_PAGE_SIZE
        self.min_task_papers = constants.PWC_MIN_TASK_PAPERS

    async def collect(self) -> List[RawCandidate]:
        """按关键词并发搜索符合条件的任务并抓取论文"""

        candidates: List[RawCandidate] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            jobs = [self._fetch_keyword_bundle(client, keyword) for keyword in self.keywords]
            results = await asyncio.gather(*jobs, return_exceptions=True)

        for keyword, result in zip(self.keywords, results, strict=False):
            if isinstance(result, Exception):
                logger.error("PwC关键词任务失败(%s): %s", keyword, result)
                continue
            candidates.extend(result)

        logger.info("PwC采集完成,候选总数%s", len(candidates))
        return candidates

    async def _fetch_keyword_bundle(
        self, client: httpx.AsyncClient, keyword: str
    ) -> List[RawCandidate]:
        """单个关键词下并发抓取任务和论文"""

        tasks = await self._fetch_tasks(client, keyword)
        paper_jobs = [self._fetch_task_papers(client, task) for task in tasks]
        paper_results = await asyncio.gather(*paper_jobs, return_exceptions=True)

        parsed: List[RawCandidate] = []
        for task_meta, papers in zip(tasks, paper_results, strict=False):
            if isinstance(papers, Exception):
                logger.error("PwC任务论文失败(%s): %s", task_meta.get("slug"), papers)
                continue
            parsed.extend(self._parse_papers(papers, task_meta.get("name")))
        return parsed

    async def _fetch_tasks(self, client: httpx.AsyncClient, keyword: str) -> List[dict]:
        """查询满足论文数量要求的任务"""

        url = f"{self.base_url}/tasks/"
        params = {"page": 1, "page_size": self.page_size, "q": keyword}
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("PwC任务列表超时: %s", keyword)
            return []
        except httpx.HTTPStatusError as exc:  # noqa: BLE001
            logger.error("PwC任务列表失败(%s): %s", keyword, exc)
            return []

        results = resp.json().get("results", [])
        filtered: List[dict] = []
        for task in results:
            papers_count = (
                task.get("paper_count")
                or task.get("num_papers")
                or task.get("papers_count")
                or 0
            )
            if papers_count >= self.min_task_papers:
                filtered.append(task)
        return filtered

    async def _fetch_task_papers(self, client: httpx.AsyncClient, task: dict) -> List[dict]:
        """抓取指定任务的论文列表"""

        slug = task.get("slug")
        if not slug:
            return []

        url = f"{self.base_url}/tasks/{slug}/papers/"
        params = {"page": 1, "page_size": self.page_size}
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("PwC任务论文超时: %s", slug)
            return []
        except httpx.HTTPStatusError as exc:  # noqa: BLE001
            logger.error("PwC任务论文失败(%s): %s", slug, exc)
            return []

        return resp.json().get("results", [])

    def _parse_papers(self, papers: List[dict], task_name: str | None) -> List[RawCandidate]:
        """将API返回转换为RawCandidate"""

        parsed: List[RawCandidate] = []
        for paper in papers:
            title = paper.get("title", "").strip()
            if not title:
                continue

            parsed.append(
                RawCandidate(
                    title=title,
                    url=paper.get("url_abs", paper.get("url", "")),
                    source="pwc",
                    abstract=paper.get("abstract"),
                    authors=paper.get("authors"),
                    publish_date=self._parse_date(paper.get("published")),
                    github_stars=paper.get("github_stars"),
                    github_url=(paper.get("official_code", {}) or {}).get("url"),
                    dataset_url=(paper.get("datasets", [{}])[0] or {}).get("url"),
                    raw_metadata={
                        "task": task_name or "",
                        "paper_url": paper.get("url"),
                    },
                )
            )

        return parsed

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """解析ISO日期,容错空值"""

        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            logger.debug("无法解析PwC日期: %s", date_str)
            return None
