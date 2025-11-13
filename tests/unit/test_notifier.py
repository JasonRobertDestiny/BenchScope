"""飞书通知测试"""
from __future__ import annotations

import pytest

from src.models import ScoredCandidate
from src.notifier.feishu_notifier import FeishuNotifier


def _candidate(total: float = 8.5) -> ScoredCandidate:
    return ScoredCandidate(
        title="High Priority Benchmark",
        url="https://example.com/1",
        source="arxiv",
        activity_score=9.0,
        reproducibility_score=9.0,
        license_score=9.0,
        novelty_score=8.0,
        relevance_score=8.5,
        reasoning="Excellent benchmark",
    )


@pytest.mark.asyncio
async def test_notifier_card_format(monkeypatch):
    notifier = FeishuNotifier(webhook_url="https://example.com/webhook")
    card = notifier._build_card([_candidate()])

    assert card["msg_type"] == "interactive"
    assert "🎯 BenchScope" in card["card"]["header"]["title"]["content"]
    assert len(card["card"]["elements"]) == 1
