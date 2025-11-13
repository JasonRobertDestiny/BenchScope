"""核心数据模型定义"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from src.common import constants

SourceType = Literal["arxiv", "github", "pwc", "huggingface"]


@dataclass(slots=True)
class RawCandidate:
    """采集器原始输出结构"""

    title: str
    url: str
    source: SourceType
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    dataset_url: Optional[str] = None
    raw_metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkScore:
    """LLM与规则评分统一结构"""

    innovation: int
    technical_depth: int
    impact: int
    data_quality: int
    reproducibility: int

    @property
    def total_score(self) -> int:
        """总分用于排序"""

        return (
            self.innovation
            + self.technical_depth
            + self.impact
            + self.data_quality
            + self.reproducibility
        )

    @property
    def priority(self) -> str:
        """根据阈值划分优先级"""

        if self.total_score >= constants.PRIORITY_HIGH_THRESHOLD:
            return "high"
        if self.total_score >= constants.PRIORITY_MEDIUM_THRESHOLD:
            return "medium"
        return "low"


@dataclass(slots=True)
class ScoredCandidate:
    """通过评分后的候选项"""

    raw: RawCandidate
    score: BenchmarkScore
    filter_reason: Optional[str] = None
