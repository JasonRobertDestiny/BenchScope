"""规则预筛选引擎"""
from __future__ import annotations

import logging
from typing import List

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


def prefilter(candidate: RawCandidate) -> bool:
    """Phase 2 基线预筛选规则"""

    if not candidate.title or len(candidate.title.strip()) < 10:
        logger.debug("过滤: 标题过短 - %s", candidate.title)
        return False

    if not candidate.abstract or len(candidate.abstract.strip()) < 20:
        logger.debug("过滤: 摘要过短 - %s", candidate.title)
        return False

    if not candidate.url or not candidate.url.startswith(("http://", "https://")):
        logger.debug("过滤: URL无效 - %s", candidate.url)
        return False

    valid_sources = ["arxiv", "github", "pwc", "huggingface"]
    if candidate.source not in valid_sources:
        logger.debug("过滤: 来源不在白名单 - %s", candidate.source)
        return False

    text = f"{candidate.title} {candidate.abstract}".lower()
    matched = [kw for kw in constants.BENCHMARK_KEYWORDS if kw in text]
    if not matched:
        logger.debug("过滤: 无关键词命中 - %s", candidate.title)
        return False

    logger.debug("通过: %s", candidate.title[:50])
    return True


def prefilter_batch(candidates: List[RawCandidate]) -> List[RawCandidate]:
    """批量预筛选"""

    if not candidates:
        return []

    filtered = [c for c in candidates if prefilter(c)]
    rate = 100 * (1 - len(filtered) / len(candidates))
    logger.info(
        "预筛选完成,输入%d条,输出%d条,过滤率%.1f%%",
        len(candidates),
        len(filtered),
        rate,
    )
    return filtered
