"""TwitterCollector 单元测试。

覆盖范围：
1. 初始化与配置加载（Bearer Token / YAML 配置）
2. URL 类型识别与标题/文本清洗
3. 推文去重与预筛选规则
4. 推文到 RawCandidate 的转换
5. collect 主流程在 mock 场景下的行为
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.collectors.twitter_collector import TwitterCollector
from src.models import RawCandidate


@pytest.fixture
def mock_twitter_config() -> SimpleNamespace:
    """构造 Twitter 数据源配置的简化版本。"""

    return SimpleNamespace(
        enabled=True,
        lookback_days=7,
        max_results_per_query=100,
        tier1_queries=["AI agent benchmark"],
        tier2_queries=["HumanEval"],
        min_likes=10,
        min_retweets=5,
        must_have_url=True,
        language="en",
        rate_limit_delay=0.0,
    )


@pytest.fixture
def mock_settings(mock_twitter_config: SimpleNamespace) -> MagicMock:
    """构造 Settings 的简单 mock, 仅包含 TwitterCollector 需要的字段。"""

    settings = MagicMock()
    settings.sources = SimpleNamespace(twitter=mock_twitter_config)
    settings.twitter_bearer_token = "test_bearer_token"
    return settings


@pytest.fixture
def twitter_collector(mock_settings: MagicMock) -> TwitterCollector:
    """创建 TwitterCollector 实例。"""

    return TwitterCollector(settings=mock_settings)


@pytest.fixture
def mock_tweet() -> dict:
    """构造一条包含 arXiv 链接的示例推文。"""

    return {
        "id": "1234567890",
        "text": "Check out this amazing AI agent benchmark! https://t.co/abc123",
        "created_at": "2025-11-17T10:00:00.000Z",
        "author_id": "user123",
        "public_metrics": {
            "like_count": 50,
            "retweet_count": 10,
            "reply_count": 5,
            "quote_count": 2,
        },
        "entities": {
            "urls": [
                {
                    "url": "https://t.co/abc123",
                    "expanded_url": "https://arxiv.org/abs/2401.12345",
                }
            ]
        },
        "author": {
            "username": "ai_researcher",
            "public_metrics": {
                "followers_count": 10000,
            },
        },
    }


class TestTwitterCollector:
    """TwitterCollector 行为测试。"""

    def test_init_with_bearer_token(self, mock_settings: MagicMock) -> None:
        """当配置了 Bearer Token 时应正确初始化。"""

        collector = TwitterCollector(settings=mock_settings)
        assert collector.bearer_token == "test_bearer_token"
        assert collector.enabled is True

    def test_init_without_bearer_token_raises(self, mock_twitter_config: SimpleNamespace) -> None:
        """启用 Twitter 源但未配置 Token 时应抛出异常。"""

        settings = MagicMock()
        settings.sources = SimpleNamespace(twitter=mock_twitter_config)
        settings.twitter_bearer_token = None

        with pytest.raises(ValueError, match="TWITTER_BEARER_TOKEN环境变量未配置"):
            TwitterCollector(settings=settings)

    def test_is_arxiv_url(self, twitter_collector: TwitterCollector) -> None:
        """arXiv URL 识别应准确。"""

        assert twitter_collector._is_arxiv_url("https://arxiv.org/abs/2401.12345")
        assert twitter_collector._is_arxiv_url("https://arxiv.org/pdf/2401.12345.pdf")
        assert not twitter_collector._is_arxiv_url("https://github.com/openai/gpt-4")

    def test_is_github_url(self, twitter_collector: TwitterCollector) -> None:
        """GitHub URL 识别应能排除非仓库主页链接。"""

        assert twitter_collector._is_github_url("https://github.com/openai/human-eval")
        # 带 blob 的文件链接
        assert not twitter_collector._is_github_url(
            "https://github.com/openai/human-eval/blob/main/README.md"
        )
        # 非 GitHub 域名
        assert not twitter_collector._is_github_url("https://arxiv.org/abs/2401.12345")

    def test_is_huggingface_url(self, twitter_collector: TwitterCollector) -> None:
        """HuggingFace URL 识别应准确。"""

        assert twitter_collector._is_huggingface_url(
            "https://huggingface.co/datasets/openai/humaneval"
        )
        assert not twitter_collector._is_huggingface_url(
            "https://github.com/openai/human-eval"
        )

    def test_extract_title_truncates_long_text(self, twitter_collector: TwitterCollector) -> None:
        """长文本标题应被截断到 100 字符以内并添加省略号。"""

        text = (
            "This is a very long tweet that exceeds 100 characters and should be "
            "truncated with ellipsis at the end of the string"
        )
        title = twitter_collector._extract_title(text)
        assert len(title) <= 100
        assert title.endswith("...")

    def test_clean_text_removes_urls(self, twitter_collector: TwitterCollector) -> None:
        """文本清理应移除推文中的短链接。"""

        text = "Check out this paper! https://t.co/abc123"
        urls = [{"url": "https://t.co/abc123"}]
        cleaned = twitter_collector._clean_text(text, urls)
        assert "https://t.co/abc123" not in cleaned
        assert "Check out this paper!" in cleaned

    def test_deduplicate_by_id(self, twitter_collector: TwitterCollector) -> None:
        """去重逻辑应基于推文 ID。"""

        tweets = [
            {"id": "1", "text": "Tweet 1"},
            {"id": "2", "text": "Tweet 2"},
            {"id": "1", "text": "Tweet 1 duplicate"},
        ]
        unique = twitter_collector._deduplicate(tweets)
        assert len(unique) == 2
        assert {t["id"] for t in unique} == {"1", "2"}

    def test_prefilter_applies_metrics_and_url_rules(
        self,
        twitter_collector: TwitterCollector,
    ) -> None:
        """预筛选应同时检查互动数与 URL 存在性。"""

        base_metrics = {
            "like_count": twitter_collector.min_likes,
            "retweet_count": twitter_collector.min_retweets,
        }
        ok_tweet = {
            "id": "1",
            "public_metrics": base_metrics,
            "entities": {"urls": [{"url": "https://example.com"}]},
        }
        low_like_tweet = {
            "id": "2",
            "public_metrics": {
                "like_count": twitter_collector.min_likes - 1,
                "retweet_count": twitter_collector.min_retweets,
            },
            "entities": {"urls": [{"url": "https://example.com"}]},
        }
        no_url_tweet = {
            "id": "3",
            "public_metrics": base_metrics,
            "entities": {},
        }

        filtered = twitter_collector._prefilter(
            [ok_tweet, low_like_tweet, no_url_tweet]
        )
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_to_candidate_arxiv(
        self,
        twitter_collector: TwitterCollector,
        mock_tweet: dict,
    ) -> None:
        """包含 arXiv 链接的推文应被识别为 arxiv 来源。"""

        candidate = twitter_collector._to_candidate(mock_tweet)
        assert isinstance(candidate, RawCandidate)
        assert candidate.source == "arxiv"
        assert candidate.paper_url == "https://arxiv.org/abs/2401.12345"
        assert candidate.github_url is None
        assert candidate.raw_metadata["tweet_id"] == "1234567890"
        assert candidate.raw_metadata["author_username"] == "ai_researcher"

    @pytest.mark.asyncio
    async def test_collect_returns_candidates(
        self,
        mock_settings: MagicMock,
        mock_tweet: dict,
    ) -> None:
        """在 mock 场景下, collect 应返回 RawCandidate 列表。"""

        collector = TwitterCollector(settings=mock_settings)

        # 使用 AsyncMock 避免实际调用 Twitter API
        collector._search_tweets = AsyncMock(return_value=[mock_tweet])  # type: ignore[method-assign]

        candidates = await collector.collect()

        assert len(candidates) == 1
        assert isinstance(candidates[0], RawCandidate)
