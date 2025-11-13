# BenchScope Phase 2 开发指令 - 详细上下文版

## 当前状态总结

### 已完成（Phase 1 MVP）
- ✅ **4个数据采集器**: arXiv, GitHub, PwC, HuggingFace
- ✅ **数据模型**: `src/models.py` (RawCandidate, ScoredCandidate等)
- ✅ **配置管理**: `src/config.py` (Settings, get_settings)
- ✅ **单元测试**: 5/5通过
- ✅ **环境配置**: uv + Redis + .env.local
- ✅ **真实数据采集**: 成功采集到1条arXiv论文（见`docs/samples/collected_data.json`）

### 待开发（Phase 2核心功能）
- ❌ **规则预筛选**: `src/prefilter/rule_filter.py`
- ❌ **LLM评分引擎**: `src/scorer/llm_scorer.py`
- ❌ **飞书存储**: `src/storage/feishu_storage.py`
- ❌ **SQLite备份**: `src/storage/sqlite_fallback.py`
- ❌ **存储管理器**: `src/storage/storage_manager.py`
- ❌ **飞书通知**: `src/notifier/feishu_notifier.py`
- ❌ **主流程更新**: `src/main.py` (当前只有采集，需要加入评分+存储+通知)

### 为什么飞书没有数据？
**原因**: 当前`src/main.py`只实现了采集，还没有实现：
1. 规则预筛选 → 过滤低质量候选
2. LLM评分 → 5维度打分
3. 飞书存储 → 写入多维表格
4. 飞书通知 → Webhook推送

**需要做的事**: 实现上述4个模块，然后在`src/main.py`串联起来。

---

## 开发环境确认

### 环境变量（已配置）
所有必需的环境变量已在`.env.local`配置：
```bash
# OpenAI API
OPENAI_API_KEY=sk-hJOSKKNm1TJTRpgrUIrOSA0YlAKJxDMV9JMxSp91qxzHQuej
OPENAI_BASE_URL=https://newapi.deepwisdom.ai/v1
OPENAI_MODEL=gpt-4o

# 飞书开放平台
FEISHU_APP_ID=cli_a99fe5757cbc101c
FEISHU_APP_SECRET=O3MyjhEzvfEYw0TM8y1zsbb8NWihxGQe

# 飞书多维表格
FEISHU_BITABLE_APP_TOKEN=NJkswt2hKi1pW0kCsdSccIoanmf
FEISHU_BITABLE_TABLE_ID=tbl53JhkakSOP4wo

# 飞书机器人Webhook
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/b9e072c7-f2a2-422c-81ed-0043eb437067

# HuggingFace API
HUGGINGFACE_TOKEN=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

# Redis缓存
REDIS_URL=redis://localhost:6379

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs/
```

### 依赖安装（已完成）
```bash
# 使用uv安装（6秒完成）
source .venv/bin/activate
uv pip install -r requirements.txt

# 验证环境
python scripts/verify_setup.py  # 应该全部通过
```

### 真实测试数据（已采集）
位置: `docs/samples/collected_data.json`
```json
{
  "title": "Where Do LLMs Still Struggle? An In-Depth Analysis of Code Generation Benchmarks",
  "url": "http://arxiv.org/abs/2511.04355v1",
  "source": "arxiv",
  "abstract": "Large Language Models (LLMs) have achieved remarkable success...",
  "authors": ["Amir Molzam Sharifloo", "Maedeh Heydari", ...],
  "publish_date": "2025-11-06 13:38:03+00:00"
}
```

这条数据是**高质量候选**，应该通过预筛选并获得7.5-8.5/10的评分。

---

## Phase 2 开发任务详解

### Task 1: 规则预筛选引擎（第一优先级）

**文件**: `src/prefilter/rule_filter.py`

**功能**: 过滤掉50%低质量候选，减少LLM调用成本

**完整实现代码**:
```python
"""规则预筛选引擎"""
from __future__ import annotations

import logging
from typing import List

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


def prefilter(candidate: RawCandidate) -> bool:
    """
    预筛选规则（过滤低质量候选）:
    1. 标题长度 >= 10字符
    2. 摘要非空
    3. URL有效
    4. 来源在白名单 (arxiv/github/pwc/huggingface)
    5. 关键词匹配（至少1个benchmark相关词）

    返回: True=保留, False=过滤
    """
    # 规则1: 标题长度检查
    if not candidate.title or len(candidate.title.strip()) < 10:
        logger.debug(f"过滤: 标题过短 - {candidate.title}")
        return False

    # 规则2: 摘要检查
    if not candidate.abstract or len(candidate.abstract.strip()) < 20:
        logger.debug(f"过滤: 摘要过短 - {candidate.title}")
        return False

    # 规则3: URL检查
    if not candidate.url or not candidate.url.startswith(('http://', 'https://')):
        logger.debug(f"过滤: URL无效 - {candidate.url}")
        return False

    # 规则4: 来源白名单
    valid_sources = ['arxiv', 'github', 'pwc', 'huggingface']
    if candidate.source not in valid_sources:
        logger.debug(f"过滤: 来源不在白名单 - {candidate.source}")
        return False

    # 规则5: 关键词匹配
    text = f"{candidate.title} {candidate.abstract}".lower()
    matched_keywords = [kw for kw in constants.BENCHMARK_KEYWORDS if kw in text]

    if not matched_keywords:
        logger.debug(f"过滤: 无关键词匹配 - {candidate.title}")
        return False

    logger.debug(f"通过: {candidate.title[:50]}... (匹配关键词: {matched_keywords[:3]})")
    return True


def prefilter_batch(candidates: List[RawCandidate]) -> List[RawCandidate]:
    """批量预筛选候选"""
    if not candidates:
        return []

    filtered = [c for c in candidates if prefilter(c)]
    filter_rate = 100 * (1 - len(filtered) / len(candidates)) if candidates else 0

    logger.info(f"预筛选完成,输入{len(candidates)}条,输出{len(filtered)}条,过滤率{filter_rate:.1f}%")

    return filtered
```

**同时创建**: `src/common/constants.py`
```python
"""全局常量配置"""

# 预筛选关键词
BENCHMARK_KEYWORDS = [
    "benchmark",
    "evaluation",
    "leaderboard",
    "dataset",
    "agent",
    "coding",
    "reasoning",
    "tool use",
    "multi-agent",
    "code generation",
]

# LLM配置
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_RETRIES = 3
LLM_TIMEOUT_SECONDS = 30

# Redis缓存
REDIS_TTL_DAYS = 7
REDIS_KEY_PREFIX = "benchscope:"

# 飞书API
FEISHU_BATCH_SIZE = 20
FEISHU_RATE_LIMIT_DELAY = 0.6  # 秒

# 评分阈值
MIN_TOTAL_SCORE = 6.0  # 低于6分不入库
```

**单元测试**: `tests/unit/test_prefilter.py`
```python
"""规则预筛选测试"""
import pytest
from datetime import datetime, timezone

from src.models import RawCandidate
from src.prefilter.rule_filter import prefilter, prefilter_batch


def test_prefilter_valid_candidate():
    """测试有效候选通过"""
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
    """测试标题过短被过滤"""
    candidate = RawCandidate(
        title="Test",
        url="https://example.com",
        source="arxiv",
        abstract="This is a long enough abstract for testing purposes.",
        authors=[],
        publish_date=None,
    )
    assert prefilter(candidate) is False


def test_prefilter_no_abstract():
    """测试无摘要被过滤"""
    candidate = RawCandidate(
        title="Long enough title here",
        url="https://example.com",
        source="arxiv",
        abstract="",
        authors=[],
        publish_date=None,
    )
    assert prefilter(candidate) is False


def test_prefilter_no_keywords():
    """测试无关键词被过滤"""
    candidate = RawCandidate(
        title="Random paper about nothing related",
        url="https://example.com",
        source="arxiv",
        abstract="This paper discusses completely unrelated topics that have nothing to do with benchmarks.",
        authors=[],
        publish_date=None,
    )
    assert prefilter(candidate) is False


def test_prefilter_invalid_url():
    """测试无效URL被过滤"""
    candidate = RawCandidate(
        title="Benchmark paper with invalid URL",
        url="not-a-url",
        source="arxiv",
        abstract="This is a benchmark paper with long abstract.",
        authors=[],
        publish_date=None,
    )
    assert prefilter(candidate) is False


def test_prefilter_invalid_source():
    """测试无效来源被过滤"""
    candidate = RawCandidate(
        title="Benchmark paper from unknown source",
        url="https://example.com",
        source="unknown",
        abstract="This is a benchmark paper from unknown source.",
        authors=[],
        publish_date=None,
    )
    assert prefilter(candidate) is False


def test_prefilter_batch():
    """测试批量预筛选"""
    candidates = [
        RawCandidate(
            title="Valid Benchmark Paper",
            url="https://example.com",
            source="arxiv",
            abstract="A benchmark evaluation paper with sufficient content.",
            authors=[],
            publish_date=None,
        ),
        RawCandidate(
            title="Short",
            url="https://example.com",
            source="arxiv",
            abstract="Valid abstract",
            authors=[],
            publish_date=None,
        ),
        RawCandidate(
            title="Another Valid Benchmark",
            url="https://example.com",
            source="github",
            abstract="Dataset and evaluation benchmark with detailed description.",
            authors=[],
            publish_date=None,
        ),
    ]

    filtered = prefilter_batch(candidates)
    assert len(filtered) == 2  # 2个通过，1个被过滤
```

**验收标准**:
- [ ] `prefilter()`函数实现完成
- [ ] `constants.py`配置文件创建
- [ ] 单元测试覆盖所有规则分支
- [ ] 测试通过率100%
- [ ] 使用真实数据测试：`docs/samples/collected_data.json`应该通过

**测试命令**:
```bash
# 运行单元测试
pytest tests/unit/test_prefilter.py -v

# 手动测试真实数据
python << 'EOF'
import json
from src.models import RawCandidate
from src.prefilter.rule_filter import prefilter

with open('docs/samples/collected_data.json') as f:
    data = json.load(f)[0]

candidate = RawCandidate(
    title=data['title'],
    url=data['url'],
    source=data['source'],
    abstract=data['abstract'],
    authors=data['authors'],
    publish_date=None
)

result = prefilter(candidate)
print(f"预筛选结果: {'通过' if result else '被过滤'}")
print(f"标题: {candidate.title[:50]}...")
EOF
```

---

### Task 2: LLM评分引擎（第二优先级）

**文件**: `src/scorer/llm_scorer.py`

**功能**: 使用gpt-4o-mini对候选进行5维度评分

**完整实现代码**:
```python
"""LLM评分引擎"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)


class LLMScorer:
    """LLM评分引擎，使用Redis缓存"""

    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.openai.api_key,
            base_url=self.settings.openai.base_url,
        )
        self.redis_client: Optional[redis.Redis] = None

    async def __aenter__(self):
        # 初始化Redis连接
        try:
            self.redis_client = await redis.from_url(
                self.settings.redis_url,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败,将不使用缓存: {e}")
            self.redis_client = None
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis_client:
            await self.redis_client.aclose()

    def _cache_key(self, candidate: RawCandidate) -> str:
        """生成缓存key"""
        key_str = f"{candidate.title}:{candidate.url}"
        hash_val = hashlib.md5(key_str.encode()).hexdigest()
        return f"{constants.REDIS_KEY_PREFIX}score:{hash_val}"

    async def _get_cached_score(self, candidate: RawCandidate) -> Optional[Dict[str, Any]]:
        """从Redis获取缓存评分"""
        if not self.redis_client:
            return None

        try:
            cache_key = self._cache_key(candidate)
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"缓存命中: {candidate.title[:50]}...")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")

        return None

    async def _set_cached_score(self, candidate: RawCandidate, scores: Dict[str, Any]):
        """将评分写入Redis缓存"""
        if not self.redis_client:
            return

        try:
            cache_key = self._cache_key(candidate)
            await self.redis_client.setex(
                cache_key,
                constants.REDIS_TTL_DAYS * 86400,
                json.dumps(scores)
            )
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

    @retry(
        stop=stop_after_attempt(constants.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _call_llm(self, candidate: RawCandidate) -> Dict[str, Any]:
        """调用LLM进行评分"""
        prompt = self._build_prompt(candidate)

        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.settings.openai.model,
                messages=[
                    {"role": "system", "content": "你是AI Benchmark评估专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            ),
            timeout=constants.LLM_TIMEOUT_SECONDS
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # 验证必需字段
        required_fields = [
            "activity_score",
            "reproducibility_score",
            "license_score",
            "novelty_score",
            "relevance_score"
        ]

        for field in required_fields:
            if field not in result:
                raise ValueError(f"LLM响应缺少字段: {field}")
            # 确保分数在0-10范围内
            result[field] = max(0.0, min(10.0, float(result[field])))

        return result

    def _build_prompt(self, candidate: RawCandidate) -> str:
        """构建评分prompt"""
        github_info = ""
        if candidate.github_url:
            github_info = f"\nGitHub信息: {candidate.github_url}"
            if candidate.github_stars:
                github_info += f" ({candidate.github_stars} stars)"

        return f"""请对以下AI Benchmark候选进行评分(每项0-10分):

候选信息:
- 标题: {candidate.title}
- 来源: {candidate.source}
- URL: {candidate.url}
- 摘要: {candidate.abstract[:500]}...{github_info}

评分维度:
1. 活跃度 (activity_score): GitHub stars数量、更新频率
2. 可复现性 (reproducibility_score): 代码/数据/文档开源状态
3. 许可合规 (license_score): MIT/Apache/BSD优先，专有/未知许可扣分
4. 任务新颖性 (novelty_score): 是否有独特价值，避免与现有benchmark重复
5. MGX适配度 (relevance_score): 与多智能体/代码生成/工具使用的相关性

输出JSON格式:
{{
  "activity_score": 7.5,
  "reproducibility_score": 9.0,
  "license_score": 10.0,
  "novelty_score": 6.0,
  "relevance_score": 8.5,
  "reasoning": "简要说明评分依据（1-2句话）"
}}
"""

    async def score(self, candidate: RawCandidate) -> ScoredCandidate:
        """对单个候选评分"""
        # 1. 尝试从缓存获取
        cached_scores = await self._get_cached_score(candidate)

        if cached_scores:
            logger.info(f"使用缓存评分: {candidate.title[:50]}...")
            scores = cached_scores
        else:
            # 2. 调用LLM评分
            try:
                logger.info(f"LLM评分: {candidate.title[:50]}...")
                scores = await self._call_llm(candidate)

                # 3. 写入缓存
                await self._set_cached_score(candidate, scores)
            except Exception as e:
                logger.error(f"LLM评分失败,使用规则兜底: {e}")
                scores = self._fallback_score(candidate)

        # 4. 创建ScoredCandidate
        return ScoredCandidate(
            title=candidate.title,
            url=candidate.url,
            source=candidate.source,
            abstract=candidate.abstract,
            authors=candidate.authors,
            publish_date=candidate.publish_date,
            github_url=candidate.github_url,
            github_stars=candidate.github_stars,
            dataset_url=candidate.dataset_url,
            raw_metadata=candidate.raw_metadata,
            activity_score=scores["activity_score"],
            reproducibility_score=scores["reproducibility_score"],
            license_score=scores["license_score"],
            novelty_score=scores["novelty_score"],
            relevance_score=scores["relevance_score"],
            reasoning=scores.get("reasoning", ""),
        )

    def _fallback_score(self, candidate: RawCandidate) -> Dict[str, Any]:
        """规则兜底评分（当LLM失败时）"""
        # 简单规则评分
        activity = 5.0
        if candidate.github_stars:
            if candidate.github_stars >= 1000:
                activity = 9.0
            elif candidate.github_stars >= 500:
                activity = 7.5
            elif candidate.github_stars >= 100:
                activity = 6.0

        reproducibility = 3.0  # 默认低分
        if candidate.github_url:
            reproducibility += 3.0
        if candidate.dataset_url:
            reproducibility += 3.0

        return {
            "activity_score": activity,
            "reproducibility_score": reproducibility,
            "license_score": 5.0,  # 中等分
            "novelty_score": 5.0,
            "relevance_score": 5.0,
            "reasoning": "规则兜底评分（LLM调用失败）"
        }

    async def score_batch(self, candidates: List[RawCandidate]) -> List[ScoredCandidate]:
        """批量评分"""
        if not candidates:
            return []

        tasks = [self.score(c) for c in candidates]
        scored = await asyncio.gather(*tasks)

        logger.info(f"批量评分完成: {len(scored)}条")
        return list(scored)
```

**单元测试**: `tests/unit/test_scorer.py`
```python
"""LLM评分测试"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import RawCandidate
from src.scorer.llm_scorer import LLMScorer


@pytest.fixture
def sample_candidate():
    return RawCandidate(
        title="AgentBench: Evaluating LLMs as Agents",
        url="https://arxiv.org/abs/2308.03688",
        source="arxiv",
        abstract="We present AgentBench, a benchmark for evaluating LLMs.",
        authors=["Author A"],
        publish_date=datetime.now(timezone.utc),
        github_url="https://github.com/example/agentbench",
        github_stars=1500,
    )


@pytest.mark.asyncio
async def test_llm_scorer_with_mock(sample_candidate):
    """测试LLM评分（Mock OpenAI API）"""
    # Mock OpenAI响应
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"activity_score": 8.5, "reproducibility_score": 9.0, "license_score": 10.0, "novelty_score": 7.0, "relevance_score": 8.0, "reasoning": "Test"}'
            )
        )
    ]

    with patch("src.scorer.llm_scorer.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        async with LLMScorer() as scorer:
            scorer.redis_client = None  # 禁用Redis缓存
            result = await scorer.score(sample_candidate)

            assert result.title == sample_candidate.title
            assert 0 <= result.activity_score <= 10
            assert 0 <= result.reproducibility_score <= 10
            assert result.reasoning == "Test"


@pytest.mark.asyncio
async def test_fallback_score(sample_candidate):
    """测试规则兜底评分"""
    async with LLMScorer() as scorer:
        fallback = scorer._fallback_score(sample_candidate)

        assert fallback["activity_score"] == 9.0  # 1500 stars
        assert fallback["reproducibility_score"] == 6.0  # 有GitHub URL
        assert "reasoning" in fallback
```

**验收标准**:
- [ ] `LLMScorer`类实现完成
- [ ] Redis缓存机制工作正常
- [ ] LLM调用失败时规则兜底生效
- [ ] 单元测试通过
- [ ] 使用真实数据测试评分结果合理

**测试命令**:
```bash
# 运行单元测试
pytest tests/unit/test_scorer.py -v

# 手动测试真实数据（需要OpenAI API可用）
python << 'EOF'
import asyncio
import json
from src.models import RawCandidate
from src.scorer.llm_scorer import LLMScorer

async def test():
    with open('docs/samples/collected_data.json') as f:
        data = json.load(f)[0]

    candidate = RawCandidate(
        title=data['title'],
        url=data['url'],
        source=data['source'],
        abstract=data['abstract'],
        authors=data['authors'],
        publish_date=None
    )

    async with LLMScorer() as scorer:
        result = await scorer.score(candidate)

        print(f"标题: {result.title[:50]}...")
        print(f"活跃度: {result.activity_score}/10")
        print(f"可复现性: {result.reproducibility_score}/10")
        print(f"许可合规: {result.license_score}/10")
        print(f"新颖性: {result.novelty_score}/10")
        print(f"MGX适配度: {result.relevance_score}/10")
        print(f"评分依据: {result.reasoning}")

asyncio.run(test())
EOF
```

---

### Task 3: 飞书多维表格存储（第三优先级）

**重要**: 这个任务需要真实的飞书API凭证，建议：
1. 先实现Task 4 (SQLite备份)
2. 再实现Task 3 (飞书存储)
3. 最后实现Task 5 (存储管理器串联两者)

详细实现代码见: `.claude/specs/benchmark-intelligence-agent/PHASE2-PROMPT.md` Task 3部分

---

### Task 4-7: 后续任务

详细实现代码见: `.claude/specs/benchmark-intelligence-agent/PHASE2-PROMPT.md`

---

## 开发顺序建议

### 第一天（今天）
1. ✅ **Task 1: 规则预筛选** - 实现 + 测试
2. ⏭️ **提交代码**: `feat(prefilter): implement rule-based candidate filtering`

### 第二天
3. ✅ **Task 2: LLM评分引擎** - 实现 + 测试
4. ⏭️ **提交代码**: `feat(scorer): implement LLM scoring with Redis cache`

### 第三天
5. ✅ **Task 4: SQLite备份** - 实现 + 测试
6. ⏭️ **Task 3: 飞书存储** - 实现 + 测试
7. ⏭️ **提交代码**: `feat(storage): implement Feishu and SQLite storage`

### 第四天
8. ✅ **Task 5: 存储管理器** - 实现 + 测试
9. ✅ **Task 6: 飞书通知** - 实现 + 测试
10. ⏭️ **提交代码**: `feat(notifier): implement Feishu webhook notification`

### 第五天
11. ✅ **Task 7: 主流程更新** - 串联所有模块
12. ✅ **端到端测试** - 使用真实数据测试完整流程
13. ⏭️ **提交代码**: `feat(main): integrate scoring and storage pipeline`
14. ✅ **更新文档**: `docs/test-report.md`

---

## 关键提醒

### 代码规范（强制）
- 禁止emoji (代码、文档、日志、commit message)
- 关键逻辑必须写中文注释
- 最大嵌套层级 ≤ 3
- 所有魔法数字定义在`constants.py`

### Commit规范（强制）
- 使用conventional commits格式
- 禁止添加"Generated with Claude Code"
- 禁止添加"Co-Authored-By: Claude"

示例:
```bash
feat(prefilter): implement rule-based candidate filtering
fix(scorer): handle LLM timeout with exponential backoff
test(storage): add unit tests for Feishu API integration
docs(test-report): add Phase 2 manual test results
```

### 测试要求（强制）
- 每个模块必须有单元测试
- 单元测试覆盖率 ≥ 60%
- 手动测试结果记录到`docs/test-report.md`
- 使用真实数据 (`docs/samples/collected_data.json`) 验证

---

## 验收标准（Phase 2完成时）

### 功能验收
- [ ] 规则预筛选过滤率40-60%
- [ ] LLM评分返回5维度分数
- [ ] 飞书多维表格自动写入
- [ ] SQLite降级备份生效
- [ ] 飞书通知每日推送Top 5
- [ ] 完整流程执行时间 < 20分钟

### 质量验收
- [ ] 单元测试覆盖率 ≥ 60%
- [ ] 所有测试通过 (pytest)
- [ ] 代码PEP8合规 (black + ruff)
- [ ] 手动测试通过 (docs/test-report.md更新)

### 成本验收
- [ ] LLM月成本 < ¥50
- [ ] Redis缓存命中率 ≥ 30%
- [ ] 飞书API调用 < 100次/天

---

## 立即开始

请按以下步骤开始Task 1开发：

1. **激活环境**:
   ```bash
   cd /mnt/d/VibeCoding_pgm/BenchScope
   source activate_env.sh
   ```

2. **创建必要文件**:
   - `src/common/constants.py`
   - `src/common/__init__.py`
   - `src/prefilter/rule_filter.py`
   - `src/prefilter/__init__.py`
   - `tests/unit/test_prefilter.py`

3. **实现并测试**:
   ```bash
   pytest tests/unit/test_prefilter.py -v
   ```

4. **使用真实数据验证**:
   ```bash
   python << 'EOF'
   # (见上文"测试命令"部分)
   EOF
   ```

5. **提交代码**:
   ```bash
   git add src/common/ src/prefilter/ tests/unit/test_prefilter.py
   git commit -m "feat(prefilter): implement rule-based candidate filtering"
   git push origin main
   ```

6. **报告进度并继续Task 2**

有任何问题随时询问用户。现在开始Task 1实现！
