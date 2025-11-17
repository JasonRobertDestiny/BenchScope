# Codex开发指令：Twitter采集器MVP实现

**任务**: 实现Twitter/X推文采集器，专注MGX场景（AI Agent/Coding Benchmark）
**开发时间**: 预计1-2天
**技术栈**: Python 3.11+ / Twitter API v2 / httpx
**参考PRD**: `.claude/specs/benchmark-intelligence-agent/PHASE6-TWITTER-MVP-PRD.md`

---

## 1. 项目背景

**当前BenchScope数据源**:
- ✅ arXiv (学术论文)
- ✅ GitHub (开源项目)
- ✅ HuggingFace (模型/数据集)
- ✅ HELM (评测榜单)
- ✅ TechEmpower (Web框架性能)
- ✅ DBEngines (数据库排名)

**Twitter采集器价值**:
- Twitter是AI/Agent领域讨论的重要平台
- 论文发布、项目发布常在Twitter首发
- 社区讨论能反映Benchmark的实际影响力

**MGX场景聚焦**:
- MGX (https://mgx.dev) - 多智能体协作框架
- 关注领域：AI Agent、代码生成、LLM评测、Benchmark

---

## 2. 核心任务清单

### Week 1 Day 1-2: 核心采集器实现

- [ ] 创建 `src/collectors/twitter_collector.py`
- [ ] 实现TwitterCollector类
- [ ] 实现Twitter API v2调用逻辑
- [ ] 实现关键词搜索
- [ ] 实现URL提取与分类
- [ ] 实现推文去重
- [ ] 实现互动数预筛选

### Week 1 Day 3: 集成与配置

- [ ] 集成到 `src/main.py`
- [ ] 更新 `config/sources.yaml`
- [ ] 更新 `src/config.py` (环境变量)
- [ ] 更新 `src/collectors/__init__.py`

### Week 1 Day 4: 测试

- [ ] 创建 `tests/test_twitter_collector.py`
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试（完整流程）

### Week 1 Day 5: 文档

- [ ] 更新 `.claude/CLAUDE.md`
- [ ] 创建测试报告
- [ ] 验收确认

---

## 3. 详细实现指南

### 3.1 文件结构

```
src/collectors/twitter_collector.py   # 新增
tests/test_twitter_collector.py       # 新增
config/sources.yaml                    # 修改
src/config.py                          # 修改
src/collectors/__init__.py             # 修改
src/main.py                            # 修改
```

### 3.2 创建 `src/collectors/twitter_collector.py`

<details>
<summary>完整代码实现（点击展开）</summary>

```python
"""Twitter/X推文采集器 (MVP版本)

专注MGX场景：
- AI Agent Benchmark
- LLM Code Generation
- Multi-Agent Evaluation

功能:
1. 基于关键词搜索推文
2. 提取URL链接（arXiv/GitHub/HuggingFace）
3. 互动数预筛选（点赞/转发）
4. 转换为RawCandidate

限制:
- 仅Twitter API v2
- 仅搜索最近7天
- 不支持流式采集
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

from src.common import constants
from src.config import Settings, get_settings
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class TwitterCollector:
    """Twitter/X推文采集器

    使用Twitter API v2搜索最近推文，提取Benchmark相关信息。
    """

    def __init__(self, settings: Optional[Settings] = None):
        """初始化Twitter采集器

        Args:
            settings: 配置对象，默认使用get_settings()
        """
        self.settings = settings or get_settings()

        if not self.settings.twitter_bearer_token:
            raise ValueError("TWITTER_BEARER_TOKEN环境变量未配置")

        self.bearer_token = self.settings.twitter_bearer_token
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "User-Agent": "BenchScope/1.0",
            },
            timeout=httpx.Timeout(30.0),
        )

        # 加载配置
        self.config = self._load_config()
        logger.info("TwitterCollector初始化完成")

    def _load_config(self) -> Dict:
        """从配置文件加载Twitter采集配置"""
        # 从sources.yaml加载配置
        # 这里简化处理，直接返回默认配置
        return {
            "lookback_days": 7,
            "max_results_per_query": 100,
            "tier1_queries": [
                "AI agent benchmark",
                "LLM code generation",
                "multi-agent evaluation",
                "coding benchmark",
                "agent framework",
            ],
            "tier2_queries": [
                "HumanEval",
                "MBPP benchmark",
                "SWE-bench",
                "agent leaderboard",
                "LLM evaluation",
            ],
            "min_likes": 10,
            "min_retweets": 5,
            "must_have_url": True,
            "language": "en",
            "rate_limit_delay": 2.0,
        }

    async def collect(self) -> List[RawCandidate]:
        """采集Twitter推文并转换为候选项

        Returns:
            RawCandidate列表
        """
        logger.info("开始Twitter采集...")

        all_tweets = []
        queries = self.config["tier1_queries"] + self.config["tier2_queries"]

        for idx, query in enumerate(queries, 1):
            logger.info(f"搜索关键词 [{idx}/{len(queries)}]: {query}")

            try:
                tweets = await self._search_tweets(query)
                all_tweets.extend(tweets)
                logger.info(f"  找到 {len(tweets)} 条推文")

                # 速率限制延迟
                if idx < len(queries):
                    await asyncio.sleep(self.config["rate_limit_delay"])

            except Exception as e:
                logger.error(f"搜索失败 ({query}): {e}")
                continue

        # 去重
        unique_tweets = self._deduplicate(all_tweets)
        logger.info(f"去重后: {len(unique_tweets)} 条推文")

        # 预筛选
        filtered = self._prefilter(unique_tweets)
        logger.info(f"预筛选后: {len(filtered)} 条推文")

        # 转换为RawCandidate
        candidates = []
        for tweet in filtered:
            try:
                candidate = self._to_candidate(tweet)
                candidates.append(candidate)
            except Exception as e:
                logger.warning(f"转换失败 (推文ID {tweet.get('id')}): {e}")

        logger.info(f"✓ Twitter采集完成: {len(candidates)} 条候选")
        return candidates

    async def _search_tweets(self, query: str) -> List[Dict]:
        """调用Twitter API v2搜索推文

        Args:
            query: 搜索关键词

        Returns:
            推文列表
        """
        # 计算时间窗口
        start_time = (
            datetime.utcnow() - timedelta(days=self.config["lookback_days"])
        ).isoformat() + "Z"

        # API参数
        params = {
            "query": f"{query} lang:{self.config['language']} -is:retweet",
            "max_results": min(self.config["max_results_per_query"], 100),
            "start_time": start_time,
            "tweet.fields": "created_at,public_metrics,entities,author_id",
            "expansions": "author_id",
            "user.fields": "username,public_metrics",
        }

        try:
            response = await self.client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params=params,
            )
            response.raise_for_status()

            data = response.json()

            # 提取推文和作者信息
            tweets = data.get("data", [])
            includes = data.get("includes", {})
            users = {u["id"]: u for u in includes.get("users", [])}

            # 合并作者信息到推文
            for tweet in tweets:
                author_id = tweet.get("author_id")
                if author_id and author_id in users:
                    tweet["author"] = users[author_id]

            return tweets

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Twitter API限流 (429)，请降低请求频率")
            else:
                logger.error(f"Twitter API错误: {e.response.status_code}")
            return []

    def _deduplicate(self, tweets: List[Dict]) -> List[Dict]:
        """去重推文（基于推文ID）

        Args:
            tweets: 推文列表

        Returns:
            去重后的推文列表
        """
        seen = set()
        unique = []

        for tweet in tweets:
            tweet_id = tweet.get("id")
            if tweet_id and tweet_id not in seen:
                seen.add(tweet_id)
                unique.append(tweet)

        return unique

    def _prefilter(self, tweets: List[Dict]) -> List[Dict]:
        """预筛选推文（互动数、URL存在性）

        Args:
            tweets: 推文列表

        Returns:
            筛选后的推文列表
        """
        filtered = []

        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})

            # 检查互动数
            if metrics.get("like_count", 0) < self.config["min_likes"]:
                continue
            if metrics.get("retweet_count", 0) < self.config["min_retweets"]:
                continue

            # 检查URL
            if self.config["must_have_url"]:
                urls = tweet.get("entities", {}).get("urls", [])
                if not urls:
                    continue

            filtered.append(tweet)

        return filtered

    def _to_candidate(self, tweet: Dict) -> RawCandidate:
        """转换推文为RawCandidate

        Args:
            tweet: Twitter推文对象

        Returns:
            RawCandidate实例
        """
        # 提取URL
        urls = tweet.get("entities", {}).get("urls", [])
        primary_url = urls[0].get("expanded_url") if urls else None

        # 分类URL
        source = "twitter"
        paper_url = None
        github_url = None

        if primary_url:
            if self._is_arxiv_url(primary_url):
                source = "arxiv"
                paper_url = primary_url
            elif self._is_github_url(primary_url):
                source = "github"
                github_url = primary_url
            elif self._is_huggingface_url(primary_url):
                source = "huggingface"

        # 提取标题（推文前100字符）
        text = tweet.get("text", "")
        title = self._extract_title(text)

        # 清理推文文本（移除URL）
        abstract = self._clean_text(text, urls)

        return RawCandidate(
            title=title,
            url=primary_url or "",
            source=source,
            abstract=abstract,
            authors=None,
            publish_date=tweet.get("created_at"),
            github_stars=tweet["public_metrics"].get("like_count"),
            paper_url=paper_url,
            github_url=github_url,
            raw_metadata={
                "tweet_id": tweet["id"],
                "retweets": tweet["public_metrics"].get("retweet_count", 0),
                "replies": tweet["public_metrics"].get("reply_count", 0),
                "quotes": tweet["public_metrics"].get("quote_count", 0),
                "author_username": tweet.get("author", {}).get("username", ""),
                "author_followers": tweet.get("author", {}).get("public_metrics", {}).get(
                    "followers_count", 0
                ),
                "tweet_url": f"https://twitter.com/i/web/status/{tweet['id']}",
            },
        )

    def _is_arxiv_url(self, url: str) -> bool:
        """检查是否为arXiv URL"""
        return "arxiv.org/abs/" in url or "arxiv.org/pdf/" in url

    def _is_github_url(self, url: str) -> bool:
        """检查是否为GitHub仓库URL"""
        if "github.com/" not in url:
            return False
        # 排除文件链接（/blob/, /tree/, /issues/等）
        excluded = ["/blob/", "/tree/", "/issues/", "/pull/", "/commit/"]
        return not any(ex in url for ex in excluded)

    def _is_huggingface_url(self, url: str) -> bool:
        """检查是否为HuggingFace URL"""
        return "huggingface.co/" in url

    def _extract_title(self, text: str) -> str:
        """从推文文本提取标题（前100字符）"""
        # 移除换行符
        title = text.replace("\n", " ").strip()
        # 截断到100字符
        if len(title) > 100:
            title = title[:97] + "..."
        return title

    def _clean_text(self, text: str, urls: List[Dict]) -> str:
        """清理推文文本（移除URL）

        Args:
            text: 原始推文文本
            urls: URL实体列表

        Returns:
            清理后的文本
        """
        cleaned = text

        # 移除所有URL
        for url_obj in urls:
            url = url_obj.get("url", "")
            if url:
                cleaned = cleaned.replace(url, "")

        # 移除多余空白
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口（关闭HTTP客户端）"""
        await self.client.aclose()
```

</details>

### 3.3 更新 `src/config.py`

在Settings类中添加Twitter配置：

```python
# 在Settings类中添加（约第40行）

# ============ Twitter/X API ============
twitter_bearer_token: Optional[str] = Field(
    default=None, alias="TWITTER_BEARER_TOKEN"
)
```

### 3.4 更新 `src/collectors/__init__.py`

```python
# 在__init__.py中添加导入

from src.collectors.twitter_collector import TwitterCollector

__all__ = [
    "ArxivCollector",
    "GitHubCollector",
    "HelmCollector",
    "HuggingFaceCollector",
    "TechEmpowerCollector",
    "DBEnginesCollector",
    "TwitterCollector",  # 新增
]
```

### 3.5 集成到 `src/main.py`

在main()函数的Step 1中添加TwitterCollector：

```python
# 在main()函数中（约第38行）

# Step 1: 数据采集
logger.info("[1/6] 数据采集...")
collectors = [
    ArxivCollector(settings=settings),
    HelmCollector(settings=settings),
    GitHubCollector(settings=settings),
    HuggingFaceCollector(settings=settings),
    TechEmpowerCollector(settings=settings),
    DBEnginesCollector(settings=settings),
    TwitterCollector(settings=settings),  # 新增
]
```

### 3.6 更新 `config/sources.yaml`

```yaml
# 在文件末尾添加

twitter:
  enabled: true
  lookback_days: 7  # 搜索最近7天推文
  max_results_per_query: 100  # 每个关键词最多100条
  search_queries:
    tier1:  # 核心关键词（必须包含）
      - "AI agent benchmark"
      - "LLM code generation"
      - "multi-agent evaluation"
      - "coding benchmark"
      - "agent framework"
    tier2:  # 扩展关键词（提升覆盖面）
      - "HumanEval"
      - "MBPP benchmark"
      - "SWE-bench"
      - "agent leaderboard"
      - "LLM evaluation"
      - "code interpreter"
  filters:
    min_likes: 10       # 最少10个赞
    min_retweets: 5     # 最少5次转发
    must_have_url: true # 必须包含URL链接
    language: "en"      # 仅英文
  rate_limit_delay: 2.0 # 请求间隔（秒）
```

---

## 4. 单元测试

创建 `tests/test_twitter_collector.py`：

<details>
<summary>完整测试代码（点击展开）</summary>

```python
"""Twitter采集器单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.collectors.twitter_collector import TwitterCollector
from src.models import RawCandidate


@pytest.fixture
def mock_settings():
    """Mock Settings对象"""
    settings = MagicMock()
    settings.twitter_bearer_token = "test_bearer_token"
    return settings


@pytest.fixture
def twitter_collector(mock_settings):
    """创建TwitterCollector实例"""
    return TwitterCollector(settings=mock_settings)


@pytest.fixture
def mock_tweet_response():
    """Mock Twitter API响应"""
    return {
        "data": [
            {
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
            }
        ],
        "includes": {
            "users": [
                {
                    "id": "user123",
                    "username": "ai_researcher",
                    "public_metrics": {
                        "followers_count": 10000,
                    },
                }
            ]
        },
    }


class TestTwitterCollector:
    """TwitterCollector测试套件"""

    def test_init_with_bearer_token(self, mock_settings):
        """测试初始化（有Bearer Token）"""
        collector = TwitterCollector(settings=mock_settings)
        assert collector.bearer_token == "test_bearer_token"

    def test_init_without_bearer_token(self):
        """测试初始化（无Bearer Token）"""
        settings = MagicMock()
        settings.twitter_bearer_token = None

        with pytest.raises(ValueError, match="TWITTER_BEARER_TOKEN环境变量未配置"):
            TwitterCollector(settings=settings)

    def test_is_arxiv_url(self, twitter_collector):
        """测试arXiv URL识别"""
        assert twitter_collector._is_arxiv_url("https://arxiv.org/abs/2401.12345")
        assert twitter_collector._is_arxiv_url("https://arxiv.org/pdf/2401.12345.pdf")
        assert not twitter_collector._is_arxiv_url("https://github.com/openai/gpt-4")

    def test_is_github_url(self, twitter_collector):
        """测试GitHub URL识别"""
        assert twitter_collector._is_github_url("https://github.com/openai/human-eval")
        assert not twitter_collector._is_github_url("https://github.com/openai/human-eval/blob/main/README.md")
        assert not twitter_collector._is_github_url("https://arxiv.org/abs/2401.12345")

    def test_is_huggingface_url(self, twitter_collector):
        """测试HuggingFace URL识别"""
        assert twitter_collector._is_huggingface_url("https://huggingface.co/datasets/openai/humaneval")
        assert not twitter_collector._is_huggingface_url("https://github.com/openai/human-eval")

    def test_extract_title(self, twitter_collector):
        """测试标题提取"""
        text = "This is a very long tweet that exceeds 100 characters and should be truncated with ellipsis at the end"
        title = twitter_collector._extract_title(text)
        assert len(title) <= 100
        assert title.endswith("...")

    def test_clean_text(self, twitter_collector):
        """测试文本清理"""
        text = "Check out this paper! https://t.co/abc123"
        urls = [{"url": "https://t.co/abc123"}]
        cleaned = twitter_collector._clean_text(text, urls)
        assert "https://t.co/abc123" not in cleaned
        assert "Check out this paper!" in cleaned

    def test_deduplicate(self, twitter_collector):
        """测试推文去重"""
        tweets = [
            {"id": "1", "text": "Tweet 1"},
            {"id": "2", "text": "Tweet 2"},
            {"id": "1", "text": "Tweet 1 duplicate"},  # 重复
        ]
        unique = twitter_collector._deduplicate(tweets)
        assert len(unique) == 2
        assert unique[0]["id"] == "1"
        assert unique[1]["id"] == "2"

    def test_prefilter_likes(self, twitter_collector):
        """测试预筛选（点赞数）"""
        tweets = [
            {"id": "1", "public_metrics": {"like_count": 50, "retweet_count": 10}, "entities": {"urls": [{"url": "https://example.com"}]}},
            {"id": "2", "public_metrics": {"like_count": 5, "retweet_count": 10}, "entities": {"urls": [{"url": "https://example.com"}]}},  # 点赞数不足
        ]
        filtered = twitter_collector._prefilter(tweets)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_prefilter_retweets(self, twitter_collector):
        """测试预筛选（转发数）"""
        tweets = [
            {"id": "1", "public_metrics": {"like_count": 50, "retweet_count": 10}, "entities": {"urls": [{"url": "https://example.com"}]}},
            {"id": "2", "public_metrics": {"like_count": 50, "retweet_count": 2}, "entities": {"urls": [{"url": "https://example.com"}]}},  # 转发数不足
        ]
        filtered = twitter_collector._prefilter(tweets)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_prefilter_url_required(self, twitter_collector):
        """测试预筛选（必须包含URL）"""
        tweets = [
            {"id": "1", "public_metrics": {"like_count": 50, "retweet_count": 10}, "entities": {"urls": [{"url": "https://example.com"}]}},
            {"id": "2", "public_metrics": {"like_count": 50, "retweet_count": 10}, "entities": {}},  # 无URL
        ]
        filtered = twitter_collector._prefilter(tweets)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_to_candidate_arxiv(self, twitter_collector):
        """测试转换为RawCandidate（arXiv）"""
        tweet = {
            "id": "1234567890",
            "text": "Check out this paper! https://t.co/abc123",
            "created_at": "2025-11-17T10:00:00.000Z",
            "public_metrics": {"like_count": 50, "retweet_count": 10, "reply_count": 5, "quote_count": 2},
            "entities": {
                "urls": [{"url": "https://t.co/abc123", "expanded_url": "https://arxiv.org/abs/2401.12345"}]
            },
            "author": {"username": "ai_researcher", "public_metrics": {"followers_count": 10000}},
        }

        candidate = twitter_collector._to_candidate(tweet)
        assert isinstance(candidate, RawCandidate)
        assert candidate.source == "arxiv"
        assert candidate.paper_url == "https://arxiv.org/abs/2401.12345"
        assert candidate.raw_metadata["tweet_id"] == "1234567890"
        assert candidate.raw_metadata["author_username"] == "ai_researcher"

    def test_to_candidate_github(self, twitter_collector):
        """测试转换为RawCandidate（GitHub）"""
        tweet = {
            "id": "1234567890",
            "text": "Awesome benchmark repo! https://t.co/xyz789",
            "created_at": "2025-11-17T10:00:00.000Z",
            "public_metrics": {"like_count": 50, "retweet_count": 10, "reply_count": 5, "quote_count": 2},
            "entities": {
                "urls": [{"url": "https://t.co/xyz789", "expanded_url": "https://github.com/openai/human-eval"}]
            },
            "author": {"username": "dev_user", "public_metrics": {"followers_count": 5000}},
        }

        candidate = twitter_collector._to_candidate(tweet)
        assert candidate.source == "github"
        assert candidate.github_url == "https://github.com/openai/human-eval"

    @pytest.mark.asyncio
    async def test_search_tweets_success(self, twitter_collector, mock_tweet_response):
        """测试搜索推文（成功）"""
        with patch.object(twitter_collector.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_tweet_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            tweets = await twitter_collector._search_tweets("AI agent benchmark")

            assert len(tweets) == 1
            assert tweets[0]["id"] == "1234567890"
            assert tweets[0]["author"]["username"] == "ai_researcher"

    @pytest.mark.asyncio
    async def test_collect_full_flow(self, twitter_collector, mock_tweet_response):
        """测试完整采集流程"""
        with patch.object(twitter_collector.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_tweet_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            candidates = await twitter_collector.collect()

            assert len(candidates) > 0
            assert all(isinstance(c, RawCandidate) for c in candidates)
```

</details>

---

## 5. 验证测试

### 5.1 运行单元测试

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
source .venv/bin/activate

# 运行Twitter采集器测试
python -m pytest tests/test_twitter_collector.py -v

# 预期结果: 全部PASSED
```

### 5.2 运行完整流程

```bash
# 运行主流程（包含Twitter采集）
python -m src.main
```

**预期日志**:
```
[1/6] 数据采集...
  ✓ ArxivCollector: XX条
  ✓ HelmCollector: XX条
  ✓ GitHubCollector: XX条
  ✓ HuggingFaceCollector: XX条
  ✓ TechEmpowerCollector: XX条
  ✓ DBEnginesCollector: XX条
  ✓ TwitterCollector: XX条  ← 新增
✓ 采集完成: XX条
```

---

## 6. 常见问题处理

### Q1: Twitter API 429错误
```
ERROR: Twitter API限流 (429)
```

**解决**:
- 增加 `rate_limit_delay` 到3-5秒
- 减少关键词数量
- 检查Twitter API配额（450次/15分钟）

### Q2: Bearer Token无效
```
ERROR: 401 Unauthorized
```

**解决**:
- 检查 `.env.local` 中 `TWITTER_BEARER_TOKEN`
- 在Twitter Developer Portal重新生成Token

### Q3: 无推文返回
```
✓ TwitterCollector: 0条
```

**排查**:
1. 检查关键词是否太特定（尝试更通用的关键词）
2. 检查时间窗口（7天可能太短）
3. 检查预筛选阈值（likes/retweets可能太高）
4. 查看详细日志（是否有API错误）

---

## 7. 验收标准

### 功能验收

- [ ] TwitterCollector成功初始化
- [ ] 能搜索Tier 1关键词
- [ ] 正确提取arXiv/GitHub/HuggingFace URL
- [ ] 互动数预筛选有效
- [ ] 推文去重正常
- [ ] 转换为RawCandidate正确
- [ ] 集成到主流程无冲突
- [ ] 单元测试覆盖率 ≥ 80%

### 数据质量验收

**预期1周采集量**:
- 采集推文: 100-200条
- 预筛选通过: 20-80条
- arXiv链接: 6-24条
- GitHub链接: 8-32条

### 性能验收

- 单次采集耗时 < 60秒
- 不触发API限流
- 内存占用 < 200MB

---

## 8. 完成检查清单

- [ ] 创建 `src/collectors/twitter_collector.py`
- [ ] 更新 `src/config.py`
- [ ] 更新 `src/collectors/__init__.py`
- [ ] 集成到 `src/main.py`
- [ ] 更新 `config/sources.yaml`
- [ ] 创建 `tests/test_twitter_collector.py`
- [ ] 运行单元测试全部通过
- [ ] 运行完整流程测试
- [ ] 生成测试报告
- [ ] 更新项目文档

---

**开发时间**: 预计1-2天
**开发者**: Codex
**监督**: Claude Code
**文档版本**: v1.0
