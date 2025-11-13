"""规则评分兜底逻辑"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.common import constants
from src.models import BenchmarkScore, RawCandidate


@dataclass(slots=True)
class RuleScorer:
    """基于简单启发式的评分器"""

    thresholds: Dict[int, int] = None

    def __post_init__(self) -> None:
        if self.thresholds is None:
            self.thresholds = dict(constants.RULE_SCORE_THRESHOLDS)

    def score(self, candidate: RawCandidate) -> BenchmarkScore:
        """根据GitHub star与信息完整度估算得分"""

        base = self._score_from_stars(candidate.github_stars or 0)
        bonus = 1 if candidate.abstract else 0
        reproducibility = min(10, base + (1 if candidate.github_url else 0))

        return BenchmarkScore(
            innovation=min(10, base + bonus),
            technical_depth=min(10, base + bonus),
            impact=min(10, base + 1),
            data_quality=min(10, base + (1 if candidate.dataset_url else 0)),
            reproducibility=reproducibility,
        )

    def _score_from_stars(self, stars: int) -> int:
        """按照阈值区间映射粗略得分"""

        for threshold, score in sorted(self.thresholds.items(), reverse=True):
            if stars >= threshold:
                return score
        return constants.RULE_SCORE_MIN
