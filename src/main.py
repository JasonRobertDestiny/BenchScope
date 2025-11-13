"""BenchScope 主编排器"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List

from src.collectors import ArxivCollector, GitHubCollector, PwCCollector
from src.config import Settings, get_settings
from src.models import RawCandidate, ScoredCandidate
from src.notifier import FeishuNotifier
from src.prefilter import RuleBasedPrefilter
from src.scorer import LLMScorer
from src.storage import StorageManager
from src.common import constants

logger = logging.getLogger(__name__)


async def run_pipeline() -> None:
    """执行完整的采集→预筛→评分→入库→通知流程"""

    settings = get_settings()
    _configure_logging(settings)

    collectors = [ArxivCollector(), GitHubCollector(), PwCCollector()]
    raw_candidates = await _collect_all(collectors)

    prefilter = RuleBasedPrefilter()
    filtered = prefilter.filter(raw_candidates)

    scorer = LLMScorer(settings)
    scored = await _score_candidates(filtered, scorer)

    storage = StorageManager()
    stored = await storage.save(scored)
    logger.info("存储阶段完成,飞书成功=%s", stored)

    notifier = FeishuNotifier(settings=settings)
    await notifier.notify(scored)


async def _collect_all(collectors) -> List[RawCandidate]:
    """并发执行采集器"""

    tasks = [collector.collect() for collector in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: List[RawCandidate] = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("采集器失败(%s): %s", collectors[idx].__class__.__name__, result)
            continue
        merged.extend(result)

    logger.info("采集阶段共获得%s条记录", len(merged))
    return merged


async def _score_candidates(candidates: List[RawCandidate], scorer: LLMScorer) -> List[ScoredCandidate]:
    """限制并发评分,并按分值降序"""

    semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)
    scored: List[ScoredCandidate] = []

    async def _score_single(candidate: RawCandidate) -> None:
        async with semaphore:
            try:
                score = await scorer.score(candidate)
                scored.append(ScoredCandidate(raw=candidate, score=score))
            except Exception as exc:  # noqa: BLE001
                logger.error("评分失败(%s): %s", candidate.title, exc)

    await asyncio.gather(*[_score_single(candidate) for candidate in candidates])
    scored.sort(key=lambda item: item.score.total_score, reverse=True)
    return scored


def _configure_logging(settings: Settings) -> None:
    """配置stdout+文件双通道日志"""

    log_path = Path(settings.logging.directory) / settings.logging.file_name
    handlers = [logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")]
    logging.basicConfig(
        level=settings.logging.level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


if __name__ == "__main__":
    asyncio.run(run_pipeline())
