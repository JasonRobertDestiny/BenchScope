"""arXiv 采集器实现"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import arxiv

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class ArxivCollector:
    """负责抓取最近24小时内的Benchmark相关论文"""

    def __init__(self) -> None:
        self.keywords = constants.ARXIV_KEYWORDS
        self.categories = constants.ARXIV_CATEGORIES
        self.max_results = constants.ARXIV_MAX_RESULTS
        self.timeout = constants.ARXIV_TIMEOUT_SECONDS
        self.max_retries = constants.ARXIV_MAX_RETRIES
        self.lookback = timedelta(hours=constants.ARXIV_LOOKBACK_HOURS)

    async def collect(self) -> List[RawCandidate]:
        """抓取并返回候选列表,失败时返回空列表"""

        for attempt in range(1, self.max_retries + 1):
            try:
                async with asyncio.timeout(self.timeout):
                    results = await asyncio.to_thread(self._fetch_results)
                return self._to_candidates(results)
            except asyncio.TimeoutError:
                logger.warning("arXiv查询超时,准备重试(%s/%s)", attempt, self.max_retries)
            except Exception as exc:  # noqa: BLE001
                logger.error("arXiv采集失败(%s/%s): %s", attempt, self.max_retries, exc)

            await asyncio.sleep(attempt)

        logger.error("arXiv连续失败,返回空列表")
        return []

    def _fetch_results(self) -> List[arxiv.Result]:
        """同步执行arXiv查询,供线程池调用"""

        query = " OR ".join([f'all:"{kw}"' for kw in self.keywords])
        cat_filter = " OR ".join([f"cat:{cat}" for cat in self.categories])
        search = arxiv.Search(
            query=f"({query}) AND ({cat_filter})",
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        return list(search.results())

    def _to_candidates(self, results: List[arxiv.Result]) -> List[RawCandidate]:
        """将arXiv返回转成内部数据结构"""

        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - self.lookback
        candidates: List[RawCandidate] = []

        for paper in results:
            # 确保published是timezone-aware
            published_dt = paper.published
            if published_dt and published_dt.tzinfo is None:
                # 如果是naive datetime，添加UTC时区
                published_dt = published_dt.replace(tzinfo=timezone.utc)

            if published_dt and published_dt < cutoff:
                continue

            candidates.append(
                RawCandidate(
                    title=paper.title.strip(),
                    url=paper.pdf_url or paper.entry_id,
                    source="arxiv",
                    abstract=paper.summary,
                    authors=[author.name for author in paper.authors],
                    publish_date=paper.published,
                    paper_url=paper.entry_id,  # arXiv论文页面链接
                    raw_metadata={
                        "arxiv_id": paper.entry_id.split("/")[-1],
                        "categories": ",".join(paper.categories or []),
                        "comment": paper.comment or "",
                    },
                )
            )

        logger.info("arXiv采集完成,有效候选%s条", len(candidates))
        return candidates
