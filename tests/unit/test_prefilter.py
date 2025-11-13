"""规则预筛选测试"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.models import RawCandidate
from src.prefilter.rule_filter import prefilter, prefilter_batch


def test_prefilter_valid_candidate():
    candidate = _build_candidate()
    assert prefilter(candidate) is True


def test_prefilter_short_title():
    candidate = _build_candidate(title="Short")
    assert prefilter(candidate) is False


def test_prefilter_no_abstract():
    candidate = _build_candidate(abstract="")
    assert prefilter(candidate) is False


def test_prefilter_no_keywords():
    candidate = _build_candidate(
        title="Unrelated topic",
        abstract="This describes something completely different, like weather forecasting systems.",
    )
    assert prefilter(candidate) is False


def test_prefilter_invalid_url():
    candidate = _build_candidate(url="ftp://example.com")
    assert prefilter(candidate) is False


def test_prefilter_invalid_source():
    candidate = _build_candidate(source="unknown")
    assert prefilter(candidate) is False


def test_prefilter_batch():
    candidates = [
        _build_candidate(),
        _build_candidate(title="short"),
        _build_github_candidate(url="https://example.com/3"),
    ]
    filtered = prefilter_batch(candidates)
    assert len(filtered) == 2


def test_prefilter_github_quality_rules():
    candidate = _build_github_candidate()
    assert prefilter(candidate) is True

    outdated = _build_github_candidate(
        publish_date=datetime.now(timezone.utc) - timedelta(days=200)
    )
    assert prefilter(outdated) is False

    short_readme = _build_github_candidate(abstract="short")
    assert prefilter(short_readme) is False

    few_stars = _build_github_candidate(github_stars=1)
    assert prefilter(few_stars) is False


def _build_candidate(**overrides) -> RawCandidate:
    data = {
        "title": "AgentBench: Evaluating LLMs as Agents",
        "url": "https://arxiv.org/abs/2308.03688",
        "source": "arxiv",
        "abstract": "We present AgentBench, a benchmark for evaluating LLMs as agents with multiple tasks.",
        "authors": ["Author A"],
        "publish_date": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return RawCandidate(**data)


def _build_github_candidate(**overrides) -> RawCandidate:
    long_readme = "Benchmark README\n" * 50
    data = {
        "title": "open-source/benchmark",
        "url": "https://github.com/open-source/benchmark",
        "source": "github",
        "abstract": long_readme,
        "github_stars": 200,
        "github_url": "https://github.com/open-source/benchmark",
        "publish_date": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return RawCandidate(**data)
