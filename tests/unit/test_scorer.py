"""评分模块单元测试"""
from __future__ import annotations

import pytest

from src.config import get_settings
from src.models import RawCandidate
from src.scorer.llm_scorer import LLMScorer
from src.scorer.rule_scorer import RuleScorer


@pytest.mark.asyncio
async def test_llm_scorer_basic(monkeypatch):
    """LLM成功返回后应解析为BenchmarkScore"""

    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    scorer = LLMScorer()

    async def fake_call(prompt: str):  # noqa: ARG001
        return {
            "innovation": 8,
            "technical_depth": 7,
            "impact": 6,
            "data_quality": 5,
            "reproducibility": 4,
        }

    monkeypatch.setattr(scorer, "_call_with_retry", fake_call)

    candidate = RawCandidate(title="TestBench", url="https://example.com", source="arxiv", abstract="demo")
    score = await scorer.score(candidate)

    assert score.total_score == 30
    assert score.priority == "medium"


@pytest.mark.asyncio
async def test_llm_scorer_without_api_key_fallback(monkeypatch):
    """未配置API key时直接fallback到规则评分"""

    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    scorer = LLMScorer()
    candidate = RawCandidate(title="Fallback", url="https://example.com", source="github", github_stars=200)

    score = await scorer.score(candidate)
    fallback = scorer.rule_scorer.score(candidate)

    assert score.total_score == fallback.total_score


def test_rule_scorer_thresholds():
    """规则评分应随star上升而增加"""

    scorer = RuleScorer()
    low = scorer.score(RawCandidate(title="Low", url="https://a", source="github", github_stars=10))
    high = scorer.score(RawCandidate(title="High", url="https://b", source="github", github_stars=1500))

    assert high.total_score > low.total_score
