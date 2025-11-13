"""规则预筛选模块"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import List, Set

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class RuleBasedPrefilter:
    """通过轻量规则过滤噪音数据"""

    def __init__(self, similarity_threshold: float = constants.PREFILTER_SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold
        self.min_github_stars = constants.PREFILTER_MIN_GITHUB_STARS

    def filter(self, candidates: List[RawCandidate]) -> List[RawCandidate]:
        """执行预筛选并记录过滤原因"""

        filtered: List[RawCandidate] = []
        seen_urls: Set[str] = set()
        accepted_titles: List[str] = []

        for candidate in candidates:
            url_key = candidate.url.strip().lower()
            if url_key in seen_urls:
                logger.debug("规则过滤: URL重复 %s", candidate.title)
                continue

            if self._is_duplicate_title(candidate.title, accepted_titles):
                logger.debug("规则过滤: 标题相似 %s", candidate.title)
                continue

            reason = self._should_reject(candidate)
            if reason:
                logger.debug("规则过滤: %s -> %s", reason, candidate.title)
                continue

            filtered.append(candidate)
            seen_urls.add(url_key)
            accepted_titles.append(candidate.title)

        logger.info(
            "预筛选完成,输入%s条,输出%s条,过滤率%.0f%%",
            len(candidates),
            len(filtered),
            0 if not candidates else (1 - len(filtered) / len(candidates)) * 100,
        )
        return filtered

    def _is_duplicate_title(self, title: str, accepted_titles: List[str]) -> bool:
        """利用相似度避免重复记录"""

        for existing in accepted_titles:
            ratio = SequenceMatcher(None, title.lower(), existing.lower()).ratio()
            if ratio >= self.similarity_threshold:
                return True
        return False

    def _should_reject(self, candidate: RawCandidate) -> str | None:
        """根据业务规则判断是否丢弃"""

        if candidate.source == "github":
            stars = candidate.github_stars or 0
            if stars < self.min_github_stars:
                return "GitHub star过低"

        if candidate.source == "arxiv" and not candidate.abstract:
            return "arXiv无摘要"

        if "survey" in candidate.title.lower() and not candidate.github_url:
            return "Survey无代码"

        return None
