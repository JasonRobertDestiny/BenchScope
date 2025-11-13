"""核心数据模型定义"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

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
class ScoredCandidate:
    """Phase 2评分后的候选项 (5维度评分模型)"""

    # RawCandidate字段
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

    # Phase 2评分字段
    activity_score: float = 0.0  # 活跃度 (25%)
    reproducibility_score: float = 0.0  # 可复现性 (30%)
    license_score: float = 0.0  # 许可合规 (20%)
    novelty_score: float = 0.0  # 新颖性 (15%)
    relevance_score: float = 0.0  # MGX适配度 (10%)
    reasoning: str = ""

    @property
    def total_score(self) -> float:
        """加权总分(0-10)"""

        return (
            self.activity_score * 0.25
            + self.reproducibility_score * 0.30
            + self.license_score * 0.20
            + self.novelty_score * 0.15
            + self.relevance_score * 0.10
        )

    @property
    def priority(self) -> str:
        """自动分级"""

        total = self.total_score
        if total >= 8.0:
            return "high"
        if total >= 6.0:
            return "medium"
        return "low"
