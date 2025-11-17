# Codex开发指令 - Phase 7: MGX场景聚焦优化

**接收方**: Codex
**发送方**: Claude Code
**PRD文档**: `PHASE7-FOCUS-PRD.md`
**预计工期**: 9天
**开发模式**: 严格按照本文档的代码实现，禁止自由发挥

---

## 📋 开发总览

### 核心目标

通过三层过滤策略，将采集精准度从3.5%提升到20-30%：
- **Layer 1**: 数据源关键词聚焦（修改yaml配置）
- **Layer 2**: 采集器内置任务过滤（修改Python代码）
- **Layer 3**: 预筛选规则增强（修改Python代码）

### 文件修改清单

| 文件 | 修改类型 | 优先级 | 预计耗时 |
|------|---------|--------|---------|
| `config/sources.yaml` | 配置优化 | P0 | 1h |
| `src/collectors/helm_collector.py` | 代码增强 | P0 | 4h |
| `src/collectors/github_collector.py` | 代码增强 | P0 | 6h |
| `src/prefilter/rule_filter.py` | 代码增强 | P1 | 3h |
| `src/scorer/llm_scorer.py` | Prompt优化 | P2 | 1h |
| `src/common/constants.py` | 新增常量 | P1 | 0.5h |
| `tests/test_phase7_filtering.py` | 新增测试 | P1 | 4h |

---

## 🔧 Task 1: 数据源配置优化

**文件**: `config/sources.yaml`
**优先级**: P0
**预计耗时**: 1小时

### 实现要求

完整替换 `config/sources.yaml` 内容，重点修改：
1. arXiv关键词从4个泛化词 → 12个聚焦词组
2. GitHub topics从3个泛化词 → 12个聚焦词
3. GitHub min_stars从0 → 50
4. HuggingFace task_categories从3个 → 1个
5. HELM新增allowed/excluded_scenarios配置

### 完整代码

```yaml
# BenchScope 数据源配置 - Phase 7优化版
# 说明: 此文件定义所有数据采集源的参数，支持运行时修改无需重新部署

# ============================================================
# 论文库 (Academic Papers)
# ============================================================

arxiv:
  enabled: true
  max_results: 50
  lookback_hours: 168  # 7天窗口
  timeout_seconds: 10
  max_retries: 3

  # Phase 7优化: 聚焦MGX场景关键词（编程/Web/Agent）
  keywords:
    # P0: 编程与代码
    - code generation benchmark
    - code evaluation
    - programming benchmark
    - software engineering benchmark
    - program synthesis evaluation
    - code completion benchmark

    # P0: Web自动化
    - web agent benchmark
    - browser automation benchmark
    - web navigation evaluation
    - GUI automation benchmark

    # P1: 多智能体
    - multi-agent benchmark
    - agent collaboration evaluation
    - tool use benchmark
    - API usage benchmark

  categories:
    - cs.SE  # Software Engineering (新增)
    - cs.AI  # Artificial Intelligence
    - cs.CL  # Computation and Language (保留，可能包含code-related NLP)
    # 移除 cs.CV (视觉), cs.MM (多媒体)

semantic_scholar:
  enabled: false  # 暂时禁用：无API密钥
  api_key: ${SEMANTIC_SCHOLAR_API_KEY}
  lookback_years: 2
  max_results: 100
  timeout_seconds: 15
  venues:
    - NeurIPS
    - ICLR
    - ICML
    - ACL
    - EMNLP
    - NAACL
  keywords:
    - benchmark
    - evaluation
    - dataset

# ============================================================
# 评测榜单 (Leaderboards)
# ============================================================

helm:
  enabled: true
  base_url: "https://crfm.stanford.edu/helm/classic/latest/"
  storage_base: "https://storage.googleapis.com/crfm-helm-public/benchmark_output"
  default_release: "v0.4.0"
  timeout_seconds: 15

  # Phase 7新增: 任务类型白名单（仅采集这些类型）
  allowed_scenarios:
    - code        # 代码生成
    - coding      # 编程任务
    - program     # 程序相关
    - reasoning   # 推理（数学/逻辑）
    - math        # 数学
    - logic       # 逻辑
    - tool        # 工具使用
    - api         # API调用
    - agent       # Agent任务
    - web         # Web相关
    - browser     # 浏览器

  # Phase 7新增: 任务类型黑名单（排除这些类型）
  excluded_scenarios:
    - qa                    # 问答
    - question              # 问题
    - answer                # 回答
    - reading               # 阅读
    - comprehension         # 理解
    - dialogue              # 对话
    - conversation          # 交谈
    - summarization         # 摘要
    - summary               # 总结
    - translation           # 翻译
    - sentiment             # 情感
    - classification        # 分类
    - image                 # 图像
    - vision                # 视觉
    - video                 # 视频

open_llm_leaderboard:
  enabled: false  # Phase 6待实现
  api_url: "https://huggingface.co/api/open-llm-leaderboard/v1/submissions"
  min_score: 60.0
  lookback_days: 30

evalplus:
  enabled: false  # Phase 6待实现
  github_repo: "evalplus/evalplus"
  api_url: "https://evalplus.github.io/leaderboard.html"
  timeout_seconds: 15

# ============================================================
# 开源社区 (Open Source Platforms)
# ============================================================

github:
  enabled: true
  trending_url: "https://github.com/trending"
  search_api: "https://api.github.com/search/repositories"

  # Phase 7优化: 聚焦MGX场景topics
  topics:
    # P0: 编程
    - code-generation
    - code-benchmark
    - program-synthesis
    - coding-challenge
    - software-testing

    # P0: Web自动化
    - web-automation
    - browser-automation
    - web-agent
    - selenium-testing
    - playwright

    # P1: GUI & Agent
    - gui-automation
    - agent-benchmark
    - multi-agent
    - llm-agent

  # Phase 7优化: 提高stars门槛（减少低质量项目）
  min_stars: 50  # 从0提升到50

  lookback_days: 30
  timeout_seconds: 5
  token: ${GITHUB_TOKEN}

  # Phase 7新增: README最小长度（确保有文档）
  min_readme_length: 500
  max_days_since_update: 90

huggingface:
  enabled: true
  api_url: "https://huggingface.co/api/datasets"

  # Phase 7优化: 收窄关键词
  keywords:
    - code
    - programming
    - software
    - benchmark

  # Phase 7优化: 仅保留code相关任务
  task_categories:
    - code  # 代码相关数据集
    # 删除: text-generation, question-answering (太泛)

  min_downloads: 100
  max_results: 50
  lookback_days: 14

# ============================================================
# 团队线索 (Internal Sources)
# ============================================================

feishu_chat:
  enabled: false  # Phase 7+ 功能
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}
  monitored_groups:
    - "Benchmark研究群"
  keywords:
    - benchmark
    - 评测
  lookback_days: 7

# ============================================================
# 社交媒体 (Social Media) - 可选
# ============================================================

twitter:
  enabled: false  # Phase 7+ 功能
  api_key: ${TWITTER_API_KEY}
  api_secret: ${TWITTER_API_SECRET}
  monitored_accounts:
    - "@paperswithcode"
    - "@huggingface"
  keywords:
    - "#benchmark"
    - "#evaluation"
  lookback_days: 3

# ============================================================
# 全局配置 (Global Settings)
# ============================================================

global:
  max_concurrent_collectors: 5

  deduplication:
    url_normalization: true
    title_similarity_threshold: 0.9

  adaptive_window:
    enabled: true
    min_candidates_per_run: 5
    max_lookback_multiplier: 3

  error_handling:
    retry_on_timeout: true
    max_retries: 3
    fallback_to_cache: true
```

### 验证步骤

修改完成后，运行以下命令验证配置：

```bash
# 验证YAML语法
python -c "import yaml; yaml.safe_load(open('config/sources.yaml'))"

# 验证配置加载
.venv/bin/python -c "
from src.config import get_settings
settings = get_settings()
print(f'arXiv keywords: {len(settings.sources.arxiv.keywords)}')
print(f'GitHub topics: {len(settings.sources.github.topics)}')
print(f'GitHub min_stars: {settings.sources.github.min_stars}')
print(f'HELM allowed: {len(settings.sources.helm.allowed_scenarios)}')
"
```

预期输出：
```
arXiv keywords: 12
GitHub topics: 12
GitHub min_stars: 50
HELM allowed: 11
```

---

## 🔧 Task 2: HELM采集器增强

**文件**: `src/collectors/helm_collector.py`
**优先级**: P0
**预计耗时**: 4小时

### 实现要求

1. 读取HELM配置中的 `allowed_scenarios` 和 `excluded_scenarios`
2. 新增 `_is_relevant_scenario()` 方法判断场景相关性
3. 在 `collect()` 方法中集成过滤逻辑
4. 添加详细日志记录过滤前后数量

### 完整代码

首先读取现有代码：

```bash
# 先查看现有代码结构
head -100 src/collectors/helm_collector.py
```

然后修改为以下完整代码（保留原有逻辑，新增过滤功能）：

```python
"""HELM Leaderboard采集器 - Phase 7增强版"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import get_settings
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class HelmCollector(BaseCollector):
    """HELM (Holistic Evaluation of Language Models) Leaderboard采集器

    Phase 7增强: 添加任务类型过滤，仅采集与MGX场景相关的benchmark
    """

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.helm_config = self.settings.sources.helm

        # Phase 7新增: 从配置读取允许/排除的场景关键词
        self.allowed_keywords = set(
            kw.lower() for kw in self.helm_config.allowed_scenarios
        )
        self.excluded_keywords = set(
            kw.lower() for kw in self.helm_config.excluded_scenarios
        )

        logger.info(
            f"HELM过滤配置加载: 允许{len(self.allowed_keywords)}类, "
            f"排除{len(self.excluded_keywords)}类"
        )

    def _is_relevant_scenario(
        self,
        scenario_name: str,
        description: str = ""
    ) -> bool:
        """判断HELM scenario是否与MGX场景相关

        Phase 7新增方法

        Args:
            scenario_name: HELM scenario名称（如"code_generation_humaneval"）
            description: scenario描述（可选）

        Returns:
            True表示相关，False表示无关

        过滤逻辑:
            1. 黑名单优先: 包含任一排除关键词 → False
            2. 白名单验证: 必须包含至少一个允许关键词 → True
        """
        # 合并名称和描述进行检查
        text = f"{scenario_name} {description}".lower()

        # 1. 黑名单优先（包含任一排除词则过滤）
        for excluded in self.excluded_keywords:
            if excluded in text:
                logger.debug(
                    f"过滤HELM scenario（黑名单: {excluded}）: {scenario_name}"
                )
                return False

        # 2. 白名单验证（必须包含至少一个允许词）
        for allowed in self.allowed_keywords:
            if allowed in text:
                logger.debug(
                    f"保留HELM scenario（白名单: {allowed}）: {scenario_name}"
                )
                return True

        # 3. 未命中白名单，过滤
        logger.debug(
            f"过滤HELM scenario（未命中白名单）: {scenario_name}"
        )
        return False

    async def _fetch_scenarios(self) -> List[Dict[str, Any]]:
        """从HELM网站抓取scenario列表

        Returns:
            scenario字典列表，每个包含name/description/url等字段
        """
        url = f"{self.helm_config.base_url}?group=all"

        try:
            async with httpx.AsyncClient(
                timeout=self.helm_config.timeout_seconds
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # 解析HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # 查找所有scenario条目（根据HELM页面结构提取）
                # 注意: HELM页面结构可能变化，需根据实际调整
                scenarios = []

                # 示例解析逻辑（需根据实际HELM页面调整）
                scenario_elements = soup.find_all("div", class_="scenario-item")

                for elem in scenario_elements:
                    name_elem = elem.find("h3", class_="scenario-name")
                    desc_elem = elem.find("p", class_="scenario-description")
                    link_elem = elem.find("a", href=True)

                    if name_elem:
                        scenario = {
                            "name": name_elem.text.strip(),
                            "description": desc_elem.text.strip() if desc_elem else "",
                            "url": f"{self.helm_config.base_url}{link_elem['href']}" if link_elem else url,
                        }
                        scenarios.append(scenario)

                logger.info(f"从HELM抓取到{len(scenarios)}个scenarios")
                return scenarios

        except httpx.TimeoutException:
            logger.error(f"HELM请求超时: {url}")
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(f"HELM请求失败 {exc.response.status_code}: {url}")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error(f"HELM解析失败: {exc}")
            return []

    def _build_candidate(self, scenario: Dict[str, Any]) -> RawCandidate:
        """将HELM scenario转换为RawCandidate

        Args:
            scenario: scenario字典

        Returns:
            RawCandidate对象
        """
        return RawCandidate(
            title=scenario["name"],
            url=scenario["url"],
            source="HELM",
            abstract=scenario.get("description", ""),
            authors=None,
            publish_date=None,
            github_stars=None,
            github_url=None,
            dataset_url=None,
            paper_url=None,
            task_type="benchmark",
            license_type=None,
            evaluation_metrics=None,
            reproduction_script_url=None,
            raw_metadata={"helm_scenario": scenario},
        )

    async def collect(self) -> List[RawCandidate]:
        """采集HELM benchmark（Phase 7增强版：带任务过滤）

        Returns:
            RawCandidate列表
        """
        if not self.helm_config.enabled:
            logger.info("HELM采集器已禁用")
            return []

        # 1. 抓取所有scenarios
        scenarios = await self._fetch_scenarios()
        if not scenarios:
            logger.warning("HELM未抓取到任何scenario")
            return []

        # 2. Phase 7新增: 任务类型过滤
        filtered_scenarios = [
            s for s in scenarios
            if self._is_relevant_scenario(s["name"], s.get("description", ""))
        ]

        filter_rate = (
            (1 - len(filtered_scenarios) / len(scenarios)) * 100
            if scenarios else 0
        )

        logger.info(
            f"HELM任务过滤: {len(scenarios)}条 → {len(filtered_scenarios)}条 "
            f"(过滤率{filter_rate:.1f}%)"
        )

        # 3. 构建候选列表
        candidates = [
            self._build_candidate(s) for s in filtered_scenarios
        ]

        logger.info(f"✓ HelmCollector: {len(candidates)}条")
        return candidates
```

### 配置支持（需同步修改config.py）

在 `src/config.py` 中，确保 `HelmSettings` 模型包含新字段：

```python
class HelmSettings(BaseModel):
    """HELM配置"""
    enabled: bool = True
    base_url: str
    storage_base: str = ""
    default_release: str = "v0.4.0"
    timeout_seconds: int = 15

    # Phase 7新增
    allowed_scenarios: List[str] = Field(default_factory=list)
    excluded_scenarios: List[str] = Field(default_factory=list)
```

### 单元测试

创建 `tests/test_helm_collector.py`:

```python
"""HELM采集器单元测试"""
import pytest
from src.collectors.helm_collector import HelmCollector


@pytest.fixture
def helm_collector():
    """创建HELM采集器实例"""
    return HelmCollector()


class TestHelmScenarioFiltering:
    """测试HELM scenario过滤逻辑"""

    def test_allowed_scenario_code(self, helm_collector):
        """测试允许的code场景"""
        assert helm_collector._is_relevant_scenario(
            "code_generation_humaneval",
            "Evaluates code generation on HumanEval"
        ) is True

    def test_allowed_scenario_reasoning(self, helm_collector):
        """测试允许的reasoning场景"""
        assert helm_collector._is_relevant_scenario(
            "math_problem_solving",
            "Evaluates mathematical reasoning"
        ) is True

    def test_excluded_scenario_qa(self, helm_collector):
        """测试排除的QA场景"""
        assert helm_collector._is_relevant_scenario(
            "question_answering_squad",
            "Reading comprehension on SQuAD"
        ) is False

    def test_excluded_scenario_dialogue(self, helm_collector):
        """测试排除的dialogue场景"""
        assert helm_collector._is_relevant_scenario(
            "dialogue_generation",
            "Conversational dialogue"
        ) is False

    def test_excluded_scenario_vision(self, helm_collector):
        """测试排除的vision场景"""
        assert helm_collector._is_relevant_scenario(
            "image_classification_imagenet",
            "Visual recognition"
        ) is False

    def test_edge_case_empty_description(self, helm_collector):
        """测试边缘情况：空描述"""
        # 仅基于名称判断
        assert helm_collector._is_relevant_scenario(
            "coding_benchmark", ""
        ) is True

        assert helm_collector._is_relevant_scenario(
            "summarization_task", ""
        ) is False
```

运行测试：

```bash
.venv/bin/python -m pytest tests/test_helm_collector.py -v
```

---

## 🔧 Task 3: GitHub采集器增强

**文件**: `src/collectors/github_collector.py`
**优先级**: P0
**预计耗时**: 6小时

### 实现要求

1. 新增 `_fetch_readme()` 方法获取仓库README内容
2. 新增 `_is_benchmark_repo()` 方法判断是否为真Benchmark
3. 在 `collect()` 中并发验证仓库
4. 添加详细日志

### 关键挑战

- GitHub API限流：需添加缓存和速率控制
- README内容可能很大：限制读取大小
- 并发请求控制：避免触发API限制

### 完整代码

```python
"""GitHub采集器 - Phase 7增强版"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional

import httpx

from src.collectors.base import BaseCollector
from src.config import get_settings
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    """GitHub仓库采集器

    Phase 7增强: 添加README内容分析，过滤非Benchmark仓库
    """

    # Phase 7新增: README关键词白名单（至少包含一个）
    README_REQUIRED_KEYWORDS = {
        "benchmark", "evaluation", "eval", "dataset",
        "leaderboard", "test set", "baseline", "metric",
        "评测", "评估", "基准"
    }

    # Phase 7新增: README关键词黑名单（包含任一则过滤）
    README_EXCLUDED_KEYWORDS = {
        # 资源汇总
        "awesome list", "curated", "collection", "resources",
        "list of", "资源汇总", "精选列表",

        # 教程/课程
        "tutorial", "course", "guide", "learning",
        "教程", "课程", "指南",

        # 工具/框架
        "framework", "library", "tool", "sdk",
        "api wrapper", "工具", "框架", "库"
    }

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.github_config = self.settings.sources.github

        # GitHub API headers
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "BenchScope/1.0"
        }

        # 添加token（如果配置了）
        if self.github_config.token:
            self.headers["Authorization"] = f"token {self.github_config.token}"

        # README缓存（避免重复请求）
        self._readme_cache: Dict[str, Optional[str]] = {}

    async def _fetch_readme(
        self,
        repo_full_name: str,
        max_size: int = 10000  # 最多读取10KB
    ) -> Optional[str]:
        """获取仓库README内容

        Phase 7新增方法

        Args:
            repo_full_name: 仓库全名（如"owner/repo"）
            max_size: 最大读取字节数

        Returns:
            README文本内容，失败返回None
        """
        # 1. 检查缓存
        if repo_full_name in self._readme_cache:
            return self._readme_cache[repo_full_name]

        # 2. 请求README API
        url = f"https://api.github.com/repos/{repo_full_name}/readme"

        try:
            async with httpx.AsyncClient(
                timeout=self.github_config.timeout_seconds,
                headers=self.headers
            ) as client:
                response = await client.get(url)

                if response.status_code == 404:
                    logger.debug(f"仓库无README: {repo_full_name}")
                    self._readme_cache[repo_full_name] = None
                    return None

                response.raise_for_status()
                data = response.json()

                # 3. 下载README内容
                download_url = data.get("download_url")
                if not download_url:
                    return None

                content_response = await client.get(download_url)
                content_response.raise_for_status()

                # 4. 限制大小并缓存
                readme_text = content_response.text[:max_size]
                self._readme_cache[repo_full_name] = readme_text

                return readme_text

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                logger.warning(f"GitHub API限流，跳过README获取: {repo_full_name}")
            else:
                logger.error(f"README请求失败 {exc.response.status_code}: {repo_full_name}")
            self._readme_cache[repo_full_name] = None
            return None

        except Exception as exc:  # noqa: BLE001
            logger.error(f"README获取异常: {exc}")
            self._readme_cache[repo_full_name] = None
            return None

    async def _is_benchmark_repo(self, repo: Dict[str, Any]) -> bool:
        """判断仓库是否为真Benchmark（而非工具/教程/资源汇总）

        Phase 7新增方法

        Args:
            repo: GitHub API返回的仓库字典

        Returns:
            True表示是Benchmark，False表示不是

        判断逻辑:
            1. 获取README内容
            2. 黑名单过滤（awesome list/教程/工具）
            3. 白名单验证（必须包含benchmark相关词汇）
        """
        repo_name = repo["full_name"]

        # 1. 获取README
        readme_text = await self._fetch_readme(repo_name)
        if not readme_text:
            # 无README或获取失败，保守保留（避免过度过滤）
            logger.debug(f"无README内容，保守保留: {repo_name}")
            return True

        readme_lower = readme_text.lower()

        # 2. 黑名单过滤（awesome list/教程/工具）
        for excluded in self.README_EXCLUDED_KEYWORDS:
            if excluded in readme_lower:
                logger.debug(
                    f"过滤GitHub仓库（黑名单: {excluded}）: {repo_name}"
                )
                return False

        # 3. 白名单验证（必须包含benchmark相关词汇）
        has_benchmark_keyword = any(
            keyword in readme_lower
            for keyword in self.README_REQUIRED_KEYWORDS
        )

        if not has_benchmark_keyword:
            logger.debug(
                f"过滤GitHub仓库（未命中白名单）: {repo_name}"
            )
            return False

        logger.debug(f"保留GitHub仓库（Benchmark验证通过）: {repo_name}")
        return True

    async def _search_repos(self) -> List[Dict[str, Any]]:
        """搜索GitHub仓库

        Returns:
            仓库字典列表
        """
        # 构建搜索查询
        topics_query = " OR ".join(
            f"topic:{topic}" for topic in self.github_config.topics
        )

        # 时间窗口
        from datetime import datetime, timedelta
        since_date = (
            datetime.now() - timedelta(days=self.github_config.lookback_days)
        ).strftime("%Y-%m-%d")

        query = (
            f"({topics_query}) "
            f"stars:>={self.github_config.min_stars} "
            f"pushed:>={since_date}"
        )

        url = f"{self.github_config.search_api}?q={query}&sort=stars&order=desc"

        try:
            async with httpx.AsyncClient(
                timeout=self.github_config.timeout_seconds,
                headers=self.headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                repos = data.get("items", [])
                logger.info(f"GitHub搜索返回{len(repos)}个仓库")
                return repos

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                logger.error("GitHub API限流，请配置GITHUB_TOKEN")
            else:
                logger.error(f"GitHub搜索失败 {exc.response.status_code}")
            return []

        except Exception as exc:  # noqa: BLE001
            logger.error(f"GitHub搜索异常: {exc}")
            return []

    def _build_candidate(self, repo: Dict[str, Any]) -> RawCandidate:
        """将GitHub仓库转换为RawCandidate"""
        return RawCandidate(
            title=repo["name"],
            url=repo["html_url"],
            source="GitHub",
            abstract=repo.get("description", ""),
            authors=repo["owner"]["login"] if repo.get("owner") else None,
            publish_date=repo.get("created_at"),
            github_stars=repo.get("stargazers_count"),
            github_url=repo["html_url"],
            dataset_url=None,
            paper_url=None,
            task_type="benchmark",
            license_type=repo.get("license", {}).get("spdx_id") if repo.get("license") else None,
            evaluation_metrics=None,
            reproduction_script_url=None,
            raw_metadata={"github_repo": repo},
        )

    async def collect(self) -> List[RawCandidate]:
        """采集GitHub仓库（Phase 7增强版：带Benchmark验证）

        Returns:
            RawCandidate列表
        """
        if not self.github_config.enabled:
            logger.info("GitHub采集器已禁用")
            return []

        # 1. 搜索仓库
        repos = await self._search_repos()
        if not repos:
            logger.warning("GitHub未搜索到任何仓库")
            return []

        # 2. Phase 7新增: 并发验证是否为Benchmark
        # 注意: 控制并发数避免API限流
        semaphore = asyncio.Semaphore(5)  # 最多5个并发请求

        async def verify_with_semaphore(repo):
            async with semaphore:
                return await self._is_benchmark_repo(repo)

        verification_tasks = [verify_with_semaphore(repo) for repo in repos]
        is_benchmark_list = await asyncio.gather(*verification_tasks)

        # 3. 过滤非Benchmark仓库
        filtered_repos = [
            repo for repo, is_benchmark in zip(repos, is_benchmark_list)
            if is_benchmark
        ]

        filter_rate = (
            (1 - len(filtered_repos) / len(repos)) * 100
            if repos else 0
        )

        logger.info(
            f"GitHub Benchmark验证: {len(repos)}条 → {len(filtered_repos)}条 "
            f"(过滤率{filter_rate:.1f}%)"
        )

        # 4. 构建候选列表
        candidates = [
            self._build_candidate(repo) for repo in filtered_repos
        ]

        logger.info(f"✓ GitHubCollector: {len(candidates)}条")
        return candidates
```

### 单元测试

创建 `tests/test_github_collector.py`:

```python
"""GitHub采集器单元测试"""
import pytest
from src.collectors.github_collector import GitHubCollector


@pytest.fixture
def github_collector():
    """创建GitHub采集器实例"""
    return GitHubCollector()


class TestGitHubBenchmarkVerification:
    """测试GitHub Benchmark验证逻辑"""

    @pytest.mark.asyncio
    async def test_benchmark_repo_with_valid_readme(self, github_collector):
        """测试有效的Benchmark仓库"""
        mock_repo = {
            "full_name": "test/humaneval",
            "name": "HumanEval",
            "html_url": "https://github.com/test/humaneval"
        }

        # Mock README内容（包含benchmark关键词）
        github_collector._readme_cache[mock_repo["full_name"]] = """
        # HumanEval Benchmark

        This is a code generation benchmark with 164 programming problems.

        ## Evaluation

        We provide baseline results for GPT-4.
        """

        result = await github_collector._is_benchmark_repo(mock_repo)
        assert result is True

    @pytest.mark.asyncio
    async def test_non_benchmark_awesome_list(self, github_collector):
        """测试非Benchmark - awesome list"""
        mock_repo = {
            "full_name": "test/awesome-ai",
            "name": "awesome-ai",
            "html_url": "https://github.com/test/awesome-ai"
        }

        # Mock README内容（awesome list）
        github_collector._readme_cache[mock_repo["full_name"]] = """
        # Awesome AI Resources

        A curated list of AI resources and tools.
        """

        result = await github_collector._is_benchmark_repo(mock_repo)
        assert result is False

    @pytest.mark.asyncio
    async def test_non_benchmark_framework(self, github_collector):
        """测试非Benchmark - 框架工具"""
        mock_repo = {
            "full_name": "test/agent-framework",
            "name": "agent-framework",
            "html_url": "https://github.com/test/agent-framework"
        }

        # Mock README内容（框架）
        github_collector._readme_cache[mock_repo["full_name"]] = """
        # Agent Framework

        A powerful framework for building AI agents.

        ## Installation

        pip install agent-framework
        """

        result = await github_collector._is_benchmark_repo(mock_repo)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_readme_conservative_keep(self, github_collector):
        """测试无README的保守策略"""
        mock_repo = {
            "full_name": "test/no-readme",
            "name": "no-readme",
            "html_url": "https://github.com/test/no-readme"
        }

        # Mock无README
        github_collector._readme_cache[mock_repo["full_name"]] = None

        # 保守保留（避免误杀）
        result = await github_collector._is_benchmark_repo(mock_repo)
        assert result is True
```

运行测试：

```bash
.venv/bin/python -m pytest tests/test_github_collector.py -v
```

---

## 🔧 Task 4: 预筛选规则增强

**文件**: `src/prefilter/rule_filter.py`
**优先级**: P1
**预计耗时**: 3小时

### 实现要求

1. 新增 `REQUIRED_KEYWORDS` 和 `EXCLUDED_KEYWORDS` 常量
2. 新增 `_check_keyword_relevance()` 方法
3. 在 `prefilter_batch()` 中集成关键词过滤
4. 优化日志输出

### 完整代码

首先读取现有代码，然后修改：

```python
"""规则预筛选器 - Phase 7增强版"""
from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

from src.models import RawCandidate

logger = logging.getLogger(__name__)


class RuleFilter:
    """规则预筛选器

    Phase 7增强: 添加关键词相关性过滤
    """

    # Phase 7新增: 标题/摘要必需关键词（至少包含一个）
    REQUIRED_KEYWORDS = {
        # P0: 编程
        "code", "coding", "program", "programming", "software",
        "代码", "编程",

        # P0: Web
        "web", "browser", "gui", "ui", "frontend",
        "浏览器",

        # P1: Agent
        "agent", "tool", "api", "task", "planning",
        "智能体", "工具",

        # P2: 推理
        "reasoning", "math", "logic",
        "推理", "数学", "逻辑",

        # Benchmark通用词（保底）
        "benchmark", "evaluation", "eval", "dataset",
        "评测", "评估", "基准"
    }

    # Phase 7新增: 标题/摘要排除关键词（包含任一则过滤）
    EXCLUDED_KEYWORDS = {
        # 视觉/音频
        "image", "vision", "video", "speech", "audio",
        "图像", "视觉", "视频", "语音",

        # 纯NLP
        "translation", "translate", "summarization", "summary",
        "sentiment", "classification", "emotion",
        "翻译", "摘要", "情感", "分类",

        # 对话
        "dialogue", "conversation", "chatbot", "chat",
        "对话", "聊天",

        # 资源汇总
        "awesome", "curated", "collection", "list of",
        "精选", "汇总",

        # 工具/框架（除非同时有benchmark关键词）
        "framework", "library", "sdk", "wrapper",
        "框架", "库"
    }

    def __init__(self) -> None:
        self.seen_urls: set[str] = set()

    def _normalize_url(self, url: str) -> str:
        """标准化URL（去除查询参数）"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _deduplicate_by_url(
        self,
        candidates: List[RawCandidate]
    ) -> List[RawCandidate]:
        """URL去重"""
        unique_candidates = []

        for candidate in candidates:
            normalized_url = self._normalize_url(candidate.url)

            if normalized_url not in self.seen_urls:
                self.seen_urls.add(normalized_url)
                unique_candidates.append(candidate)
            else:
                logger.debug(f"URL重复过滤: {candidate.title[:50]}")

        logger.info(
            f"URL去重: {len(candidates)}条 → {len(unique_candidates)}条 "
            f"(过滤{len(candidates) - len(unique_candidates)}条)"
        )

        return unique_candidates

    def _check_keyword_relevance(self, candidate: RawCandidate) -> bool:
        """检查关键词相关性

        Phase 7新增方法

        Args:
            candidate: 候选项

        Returns:
            True表示相关，False表示无关

        判断逻辑:
            1. 排除无关领域（视觉/音频/纯NLP）
            2. 必须命中MGX场景关键词
        """
        # 合并标题和摘要进行检查
        text = f"{candidate.title} {candidate.abstract or ''}".lower()

        # 1. 排除无关领域
        for excluded in self.EXCLUDED_KEYWORDS:
            if excluded in text:
                logger.debug(
                    f"过滤候选（排除关键词: {excluded}）: {candidate.title[:50]}"
                )
                return False

        # 2. 必须命中MGX场景关键词
        has_required = any(required in text for required in self.REQUIRED_KEYWORDS)

        if not has_required:
            logger.debug(
                f"过滤候选（未命中场景关键词）: {candidate.title[:50]}"
            )
            return False

        return True

    def _check_github_quality(self, candidate: RawCandidate) -> bool:
        """GitHub特定质量检查"""
        # Stars门槛（已在采集器中实现，这里保留兜底）
        if candidate.github_stars is not None and candidate.github_stars < 10:
            logger.debug(f"过滤低stars仓库: {candidate.title[:50]}")
            return False

        # README长度检查（已在采集器中实现）
        # 这里可以添加额外的GitHub特定规则

        return True

    def _check_hf_quality(self, candidate: RawCandidate) -> bool:
        """HuggingFace特定质量检查"""
        # Downloads门槛（配置中已定义，这里可以添加额外检查）
        return True

    def prefilter_batch(
        self,
        candidates: List[RawCandidate]
    ) -> List[RawCandidate]:
        """批量预筛选（Phase 7增强版）

        Args:
            candidates: 原始候选列表

        Returns:
            过滤后的候选列表

        过滤流程:
            1. URL去重
            2. Phase 7新增: 关键词相关性过滤
            3. GitHub特定规则
            4. HuggingFace特定规则
        """
        if not candidates:
            return []

        logger.info(f"开始预筛选: {len(candidates)}条候选")

        # 1. URL去重
        unique_candidates = self._deduplicate_by_url(candidates)

        # 2. Phase 7新增: 关键词相关性过滤
        keyword_filtered = [
            c for c in unique_candidates
            if self._check_keyword_relevance(c)
        ]

        keyword_filter_rate = (
            (1 - len(keyword_filtered) / len(unique_candidates)) * 100
            if unique_candidates else 0
        )

        logger.info(
            f"关键词过滤: {len(unique_candidates)}条 → {len(keyword_filtered)}条 "
            f"(过滤率{keyword_filter_rate:.1f}%)"
        )

        # 3. GitHub特定规则
        github_filtered = [
            c for c in keyword_filtered
            if c.source != "GitHub" or self._check_github_quality(c)
        ]

        # 4. HuggingFace特定规则
        final_filtered = [
            c for c in github_filtered
            if c.source != "HuggingFace" or self._check_hf_quality(c)
        ]

        # 总体过滤统计
        total_filter_rate = (
            (1 - len(final_filtered) / len(candidates)) * 100
            if candidates else 0
        )

        logger.info(
            f"预筛选完成: {len(candidates)}条 → {len(final_filtered)}条 "
            f"(总过滤率{total_filter_rate:.1f}%)"
        )

        return final_filtered
```

### 单元测试

创建 `tests/test_rule_filter.py`:

```python
"""预筛选规则单元测试"""
import pytest
from src.prefilter.rule_filter import RuleFilter
from src.models import RawCandidate


@pytest.fixture
def rule_filter():
    """创建规则过滤器实例"""
    return RuleFilter()


class TestKeywordRelevance:
    """测试关键词相关性过滤"""

    def test_relevant_code_benchmark(self, rule_filter):
        """测试相关的代码benchmark"""
        candidate = RawCandidate(
            title="HumanEval: Code Generation Benchmark",
            url="https://example.com/humaneval",
            source="arXiv",
            abstract="A benchmark for evaluating code generation models"
        )
        assert rule_filter._check_keyword_relevance(candidate) is True

    def test_relevant_web_benchmark(self, rule_filter):
        """测试相关的web benchmark"""
        candidate = RawCandidate(
            title="WebArena: Web Agent Benchmark",
            url="https://example.com/webarena",
            source="arXiv",
            abstract="Evaluating web agents on browser automation tasks"
        )
        assert rule_filter._check_keyword_relevance(candidate) is True

    def test_excluded_vision_benchmark(self, rule_filter):
        """测试排除的vision benchmark"""
        candidate = RawCandidate(
            title="ImageNet: Image Classification Benchmark",
            url="https://example.com/imagenet",
            source="arXiv",
            abstract="Large-scale image recognition dataset"
        )
        assert rule_filter._check_keyword_relevance(candidate) is False

    def test_excluded_translation_task(self, rule_filter):
        """测试排除的翻译任务"""
        candidate = RawCandidate(
            title="WMT Translation Benchmark",
            url="https://example.com/wmt",
            source="arXiv",
            abstract="Machine translation evaluation"
        )
        assert rule_filter._check_keyword_relevance(candidate) is False

    def test_excluded_awesome_list(self, rule_filter):
        """测试排除的awesome list"""
        candidate = RawCandidate(
            title="Awesome AI Resources",
            url="https://github.com/test/awesome-ai",
            source="GitHub",
            abstract="A curated list of AI tools and resources"
        )
        assert rule_filter._check_keyword_relevance(candidate) is False
```

运行测试：

```bash
.venv/bin/python -m pytest tests/test_rule_filter.py -v
```

---

## 🔧 Task 5: LLM Prompt优化（可选）

**文件**: `src/scorer/llm_scorer.py`
**优先级**: P2
**预计耗时**: 1小时

### 实现要求

强化system prompt中的MGX场景定义，更明确地区分高/中/低相关性场景。

### 修改内容

找到 `_call_llm()` 方法中的 `system_prompt`，修改为：

```python
system_prompt = """你是一名AI Benchmark评审专家,专注于**编程/Web自动化/GUI/多智能体**领域。

**什么是真正的Benchmark（必须同时满足以下4项）**:
1. ✅ 明确的评测任务定义（如代码生成、问答、推理、Agent规划）
2. ✅ 标准化测试数据集（test set/eval set，不是demo数据）
3. ✅ 明确的评估指标（Accuracy/F1/BLEU/Pass@k/Success Rate等）
4. ✅ 基准结果（baseline performance，如GPT-4得分X%）

**不是Benchmark的项目类型（必须严格排除）**:
- ❌ Awesome lists / 资源汇总 / curated collections
- ❌ 工具/库/框架（如Agent框架、API wrapper、工具集）
- ❌ 教程/课程/学习资料（如system design guides）
- ❌ Demo/Example项目（仅展示功能，无标准评测）
- ❌ 数据集（仅提供数据，无评测任务和指标）

MGX技术背景:
- MGX (https://mgx.dev): 多智能体协作框架,专注Vibe Coding(AI原生编程)
- 基于MetaGPT开源框架构建
- 核心技术方向: 多智能体协作与编排、代码生成与理解、工具调用与任务自动化、智能工作流设计

**MGX场景相关性分级（仅对真Benchmark评分）**:

P0 - 核心场景（relevance_score 8-10分）:
- 代码生成/理解/补全/修复 Benchmark
  示例: HumanEval, MBPP, CodeXGLUE, APPS
- Web自动化/浏览器操作 Benchmark
  示例: WebArena, Mind2Web, WebShop
- GUI自动化/桌面应用 Benchmark
  示例: OSWorld, UIBert
- 多智能体协作 Benchmark
  示例: AgentBench, CAMEL, MetaGPT-Eval

P1 - 辅助场景（relevance_score 5-7分）:
- Agent工具调用/任务规划 Benchmark
  示例: ToolBench, API-Bank, ToolLLM
- 数学/逻辑推理 Benchmark（作为代码推理能力参考）
  示例: GSM8K, MATH, TheoremQA
- 通用推理 Benchmark（如需与代码/Agent结合）
  示例: MMLU（仅code相关子集）, Big-Bench（programming任务）

P2 - 边缘场景（relevance_score 3-4分）:
- 纯数学/逻辑推理（无代码/Agent关联）
  示例: HellaSwag, CommonsenseQA
- 通用NLP Benchmark（仅当包含code子任务）
  示例: GLUE（无code相关）, SuperGLUE

❌ 无关场景（relevance_score 0-2分）:
- 纯NLP任务（情感分析/文本分类/翻译/摘要）
- 对话/聊天（除非是Agent交互）
- 阅读理解/常识推理（除非是代码理解）
- 图像/视觉/语音

**非Benchmark项目（工具/教程/资源汇总）**:
- 无论stars多高，relevance_score必须≤2分
- 示例: system-design-primer (stars虽高但是学习资源) → relevance=1分
- 示例: awesome-chatgpt-prompts (资源汇总) → relevance=1分
- 示例: langchain (工具库) → relevance=2分

**核心判断逻辑**:
- 首先判断"是否是真Benchmark"（有评测任务+数据集+指标+基准结果）
- 如果不是Benchmark → relevance_score自动≤2分，reasoning必须明确说明"不是Benchmark"
- 如果是真Benchmark → 再按MGX场景分级打分（P0/P1/P2/无关）

注意:
- 必须在reasoning中明确说明"是否是真正的Benchmark"
- 必须在reasoning中明确说明"属于MGX哪个场景级别（P0/P1/P2/无关）"
- 如果缺少评测任务/数据集/指标/基准结果中的任何一项，必须标注为"非标准Benchmark"并降低相关性评分"""
```

### 测试方法

运行一次完整流程，检查LLM评分的reasoning是否更明确地区分了场景级别：

```bash
.venv/bin/python src/main.py
```

---

## 🧪 Task 6: 集成测试与调优

**优先级**: P1
**预计耗时**: 2天

### 测试脚本

创建 `scripts/test_phase7_pipeline.py`:

```python
"""Phase 7完整流程测试脚本"""
import asyncio
import logging
from collections import Counter

from src.collectors import (
    ArxivCollector,
    HelmCollector,
    GitHubCollector,
    HuggingFaceCollector,
)
from src.prefilter.rule_filter import RuleFilter
from src.scorer.llm_scorer import LLMScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_full_pipeline():
    """测试Phase 7完整流程"""
    logger.info("=" * 60)
    logger.info("Phase 7 完整流程测试")
    logger.info("=" * 60)

    # Step 1: 采集
    logger.info("\n[1/4] 数据采集...")

    arxiv_collector = ArxivCollector()
    helm_collector = HelmCollector()
    github_collector = GitHubCollector()
    hf_collector = HuggingFaceCollector()

    arxiv_candidates = await arxiv_collector.collect()
    helm_candidates = await helm_collector.collect()
    github_candidates = await github_collector.collect()
    hf_candidates = await hf_collector.collect()

    all_candidates = (
        arxiv_candidates +
        helm_candidates +
        github_candidates +
        hf_candidates
    )

    logger.info(f"采集汇总:")
    logger.info(f"  arXiv: {len(arxiv_candidates)}条")
    logger.info(f"  HELM: {len(helm_candidates)}条")
    logger.info(f"  GitHub: {len(github_candidates)}条")
    logger.info(f"  HuggingFace: {len(hf_candidates)}条")
    logger.info(f"  总计: {len(all_candidates)}条")

    # Step 2: 预筛选
    logger.info("\n[2/4] 预筛选...")

    rule_filter = RuleFilter()
    filtered_candidates = rule_filter.prefilter_batch(all_candidates)

    logger.info(f"预筛选结果: {len(all_candidates)}条 → {len(filtered_candidates)}条")

    # Step 3: LLM评分（采样10条测试）
    logger.info("\n[3/4] LLM评分（采样10条）...")

    sample_candidates = filtered_candidates[:10]

    async with LLMScorer() as scorer:
        scored_candidates = await scorer.score_batch(sample_candidates)

    logger.info(f"评分完成: {len(scored_candidates)}条")

    # Step 4: 统计分析
    logger.info("\n[4/4] 统计分析...")

    # 来源分布
    source_counter = Counter(c.source for c in filtered_candidates)
    logger.info("来源分布:")
    for source, count in source_counter.most_common():
        logger.info(f"  {source}: {count}条")

    # 评分统计
    if scored_candidates:
        avg_score = sum(
            c.activity_score * 0.25 +
            c.reproducibility_score * 0.30 +
            c.license_score * 0.20 +
            c.novelty_score * 0.15 +
            c.relevance_score * 0.10
            for c in scored_candidates
        ) / len(scored_candidates)

        avg_relevance = sum(c.relevance_score for c in scored_candidates) / len(scored_candidates)

        high_priority = sum(
            1 for c in scored_candidates
            if (c.activity_score * 0.25 +
                c.reproducibility_score * 0.30 +
                c.license_score * 0.20 +
                c.novelty_score * 0.15 +
                c.relevance_score * 0.10) >= 7.0
        )

        logger.info(f"评分统计（采样10条）:")
        logger.info(f"  平均总分: {avg_score:.2f}/10")
        logger.info(f"  平均相关性: {avg_relevance:.2f}/10")
        logger.info(f"  高优先级: {high_priority}条 ({high_priority/len(scored_candidates)*100:.1f}%)")

    # 打印示例reasoning
    logger.info("\n示例评分reasoning:")
    for i, c in enumerate(scored_candidates[:3], 1):
        logger.info(f"\n候选{i}: {c.title[:60]}")
        logger.info(f"  总分: {
            c.activity_score * 0.25 +
            c.reproducibility_score * 0.30 +
            c.license_score * 0.20 +
            c.novelty_score * 0.15 +
            c.relevance_score * 0.10
        :.2f}")
        logger.info(f"  相关性: {c.relevance_score:.1f}/10")
        logger.info(f"  Reasoning: {c.reasoning[:200]}...")

    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
```

运行测试：

```bash
.venv/bin/python scripts/test_phase7_pipeline.py
```

### 性能验收清单

运行3次完整pipeline，填写以下表格：

| 指标 | Run 1 | Run 2 | Run 3 | 平均值 | 目标 | 是否达标 |
|------|-------|-------|-------|--------|------|---------|
| 采集总数 | | | | | 40-60条 | |
| 高优先级命中率 | | | | | ≥20% | |
| 平均评分 | | | | | ≥6.5 | |
| HELM采集数 | | | | | ≤15条 | |
| coding/web相关占比 | | | | | ≥60% | |

### 人工标注验证

从最终候选池中随机抽取100条，人工标注是否与MGX场景相关，填写 `docs/phase7-manual-verification.csv`:

```csv
候选标题,来源,是否相关(0/1),场景分类(coding/web/gui/agent/推理/无关)
HumanEval,GitHub,1,coding
ImageNet,arXiv,0,无关
WebArena,arXiv,1,web
...
```

计算相关性占比：

```bash
.venv/bin/python -c "
import csv
with open('docs/phase7-manual-verification.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    relevant = sum(1 for r in rows if r['是否相关(0/1)'] == '1')
    total = len(rows)
    print(f'相关候选: {relevant}/{total} = {relevant/total*100:.1f}%')
    print(f'目标: ≥60%')
    print(f'达标: {"✅" if relevant/total >= 0.6 else "❌"}')
"
```

---

## ✅ 验收清单

### 功能验收

- [ ] 修改 `config/sources.yaml` 后，下次运行立即生效
- [ ] HELM采集数从59条降至≤15条
- [ ] GitHub能识别并排除awesome list/教程/工具类仓库
- [ ] 关键词过滤能过滤纯NLP/视觉/音频等无关候选
- [ ] 各层过滤结果清晰记录在日志中
- [ ] 不影响现有飞书存储/通知功能

### 性能验收（运行3次平均值）

- [ ] 采集总数: 40-60条
- [ ] 高优先级命中率: ≥20%
- [ ] 平均评分: ≥6.5
- [ ] coding/web相关占比: ≥60%（人工标注100条）
- [ ] HELM采集数: ≤15条
- [ ] 月LLM成本: ≤¥10

### 代码质量验收

- [ ] PEP8合规: `black .` 和 `ruff check .` 无错误
- [ ] 单元测试覆盖: 新增代码覆盖率≥80%
- [ ] 中文注释: 关键逻辑有中文注释
- [ ] 常量管理: 魔法数字定义在constants或配置中
- [ ] 错误处理: API调用有超时/重试机制

### 文档验收

- [ ] 更新 `CLAUDE.md` 中的Phase 7说明
- [ ] 编写测试报告 `docs/phase7-test-report.md`
- [ ] 记录配置变更说明 `docs/phase7-config-changes.md`

---

## 📊 测试报告模板

完成开发后，请填写 `docs/phase7-test-report.md`:

```markdown
# Phase 7测试报告

**测试时间**: YYYY-MM-DD
**测试人**: Codex
**版本**: Phase 7 MGX场景聚焦优化

## 测试环境

- Python: 3.11
- 操作系统: WSL2 Ubuntu
- 虚拟环境: .venv

## 功能测试

### 配置生效测试

- [ ] 修改sources.yaml后立即生效
- [ ] 配置加载无错误

### HELM过滤测试

- 优化前: 59条
- 优化后: X条
- 过滤率: X%
- 典型过滤场景: [列举3个被过滤的场景]

### GitHub Benchmark验证测试

- 优化前: X条
- 优化后: X条
- 过滤率: X%
- 典型过滤案例:
  - awesome-ai-resources → 过滤（awesome list）
  - langchain → 过滤（框架工具）
  - HumanEval → 保留（真Benchmark）

### 关键词过滤测试

- 过滤率: X%
- 典型过滤案例:
  - ImageNet → 过滤（视觉）
  - WMT Translation → 过滤（翻译）
  - CodeXGLUE → 保留（代码）

## 性能测试

| 指标 | Run 1 | Run 2 | Run 3 | 平均值 | 目标 | 达标 |
|------|-------|-------|-------|--------|------|------|
| 采集总数 | | | | | 40-60 | |
| 高优先级命中率 | | | | | ≥20% | |
| 平均评分 | | | | | ≥6.5 | |
| coding/web占比 | | | | | ≥60% | |
| HELM采集数 | | | | | ≤15 | |

## 人工验收

抽样100条候选，标注结果:
- 相关候选: X/100 (X%)
- coding场景: X条
- web场景: X条
- gui场景: X条
- agent场景: X条
- 推理场景: X条
- 无关场景: X条

## 发现的问题

1. [问题描述]
   - 严重程度: 高/中/低
   - 修复方案: [...]

## 优化建议

1. [建议描述]

## 总结

Phase 7优化 [成功/需调优/失败]

主要改进:
- ...

待优化:
- ...
```

---

## 🚀 部署上线

验收通过后，执行以下步骤上线：

```bash
# 1. 代码格式化
black .
ruff check --fix .

# 2. 运行完整测试
.venv/bin/python -m pytest tests/ -v

# 3. Git提交
git add .
git commit -m "feat(phase7): MGX场景聚焦优化

- 数据源关键词聚焦（arXiv/GitHub/HuggingFace）
- HELM任务类型过滤（允许/排除场景配置）
- GitHub Benchmark验证（README内容分析）
- 预筛选关键词过滤（MGX场景相关性）
- LLM Prompt优化（场景分级P0/P1/P2）

性能提升:
- 采集精准度: 3.5% → X%
- 平均评分: 5.86 → X.XX
- coding/web占比: <20% → X%

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 4. 推送到GitHub（触发Actions）
git push origin main
```

---

**文档结束**

**注意事项**:
1. 严格按照本文档代码实现，不要自由发挥
2. 遇到问题先查看日志，再联系Claude Code
3. 所有测试必须通过才能上线
4. 保留旧配置备份 `config/sources.yaml.backup`

**交付清单**:
- [ ] 6个修改文件的完整代码
- [ ] 3个单元测试文件
- [ ] 1个集成测试脚本
- [ ] 1份测试报告
- [ ] 1份配置变更文档
