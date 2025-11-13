"""规则预筛选测试"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models import RawCandidate
from src.prefilter.rule_filter import prefilter, prefilter_batch


def test_prefilter_valid_candidate():
    candidate = RawCandidate(
        title="AgentBench: Evaluating LLMs as Agents",
        url="https://arxiv.org/abs/2308.03688",
        source="arxiv",
        abstract="We present AgentBench, a benchmark for evaluating LLMs as agents with multiple tasks.",
        authors=["Author A"],
        publish_date=datetime.now(timezone.utc),
    )
    assert prefilter(candidate) is True


def test_prefilter_short_title():
    candidate = RawCandidate(
        title="Short",
        url="https://example.com",
        source="arxiv",
        abstract="This is a benchmark with enough description for testing.",
    )
    assert prefilter(candidate) is False


def test_prefilter_no_abstract():
    candidate = RawCandidate(
        title="Valid Benchmark Title",
        url="https://example.com",
        source="arxiv",
        abstract="",
    )
    assert prefilter(candidate) is False


def test_prefilter_no_keywords():
    candidate = RawCandidate(
        title="Unrelated topic",
        url="https://example.com",
        source="github",
        abstract="This describes something completely different, like weather forecasting systems.",
    )
    assert prefilter(candidate) is False


def test_prefilter_invalid_url():
    candidate = RawCandidate(
        title="Benchmark with invalid url",
        url="ftp://example.com",
        source="github",
        abstract="Benchmark paper with enough text to pass length requirements.",
    )
    assert prefilter(candidate) is False


def test_prefilter_invalid_source():
    candidate = RawCandidate(
        title="Benchmark from unknown source",
        url="https://example.com",
        source="unknown",
        abstract="Benchmark content with enough length and keywords.",
    )
    assert prefilter(candidate) is False


def test_prefilter_batch():
    candidates = [
        RawCandidate(
            title="Valid Benchmark Paper",
            url="https://example.com/1",
            source="arxiv",
            abstract="A benchmark evaluation paper with sufficient content.",
        ),
        RawCandidate(
            title="Short",
            url="https://example.com/2",
            source="arxiv",
            abstract="Valid abstract but short title.",
        ),
        RawCandidate(
            title="Another Benchmark Dataset",
            url="https://example.com/3",
            source="github",
            abstract="Dataset and evaluation benchmark with detailed description.",
        ),
    ]

    filtered = prefilter_batch(candidates)
    assert len(filtered) == 2
