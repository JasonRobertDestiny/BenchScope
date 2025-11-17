# CODEX 完整开发指令：后端 Benchmark 扩展 + LLM 评分保障

**开发阶段**: Backend Expansion + LLM Scoring Guarantee (Complete)
**开发时间**: 2025-11-16
**开发者**: Codex
**验收者**: Claude Code

**核心目标**:
1. 让 BenchScope 能够采集后端开发能力相关的 benchmark（后端候选占比 <5% → 30-40%）
2. 保证每个候选都成功调用 LLM 评分（成功率 70-80% → ≥95%）

---

# 第一部分：后端 Benchmark 扩展

## 一、任务目标

让 BenchScope 能够采集到**后端开发能力**相关的 benchmark，扩展系统覆盖范围。

**当前问题**:
- 现有配置聚焦代码生成/Web自动化/多智能体
- 完全没有覆盖后端开发能力 benchmark
- 导致后端工程师无法从系统中找到有价值的评测资源

**目标**:
- 扩充关键词，覆盖后端开发领域
- 新增 2 个专项数据源（TechEmpower、DB-Engines）
- 开发后端专项评分模型
- 后端候选占比从 <5% 提升到 30-40%

---

## 二、实施方案（渐进式三阶段）

### Phase 1: 配置扩充（最小改动）

**目标**: 验证能否通过扩充关键词找到后端 benchmark

**改动文件**: `config/sources.yaml`

#### 1.1 arXiv 关键词扩展

**位置**: 行 8-42

```yaml
arxiv:
  enabled: true
  max_results: 50
  lookback_hours: 168  # 7天窗口
  timeout_seconds: 10
  max_retries: 3

  keywords:
    # ===== P0 - 编程与代码 (现有) =====
    - code generation benchmark
    - code evaluation
    - programming benchmark
    - software engineering benchmark
    - program synthesis evaluation
    - code completion benchmark

    # ===== P0 - Web自动化 (现有) =====
    - web agent benchmark
    - browser automation benchmark
    - web navigation evaluation
    - GUI automation benchmark

    # ===== P1 - 多智能体 (现有) =====
    - multi-agent benchmark
    - agent collaboration evaluation
    - tool use benchmark
    - API usage benchmark

    # ===== 新增：后端开发能力 =====
    - backend development benchmark
    - API design benchmark
    - RESTful API evaluation
    - GraphQL performance benchmark
    - database query benchmark
    - SQL optimization benchmark
    - microservices benchmark
    - distributed systems benchmark
    - system design evaluation
    - backend framework benchmark
    - server performance benchmark
    - web framework comparison

  categories:
    - cs.SE  # Software Engineering
    - cs.AI  # Artificial Intelligence
    - cs.CL  # Computation and Language
    - cs.DC  # Distributed Computing (新增)
    - cs.DB  # Databases (新增)
    - cs.NI  # Networking and Internet (新增)
```

**说明**:
- 新增 12 个后端相关关键词
- 新增 3 个 arXiv 分类（cs.DC/cs.DB/cs.NI）

---

#### 1.2 GitHub Topics 扩展

**位置**: 行 120-160

```yaml
github:
  enabled: true
  trending_url: "https://github.com/trending"
  search_api: "https://api.github.com/search/repositories"

  topics:
    # ===== P0 - 编程 (现有) =====
    - code-generation
    - code-benchmark
    - program-synthesis
    - coding-challenge
    - software-testing

    # ===== P0 - Web自动化 (现有) =====
    - web-automation
    - browser-automation
    - web-agent
    - selenium-testing
    - playwright

    # ===== P1 - GUI/Agent (现有) =====
    - gui-automation
    - agent-benchmark
    - multi-agent
    - llm-agent

    # ===== 新增：后端开发 =====
    - backend-benchmark
    - api-benchmark
    - database-benchmark
    - microservices-benchmark
    - distributed-systems
    - system-design
    - restful-api
    - graphql
    - performance-testing
    - load-testing
    - api-testing
    - backend-framework
    - server-benchmark
    - web-framework-benchmark
    - database-performance
    - sql-benchmark

  languages:
    - Python
    - JavaScript
    - TypeScript
    - Go          # 新增：后端常用语言
    - Java        # 新增：后端常用语言
    - Rust        # 新增：后端常用语言

  min_stars: 50
  lookback_days: 30
  timeout_seconds: 5
  token: ${GITHUB_TOKEN}

  min_readme_length: 500
  max_days_since_update: 90
```

**说明**:
- 新增 16 个后端相关 topics
- 新增 3 个后端常用语言（Go/Java/Rust）

---

#### 1.3 HuggingFace 关键词扩展

**位置**: 行 161-178

```yaml
huggingface:
  enabled: true
  api_url: "https://huggingface.co/api/datasets"

  keywords:
    - code
    - programming
    - software
    - benchmark
    # 新增：后端相关
    - backend
    - api
    - database
    - sql
    - microservices
    - system-design

  task_categories:
    - code
    - software-engineering  # 新增：更广泛

  min_downloads: 100
  max_results: 50
  lookback_days: 14
```

**说明**:
- 新增 6 个后端相关关键词
- 新增 1 个任务分类（software-engineering）

---

**Phase 1 验收标准**:
- [ ] `config/sources.yaml` 修改完成
- [ ] 运行采集后，GitHub 采集到 ≥3 个后端相关仓库
- [ ] arXiv 采集到 ≥1 篇后端相关论文
- [ ] 总候选数增加 20-30%
- [ ] 无语法错误，GitHub Actions 运行成功

---

### Phase 2: 新增专项数据源

**目标**: 稳定采集 TechEmpower、DB-Engines 等权威后端 benchmark

#### 2.1 开发 TechEmpower Collector

**文件**: `src/collectors/techempower_collector.py`

**完整代码**:

```python
"""
TechEmpower Framework Benchmarks 采集器

TechEmpower 是著名的 Web 框架性能 benchmark，评估各语言框架的：
- JSON 序列化性能
- 数据库查询性能
- 并发处理能力
- 模板渲染性能

官网: https://www.techempower.com/benchmarks/
API: https://tfb-status.techempower.com

数据流程:
1. GET /runs → 获取最新测试轮次
2. GET /results/{uuid} → 获取框架性能数据
3. 过滤低分框架 (composite_score < min_composite_score)
4. 转换为 RawCandidate
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class TechEmpowerCollector:
    """TechEmpower Framework Benchmarks 采集器"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.base_url = constants.TECHEMPOWER_BASE_URL
        self.timeout = constants.TECHEMPOWER_TIMEOUT_SECONDS
        self.min_composite_score = constants.TECHEMPOWER_MIN_COMPOSITE_SCORE

    async def collect(self) -> List[RawCandidate]:
        """采集最新一轮性能测试结果

        Returns:
            候选项列表

        Raises:
            httpx.TimeoutException: 请求超时
            httpx.HTTPStatusError: HTTP 错误
        """
        try:
            candidates = []

            # Step 1: 获取最新测试轮次
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("正在获取 TechEmpower 最新测试轮次...")

                runs_resp = await client.get(f"{self.base_url}/runs")
                runs_resp.raise_for_status()
                runs_data = runs_resp.json()

                if not runs_data or "runs" not in runs_data:
                    logger.warning("TechEmpower API 返回数据为空")
                    return []

                runs = runs_data["runs"]
                if not runs:
                    logger.warning("未找到任何测试轮次")
                    return []

                latest_run = runs[0]  # 最新轮次
                run_uuid = latest_run["uuid"]
                run_name = latest_run.get("name", "Unknown")
                run_date = latest_run.get("started", "")

                logger.info(f"最新轮次: {run_name} ({run_date})")

                # Step 2: 获取测试框架列表
                logger.info(f"正在获取测试结果...")
                results_resp = await client.get(f"{self.base_url}/results/{run_uuid}")
                results_resp.raise_for_status()
                results_data = results_resp.json()

                if not results_data or "frameworks" not in results_data:
                    logger.warning("测试结果为空")
                    return []

                frameworks = results_data["frameworks"]
                logger.info(f"共 {len(frameworks)} 个框架参与测试")

                # Step 3: 过滤并转换为候选项
                for fw in frameworks:
                    composite_score = fw.get("composite", 0)

                    # 过滤低分框架
                    if composite_score < self.min_composite_score:
                        continue

                    # 提取元数据
                    metadata = self._extract_metadata(fw, latest_run)

                    # 生成描述
                    description = self._generate_description(fw, metadata)

                    # 创建候选项
                    candidate = RawCandidate(
                        title=f"TechEmpower Benchmark - {fw['name']}",
                        source="TechEmpower",
                        url=f"{self.base_url}/results/{run_uuid}#{fw['name']}",
                        abstract=description,
                        raw_metadata=metadata,
                        github_url=fw.get("github", ""),
                        github_stars=None,  # TechEmpower 不提供 stars
                        license_type=None,
                        task_type="Backend Performance",
                        publish_date=run_date,
                    )

                    candidates.append(candidate)

            logger.info(f"TechEmpower 采集完成: {len(candidates)} 条")
            return candidates

        except httpx.TimeoutException:
            logger.error(f"TechEmpower API 超时 (>{self.timeout}s)")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"TechEmpower API 请求失败: {e.response.status_code} - {e.response.text[:200]}"
            )
            return []
        except Exception as e:
            logger.error(f"TechEmpower 采集异常: {e}", exc_info=True)
            return []

    def _extract_metadata(
        self, fw: Dict[str, Any], run_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取框架元数据

        Args:
            fw: 框架性能数据
            run_info: 测试轮次信息

        Returns:
            元数据字典
        """
        return {
            # 框架基本信息
            "language": fw.get("language", "Unknown"),
            "framework": fw.get("name", "Unknown"),
            "classification": fw.get("classification", ""),
            "approach": fw.get("approach", ""),
            # 性能指标
            "json_score": fw.get("json", 0),
            "db_score": fw.get("db", 0),
            "query_score": fw.get("query", 0),
            "fortune_score": fw.get("fortune", 0),
            "update_score": fw.get("update", 0),
            "plaintext_score": fw.get("plaintext", 0),
            "composite_score": fw.get("composite", 0),
            # 代码仓库
            "github_url": fw.get("github", ""),
            "website": fw.get("website", ""),
            # 测试轮次信息
            "benchmark_date": run_info.get("started", ""),
            "benchmark_name": run_info.get("name", ""),
        }

    def _generate_description(
        self, fw: Dict[str, Any], metadata: Dict[str, Any]
    ) -> str:
        """生成候选项描述

        Args:
            fw: 框架性能数据
            metadata: 元数据

        Returns:
            描述文本
        """
        lang = metadata["language"]
        framework_name = metadata["framework"]
        composite = metadata["composite_score"]

        desc = (
            f"Web框架性能测试: {lang} - {framework_name} (综合得分: {composite:.1f})\n\n"
        )

        desc += "性能指标:\n"
        desc += f"- JSON序列化: {metadata['json_score']:.0f} req/s\n"
        desc += f"- 数据库查询: {metadata['db_score']:.0f} req/s\n"
        desc += f"- 多查询: {metadata['query_score']:.0f} req/s\n"
        desc += f"- 数据更新: {metadata['update_score']:.0f} req/s\n"

        if metadata.get("classification"):
            desc += f"\n分类: {metadata['classification']}"

        if metadata.get("approach"):
            desc += f"\n实现方式: {metadata['approach']}"

        return desc
```

**说明**:
- 完整的错误处理（超时、HTTP 错误、数据为空）
- 详细的日志记录
- 丰富的元数据提取
- 符合 PEP8 规范

---

#### 2.2 开发 DB-Engines Collector

**文件**: `src/collectors/dbengines_collector.py`

**完整代码**:

```python
"""
DB-Engines 数据库排名采集器

DB-Engines 追踪数据库流行度排名，可以找到：
- 新兴数据库的 benchmark
- 数据库性能对比
- 数据库技术趋势

官网: https://db-engines.com/en/ranking

数据流程:
1. GET /en/ranking → 抓取排名页面
2. 解析 HTML 表格，提取数据库信息
3. 转换为 RawCandidate
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate

logger = logging.getLogger(__name__)


class DBEnginesCollector:
    """DB-Engines 数据库排名采集器"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.base_url = constants.DBENGINES_BASE_URL
        self.timeout = constants.DBENGINES_TIMEOUT_SECONDS
        self.max_results = constants.DBENGINES_MAX_RESULTS

    async def collect(self) -> List[RawCandidate]:
        """采集数据库排名 + benchmark 链接

        Returns:
            候选项列表

        Raises:
            httpx.TimeoutException: 请求超时
            httpx.HTTPStatusError: HTTP 错误
        """
        try:
            candidates = []

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("正在抓取 DB-Engines 排名...")

                resp = await client.get(f"{self.base_url}/ranking")
                resp.raise_for_status()

                # 解析 HTML
                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.select("table.dbi tbody tr")

                if not rows:
                    logger.warning("未找到排名数据（HTML 结构可能变化）")
                    return []

                logger.info(f"找到 {len(rows)} 个数据库")

                # 遍历前 N 个
                for i, row in enumerate(rows[: self.max_results]):
                    try:
                        # 提取基本信息
                        rank_cell = row.select_one("td:nth-child(1)")
                        name_cell = row.select_one("td:nth-child(2) a")
                        type_cell = row.select_one("td:nth-child(3)")
                        score_cell = row.select_one("td:nth-child(4)")

                        if not all([rank_cell, name_cell, type_cell, score_cell]):
                            logger.debug(f"第 {i+1} 行数据不完整，跳过")
                            continue

                        rank = rank_cell.text.strip()
                        name = name_cell.text.strip()
                        db_type = type_cell.text.strip()
                        score = score_cell.text.strip()

                        # 构造详情页 URL
                        detail_url = name_cell.get("href", "")
                        if detail_url and not detail_url.startswith("http"):
                            detail_url = f"{self.base_url}/{detail_url}"

                        # 提取元数据
                        metadata = {
                            "database": name,
                            "type": db_type,
                            "ranking_score": score,
                            "rank": rank,
                            "detail_url": detail_url,
                        }

                        # 生成描述
                        description = self._generate_description(metadata)

                        # 创建候选项
                        candidate = RawCandidate(
                            title=f"DB-Engines - {name} Performance Benchmark",
                            source="DB-Engines",
                            url=detail_url or f"{self.base_url}/ranking",
                            abstract=description,
                            raw_metadata=metadata,
                            task_type="Database Performance",
                        )

                        candidates.append(candidate)

                    except Exception as e:
                        logger.warning(f"解析第 {i+1} 行失败: {e}")
                        continue

            logger.info(f"DB-Engines 采集完成: {len(candidates)} 条")
            return candidates

        except httpx.TimeoutException:
            logger.error(f"DB-Engines 超时 (>{self.timeout}s)")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"DB-Engines 请求失败: {e.response.status_code} - {e.response.text[:200]}"
            )
            return []
        except Exception as e:
            logger.error(f"DB-Engines 采集异常: {e}", exc_info=True)
            return []

    def _generate_description(self, metadata: Dict[str, Any]) -> str:
        """生成候选项描述

        Args:
            metadata: 元数据

        Returns:
            描述文本
        """
        name = metadata["database"]
        db_type = metadata["type"]
        score = metadata["ranking_score"]
        rank = metadata["rank"]

        desc = f"{db_type} 数据库性能评测\n\n"
        desc += f"排名: #{rank}\n"
        desc += f"流行度评分: {score}\n"
        desc += f"数据库类型: {db_type}\n\n"
        desc += (
            "DB-Engines 是追踪数据库流行度的权威平台，"
            "可以找到该数据库的性能 benchmark、技术文档、使用案例。"
        )

        return desc
```

**说明**:
- 使用 BeautifulSoup 解析 HTML
- 完整的错误处理
- 防御性编程（检查元素是否存在）

---

#### 2.3 配置文件扩展

**文件**: `config/sources.yaml`

**在文件末尾添加**（行 230+）：

```yaml
# ============================================================
# 后端专项数据源 (Backend-Specific Sources)
# ============================================================

techempower:
  enabled: true
  base_url: "https://tfb-status.techempower.com"
  timeout_seconds: 15
  min_composite_score: 50.0  # 过滤低分框架（满分约 1000+）

dbengines:
  enabled: true
  base_url: "https://db-engines.com/en"
  timeout_seconds: 15
  max_results: 50  # Top 50 数据库
```

---

#### 2.4 更新常量定义

**文件**: `src/common/constants.py`

**在文件末尾添加**（行 230+）：

```python
# ---- 后端专项数据源配置 ----
TECHEMPOWER_BASE_URL: Final[str] = "https://tfb-status.techempower.com"
TECHEMPOWER_TIMEOUT_SECONDS: Final[int] = 15
TECHEMPOWER_MIN_COMPOSITE_SCORE: Final[float] = 50.0

DBENGINES_BASE_URL: Final[str] = "https://db-engines.com/en"
DBENGINES_TIMEOUT_SECONDS: Final[int] = 15
DBENGINES_MAX_RESULTS: Final[int] = 50
```

---

#### 2.5 集成到主流程

**文件**: `src/main.py`

**修改点 1**: 添加 import（行 10-17）

```python
from src.collectors import (
    ArxivCollector,
    DBEnginesCollector,  # 新增
    GitHubCollector,
    HelmCollector,
    HuggingFaceCollector,
    TechEmpowerCollector,  # 新增
)
```

**修改点 2**: 添加到 collectors 列表（行 38-46）

```python
collectors = [
    ArxivCollector(settings=settings),
    # SemanticScholarCollector(),  # 暂时禁用：无API密钥
    HelmCollector(settings=settings),
    GitHubCollector(settings=settings),
    HuggingFaceCollector(settings=settings),
    TechEmpowerCollector(settings=settings),  # 新增
    DBEnginesCollector(settings=settings),  # 新增
]
```

---

**Phase 2 验收标准**:
- [ ] `src/collectors/techempower_collector.py` 开发完成
- [ ] `src/collectors/dbengines_collector.py` 开发完成
- [ ] `src/common/constants.py` 添加配置
- [ ] `config/sources.yaml` 添加配置
- [ ] `src/main.py` 集成新采集器
- [ ] 手动运行采集，TechEmpower 产生 ≥5 条候选
- [ ] 手动运行采集，DB-Engines 产生 ≥10 条候选
- [ ] 飞书表格正常写入，通知正常推送
- [ ] 无报错，日志清晰

---

### Phase 3: 后端专项评分模型

**目标**: 后端 benchmark 评分更准确，突出工程价值

#### 3.1 开发后端评分模型

**文件**: `src/scorer/backend_scorer.py`

**完整代码**:

```python
"""
后端开发能力 Benchmark 专项评分模型

评分维度:
1. 工程实践价值 (30%) - 是否解决真实后端问题
2. 性能覆盖面 (25%) - 覆盖多少性能维度（延迟/吞吐/并发/内存）
3. 可复现性 (20%) - 是否易于复现和验证
4. 行业采用度 (15%) - GitHub stars、知名来源
5. MGX业务相关性 (10%) - 与 Vibe Coding 的关联度

设计理念:
- 后端 benchmark 不强调"任务新颖性"（性能测试是标准化的）
- 强调"工程实践价值"（是否解决真实性能问题）
- 突出"性能覆盖面"（延迟、吞吐、并发、内存、数据库）
"""

from __future__ import annotations

import logging
from typing import Dict

from src.models import RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)


class BackendBenchmarkScorer:
    """后端开发能力 benchmark 专项评分"""

    WEIGHTS = {
        "engineering_value": 0.30,  # 工程实践价值
        "performance_coverage": 0.25,  # 性能覆盖面
        "reproducibility": 0.20,  # 可复现性
        "industry_adoption": 0.15,  # 行业采用度
        "relevance": 0.10,  # MGX业务相关性
    }

    def score(self, candidate: RawCandidate) -> ScoredCandidate:
        """评分

        Args:
            candidate: 原始候选项

        Returns:
            评分后的候选项
        """
        logger.debug(f"使用后端专项评分: {candidate.title}")

        # 计算各维度分数
        scores = {
            "engineering_value": self._score_engineering_value(candidate),
            "performance_coverage": self._score_performance_coverage(candidate),
            "reproducibility": self._score_reproducibility(candidate),
            "industry_adoption": self._score_industry_adoption(candidate),
            "relevance": self._score_relevance(candidate),
        }

        # 加权总分
        total = sum(scores[dim] * self.WEIGHTS[dim] for dim in scores)

        # 分配优先级
        priority = self._assign_priority(total)

        # 生成评分依据
        rationale = self._generate_rationale(scores)

        # 转换为 ScoredCandidate
        return ScoredCandidate(
            **candidate.model_dump(),
            activity_score=scores["industry_adoption"],  # 行业采用度对应活跃度
            reproducibility_score=scores["reproducibility"],
            license_score=5.0,  # 后端 benchmark 通常不关注许可证
            novelty_score=5.0,  # 后端 benchmark 不强调新颖性
            relevance_score=scores["relevance"],
            score_reasoning=rationale,
            total_score=round(total, 2),
            priority=priority,
            # 后端专项评分维度
            metrics=[],  # 后端 benchmark 可能没有标准 metrics
            baselines=[],
            task_domain="Backend",
        )

    def _score_engineering_value(self, candidate: RawCandidate) -> float:
        """工程实践价值 (0-10)

        关注是否解决真实后端问题:
        - 生产环境性能优化
        - 真实负载测试
        - 行业标准 benchmark
        - 可扩展性/可靠性/延迟优化

        Args:
            candidate: 候选项

        Returns:
            评分 (0-10)
        """
        value_keywords = [
            "production",
            "real-world",
            "industry",
            "scalability",
            "reliability",
            "latency",
            "throughput",
            "optimization",
            "monitoring",
            "performance",
        ]

        desc_lower = (candidate.abstract or "").lower()
        title_lower = candidate.title.lower()
        combined = desc_lower + " " + title_lower

        match_count = sum(1 for kw in value_keywords if kw in combined)

        # 来源加权
        if candidate.source == "TechEmpower":
            # TechEmpower 是权威后端性能 benchmark
            return min(10.0, 7.0 + match_count * 0.5)
        elif candidate.source == "DB-Engines":
            # DB-Engines 提供数据库性能参考
            return min(10.0, 6.0 + match_count * 0.5)
        elif candidate.source == "GitHub":
            stars = candidate.github_stars or 0
            if stars > 1000:
                return min(10.0, 6.0 + match_count * 0.5)
            else:
                return min(10.0, 4.0 + match_count * 0.5)
        else:
            return min(10.0, match_count * 1.0)

    def _score_performance_coverage(self, candidate: RawCandidate) -> float:
        """性能覆盖面 (0-10)

        检查覆盖多少性能维度:
        - 延迟 (latency, response time, p99, p95)
        - 吞吐 (throughput, qps, rps)
        - 并发 (concurrent, parallel, async)
        - 内存 (memory, heap, gc)
        - 数据库 (sql, query, orm)

        Args:
            candidate: 候选项

        Returns:
            评分 (0-10)
        """
        dimensions = {
            "latency": ["latency", "response time", "p99", "p95", "p50"],
            "throughput": [
                "throughput",
                "qps",
                "rps",
                "requests per second",
                "queries per second",
            ],
            "concurrency": [
                "concurrent",
                "parallel",
                "async",
                "multi-thread",
                "goroutine",
            ],
            "memory": ["memory", "heap", "gc", "allocation", "ram"],
            "database": ["sql", "query", "database", "orm", "transaction"],
        }

        desc_lower = (candidate.abstract or "").lower()
        coverage_count = sum(
            1
            for keywords in dimensions.values()
            if any(kw in desc_lower for kw in keywords)
        )

        return min(10.0, coverage_count * 2.0)

    def _score_reproducibility(self, candidate: RawCandidate) -> float:
        """可复现性 (0-10)

        评估是否易于复现:
        - GitHub 仓库
        - README 文档
        - 数据集链接
        - 开源许可

        Args:
            candidate: 候选项

        Returns:
            评分 (0-10)
        """
        score = 0.0

        # GitHub 仓库
        github_url = candidate.github_url or ""
        if github_url:
            score += 4.0

            # README 长度（从 raw_metadata 获取）
            readme_len = candidate.raw_metadata.get("readme_length", 0)
            if readme_len > 1000:
                score += 2.0
            elif readme_len > 500:
                score += 1.0

        # 数据集链接
        if candidate.dataset_url:
            score += 2.0

        # 开源许可
        license_type = (candidate.license_type or "").lower()
        if any(lic in license_type for lic in ["mit", "apache", "bsd"]):
            score += 2.0

        return min(10.0, score)

    def _score_industry_adoption(self, candidate: RawCandidate) -> float:
        """行业采用度 (0-10)

        评估行业认可度:
        - GitHub stars
        - 知名来源
        - 引用次数

        Args:
            candidate: 候选项

        Returns:
            评分 (0-10)
        """
        # GitHub stars
        stars = candidate.github_stars or 0
        if stars >= 5000:
            return 10.0
        elif stars >= 1000:
            return 8.0
        elif stars >= 500:
            return 6.0
        elif stars >= 100:
            return 4.0

        # 知名来源加分
        if candidate.source == "TechEmpower":
            return 9.0  # 权威框架性能 benchmark
        elif candidate.source == "DB-Engines":
            return 7.0  # 权威数据库排名
        elif candidate.source == "HELM":
            return 6.0

        # 论文引用（从 raw_metadata 获取）
        citations = candidate.raw_metadata.get("citations", 0)
        if citations >= 100:
            return 8.0
        elif citations >= 50:
            return 6.0
        elif citations >= 10:
            return 4.0

        return 2.0

    def _score_relevance(self, candidate: RawCandidate) -> float:
        """MGX业务相关性 (0-10)

        后端开发能力与 MGX 的 Vibe Coding 高度相关:
        - AI 生成的后端代码需要性能优化
        - Multi-Agent 系统需要后端架构设计

        Args:
            candidate: 候选项

        Returns:
            评分 (0-10)
        """
        # MGX 相关关键词
        mgx_keywords = [
            "code generation",
            "ai-generated",
            "llm",
            "automated",
            "synthesis",
            "agent",
            "multi-agent",
        ]

        desc_lower = (candidate.abstract or "").lower()
        relevance_count = sum(1 for kw in mgx_keywords if kw in desc_lower)

        # 即使没有直接提到 AI，后端 benchmark 本身也有价值
        # 因为 MGX 最终生成的是后端代码，需要性能评测
        base_score = 5.0  # 后端 benchmark 基础分
        bonus = relevance_count * 1.5

        return min(10.0, base_score + bonus)

    def _assign_priority(self, total_score: float) -> str:
        """分配优先级

        Args:
            total_score: 总分 (0-10)

        Returns:
            优先级 (high/medium/low)
        """
        if total_score >= 8.0:
            return "high"
        elif total_score >= 6.0:
            return "medium"
        else:
            return "low"

    def _generate_rationale(self, scores: Dict[str, float]) -> str:
        """生成评分依据

        Args:
            scores: 各维度分数

        Returns:
            评分依据文本
        """
        top_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:2]

        explanations = {
            "engineering_value": "工程实践价值高",
            "performance_coverage": "性能维度覆盖全面",
            "reproducibility": "易于复现",
            "industry_adoption": "行业采用度高",
            "relevance": "与MGX业务相关",
        }

        rationale = "后端能力评分: "
        rationale += ", ".join(
            f"{explanations[dim]} ({score:.1f}/10)" for dim, score in top_dims
        )

        return rationale
```

**说明**:
- 5 个专项评分维度
- 详细的 Docstring
- 符合 PEP8 规范

---

#### 3.2 修改 LLMScorer 分流逻辑

**文件**: `src/scorer/llm_scorer.py`

**修改点 1**: 添加 import（文件开头）

```python
# 在现有 import 后添加
from src.scorer.backend_scorer import BackendBenchmarkScorer
```

**修改点 2**: 在 `__init__` 中初始化（行 101-108）

```python
def __init__(self) -> None:
    self.settings = get_settings()
    api_key = self.settings.openai.api_key
    base_url = self.settings.openai.base_url
    self.client: Optional[AsyncOpenAI] = None
    if api_key:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    self.redis_client: Optional[redis.Redis] = None

    # 后端专项评分器
    self.backend_scorer = BackendBenchmarkScorer()

    # 并发控制（将在第二部分添加）
    self.semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)
```

**修改点 3**: 修改 `score` 方法（行 245-260）

在方法开头添加后端判断：

```python
async def score(self, candidate: RawCandidate) -> ScoredCandidate:
    """评分单个候选

    如果是后端 benchmark，使用后端专项评分模型。
    否则使用 LLM 评分。

    Args:
        candidate: 候选项

    Returns:
        评分后的候选项
    """
    # 检测是否为后端 benchmark
    if self._is_backend_benchmark(candidate):
        logger.info(f"使用后端专项评分: {candidate.title[:50]}")
        return self.backend_scorer.score(candidate)

    # 使用 LLM 评分（原逻辑保持不变）
    async with self.semaphore:
        extraction = await self._get_cached_score(candidate)

        if not extraction:
            if not self.client:
                logger.warning("OpenAI未配置,使用规则兜底评分")
                extraction = self._fallback_extraction(candidate)
            else:
                extraction = await self._call_llm(candidate)
                await self._set_cached_score(candidate, extraction)

        return self._to_scored_candidate(candidate, extraction)
```

**修改点 4**: 添加 `_is_backend_benchmark` 方法（在文件末尾添加）

```python
def _is_backend_benchmark(self, candidate: RawCandidate) -> bool:
    """判断是否为后端 benchmark

    判断依据:
    1. 来源是 TechEmpower/DB-Engines → 肯定是后端
    2. 标题/描述包含 ≥2 个后端信号词 → 判定为后端

    Args:
        candidate: 候选项

    Returns:
        是否为后端 benchmark
    """
    # 后端信号词
    backend_signals = [
        "backend",
        "api",
        "database",
        "microservices",
        "performance",
        "latency",
        "throughput",
        "scalability",
        "web framework",
        "rest",
        "graphql",
        "sql",
        "server",
        "distributed systems",
    ]

    # 检查来源
    if candidate.source in ["TechEmpower", "DB-Engines"]:
        return True

    # 检查标题/描述
    desc_lower = (candidate.abstract or "").lower()
    title_lower = candidate.title.lower()
    combined = desc_lower + " " + title_lower

    signal_count = sum(1 for sig in backend_signals if sig in combined)

    # 至少2个后端信号才判定为后端 benchmark
    return signal_count >= 2
```

---

**Phase 3 验收标准**:
- [ ] `src/scorer/backend_scorer.py` 开发完成
- [ ] `src/scorer/llm_scorer.py` 集成完成
- [ ] 运行测试，后端候选使用后端评分模型
- [ ] 非后端候选仍使用 LLM 评分
- [ ] 后端候选平均分 6.0-7.5（不再虚高）
- [ ] High 优先级占比 30-40%
- [ ] 评分依据清晰可解释

---

# 第二部分：LLM 评分保障机制

## 三、任务目标

保证每个候选都成功调用 LLM 评分，避免因为网络抖动、API 限流、JSON 解析失败等原因导致评分缺失。

**当前问题**:
- LLM 评分成功率 ~70-80%
- 批量评分时，个别候选失败可能影响整批
- JSON 解析失败直接降级到规则兜底（5/10 分）
- OpenAI API 限流时大量失败

**目标**:
- LLM 评分成功率 ≥95%
- 失败时智能重试（指数退避 + 严格 JSON 模式）
- 并发控制，避免 API 限流
- 失败隔离，保证其他评分不受影响

---

## 四、失败原因分析

### 1. API 限流（Rate Limit）

**现象**:
```
openai.RateLimitError: Rate limit reached for gpt-4o
```

**原因**:
- OpenAI API 限制: `gpt-4o` **10,000 TPM**
- 当前并发度: `SCORE_CONCURRENCY = 10`
- 50 个候选同时评分 → 触发限流

**解决**:
- 降低并发度: `10 → 5`
- 增加重试间隔

---

### 2. 网络超时（Timeout）

**现象**:
```
asyncio.TimeoutError: LLM调用超时
```

**原因**:
- 当前超时: `30s`
- OpenAI API 偶尔响应慢

**解决**:
- 增加超时: `30s → 60s`
- 重试时动态增加超时

---

### 3. JSON 解析失败（Parse Error）

**现象**:
```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**:
- LLM 输出包含代码块、额外文字
- 例如：`\`\`\`json\n{...}\n\`\`\``

**解决**:
- 增强 JSON 清理逻辑
- 失败时使用严格 JSON 模式重试

---

### 4. 字段校验失败（Validation Error）

**现象**:
```
ValidationError: activity_score: ensure this value is less than or equal to 10.0
```

**原因**:
- LLM 返回越界值（如 `11.0`）
- 必填字段缺失

**解决**:
- 自动修正越界值
- 补充缺失字段

---

## 五、实施方案

### Step 1: 修改配置参数

**文件**: `src/common/constants.py`

**修改位置**: 行 296-302

```python
# 原值
LLM_DEFAULT_MODEL: Final[str] = "gpt-4o"
LLM_MODEL: Final[str] = LLM_DEFAULT_MODEL
LLM_TIMEOUT_SECONDS: Final[int] = 30
LLM_CACHE_TTL_SECONDS: Final[int] = 7 * 24 * 3600
LLM_MAX_RETRIES: Final[int] = 3
LLM_COMPLETION_MAX_TOKENS: Final[int] = 2000
SCORE_CONCURRENCY: Final[int] = 10

# 修改为
LLM_DEFAULT_MODEL: Final[str] = "gpt-4o"  # 保持不变
LLM_MODEL: Final[str] = LLM_DEFAULT_MODEL
LLM_TIMEOUT_SECONDS: Final[int] = 60  # 增加超时时间 30s → 60s
LLM_CACHE_TTL_SECONDS: Final[int] = 7 * 24 * 3600
LLM_MAX_RETRIES: Final[int] = 5  # 增加重试次数 3 → 5
LLM_COMPLETION_MAX_TOKENS: Final[int] = 2000
SCORE_CONCURRENCY: Final[int] = 5  # 降低并发度 10 → 5
```

---

### Step 2: 增强重试机制

**文件**: `src/scorer/llm_scorer.py`

#### 2.1 添加 import

在文件开头添加：

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,  # 新增
    before_sleep_log,  # 新增
)
```

#### 2.2 修改 `_call_llm` 方法

**原位置**: 行 165-192

```python
# 原代码
@retry(
    stop=stop_after_attempt(constants.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _call_llm(self, candidate: RawCandidate) -> BenchmarkExtraction:
    if not self.client:
        raise RuntimeError("未配置OpenAI接口,无法调用LLM")

    prompt = self._build_prompt(candidate)
    response = await asyncio.wait_for(
        self.client.chat.completions.create(
            model=self.settings.openai.model or constants.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是MGX BenchScope的Benchmark评估专家,只能返回严格JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
        ),
        timeout=constants.LLM_TIMEOUT_SECONDS,
    )

    content = response.choices[0].message.content or ""
    logger.debug("LLM原始响应(前500字符): %s", content[:500])
    extraction = self._parse_extraction(content)
    return extraction

# 修改为
@retry(
    # 只重试可恢复的错误
    retry=retry_if_exception_type((
        asyncio.TimeoutError,
    )),
    stop=stop_after_attempt(constants.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _call_llm(
    self,
    candidate: RawCandidate,
    attempt: int = 1,
) -> BenchmarkExtraction:
    """调用 LLM 评分（带智能重试）

    Args:
        candidate: 候选项
        attempt: 当前重试次数（用于动态调整超时）

    Returns:
        评分结果

    Raises:
        RuntimeError: OpenAI 未配置
        json.JSONDecodeError: JSON 解析失败（会触发严格 JSON 重试）
        ValidationError: 字段校验失败（会尝试自动修正）
    """
    if not self.client:
        raise RuntimeError("未配置OpenAI接口,无法调用LLM")

    # 动态超时：首次 60s，第 2 次 90s，第 3 次 120s
    timeout = constants.LLM_TIMEOUT_SECONDS + (attempt - 1) * 30

    prompt = self._build_prompt(candidate)

    try:
        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.settings.openai.model or constants.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是MGX BenchScope的Benchmark评估专家,只能返回严格JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
            ),
            timeout=timeout,
        )

        content = response.choices[0].message.content or ""
        logger.debug("LLM原始响应(前500字符): %s", content[:500])

        extraction = self._parse_extraction(content)
        return extraction

    except json.JSONDecodeError as exc:
        # JSON 解析失败 → 使用严格 JSON 模式重试
        logger.warning(
            "LLM 返回非法 JSON (尝试 %d/%d): %s",
            attempt,
            constants.LLM_MAX_RETRIES,
            exc,
        )

        if attempt < constants.LLM_MAX_RETRIES:
            # 重新调用，强调 JSON 格式
            logger.info("使用严格 JSON 模式重试...")
            return await self._call_llm_strict_json(candidate, attempt + 1)
        else:
            # 最后一次也失败了，抛出异常
            raise

    except ValidationError as exc:
        # 字段校验失败 → 尝试自动修正
        logger.warning("LLM 返回字段校验失败: %s，尝试自动修正...", exc)
        return self._fix_validation_error(content, exc)
```

#### 2.3 新增 `_call_llm_strict_json` 方法

在 `_call_llm` 方法之后添加：

```python
async def _call_llm_strict_json(
    self,
    candidate: RawCandidate,
    attempt: int,
) -> BenchmarkExtraction:
    """调用 LLM（严格 JSON 模式）

    当普通模式返回非法 JSON 时，使用此方法重试。
    强调：不要代码块、不要额外文字、只返回纯 JSON。

    Args:
        candidate: 候选项
        attempt: 当前重试次数

    Returns:
        评分结果
    """
    if not self.client:
        raise RuntimeError("未配置OpenAI接口")

    timeout = constants.LLM_TIMEOUT_SECONDS + (attempt - 1) * 30

    # 强调 JSON 格式的 System Prompt
    system_prompt = """你是MGX BenchScope的Benchmark评估专家。

【关键要求】
1. 只能返回纯JSON，不能有任何其他文字
2. 不要用代码块包裹（不要 ```json ```）
3. 所有字段必须存在，不能缺失
4. 分数必须在 0-10 之间

如果返回格式错误，将导致评分失败！"""

    prompt = self._build_prompt(candidate)
    prompt += "\n\n【再次提醒】只返回纯JSON，不要任何解释或代码块！"

    response = await asyncio.wait_for(
        self.client.chat.completions.create(
            model=self.settings.openai.model or constants.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,  # 降低随机性
            max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
        ),
        timeout=timeout,
    )

    content = response.choices[0].message.content or ""
    logger.debug("严格JSON模式响应: %s", content[:500])

    return self._parse_extraction(content)
```

#### 2.4 新增 `_fix_validation_error` 方法

在 `_call_llm_strict_json` 方法之后添加：

```python
def _fix_validation_error(
    self,
    content: str,
    validation_error: ValidationError,
) -> BenchmarkExtraction:
    """自动修正 LLM 返回的字段错误

    修正策略:
    1. 越界分数 → 裁剪到 [0, 10]
    2. 缺失必填字段 → 补默认值

    Args:
        content: LLM 原始响应
        validation_error: Pydantic 校验错误

    Returns:
        修正后的评分结果

    Raises:
        ValidationError: 修正失败
    """
    try:
        payload = json.loads(self._strip_code_fence(content))

        # 修正越界分数（裁剪到 [0, 10]）
        score_fields = [
            "activity_score",
            "reproducibility_score",
            "license_score",
            "novelty_score",
            "relevance_score",
        ]

        for field in score_fields:
            if field in payload:
                value = payload[field]
                if isinstance(value, (int, float)):
                    original = value
                    payload[field] = max(0.0, min(10.0, float(value)))
                    if original != payload[field]:
                        logger.info(
                            "修正越界分数: %s %.1f → %.1f",
                            field,
                            original,
                            payload[field],
                        )

        # 补充缺失的必填字段
        if "score_reasoning" not in payload or not payload["score_reasoning"]:
            payload["score_reasoning"] = "LLM 未提供评分依据（已自动修正）"
            logger.info("补充缺失字段: score_reasoning")

        # 确保分数字段都存在
        for field in score_fields:
            if field not in payload:
                payload[field] = 5.0
                logger.warning("补充缺失分数字段: %s = 5.0", field)

        # 重新校验
        extraction = BenchmarkExtraction.parse_obj(payload)
        logger.info("字段自动修正成功")
        return extraction

    except Exception as exc:
        logger.error("字段自动修正失败: %s", exc, exc_info=True)
        raise validation_error  # 修正失败，抛出原始错误
```

---

### Step 3: 并发控制

**文件**: `src/scorer/llm_scorer.py`

#### 3.1 在 `__init__` 中添加信号量

已在 Phase 3 中添加：

```python
self.semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)
```

#### 3.2 修改 `score` 方法使用信号量

已在 Phase 3 中修改（使用 `async with self.semaphore`）

---

### Step 4: 失败隔离

**文件**: `src/scorer/llm_scorer.py`

#### 4.1 修改 `score_batch` 方法

**原位置**: 行 339-354

```python
# 原代码
async def score_batch(
    self, candidates: List[RawCandidate]
) -> List[ScoredCandidate]:
    if not candidates:
        return []

    tasks = [self.score(candidate) for candidate in candidates]
    results = await asyncio.gather(*tasks)
    logger.info("批量评分完成: %d条", len(results))
    return list(results)

# 修改为
async def score_batch(
    self, candidates: List[RawCandidate]
) -> List[ScoredCandidate]:
    """批量评分，保证每个候选都有评分（优先 LLM，失败后规则兜底）

    使用 return_exceptions=True 确保单个候选失败不影响其他候选。

    Args:
        candidates: 候选项列表

    Returns:
        评分后的候选项列表（长度与输入相同）
    """
    if not candidates:
        return []

    logger.info("开始批量评分: %d 个候选", len(candidates))

    tasks = [self.score(candidate) for candidate in candidates]

    # return_exceptions=True: 异常不会停止其他任务
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果
    scored = []
    llm_success = 0
    backend_scorer_count = 0
    fallback_count = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # 这个候选 LLM 评分失败，使用规则兜底
            logger.error(
                "候选 #%d (%s) LLM 评分失败: %s，使用规则兜底",
                i + 1,
                candidates[i].title[:50],
                str(result),
            )

            # 强制使用规则兜底
            extraction = self._fallback_extraction(candidates[i])
            scored_candidate = self._to_scored_candidate(candidates[i], extraction)
            scored.append(scored_candidate)
            fallback_count += 1
        else:
            scored.append(result)

            # 统计评分方式
            if result.task_domain == "Backend":
                backend_scorer_count += 1
            else:
                llm_success += 1

    # 统计日志
    logger.info(
        "批量评分完成: LLM 成功 %d 条 (%.1f%%)，后端评分 %d 条 (%.1f%%)，规则兜底 %d 条 (%.1f%%)",
        llm_success,
        100 * llm_success / len(scored) if scored else 0,
        backend_scorer_count,
        100 * backend_scorer_count / len(scored) if scored else 0,
        fallback_count,
        100 * fallback_count / len(scored) if scored else 0,
    )

    # 如果兜底比例过高，发出警告
    if fallback_count > llm_success + backend_scorer_count:
        logger.warning(
            "⚠️  LLM 评分成功率低于 50%%，请检查："
            "\n  1. OpenAI API 密钥是否有效"
            "\n  2. 是否触发限流（降低 SCORE_CONCURRENCY）"
            "\n  3. 网络是否稳定"
        )

    return scored
```

---

## 六、验收标准

### 6.1 功能测试

**测试步骤**:

```bash
# 1. 运行完整流程
.venv/bin/python -m src.main

# 2. 检查日志中的评分成功率
tail -200 logs/$(ls -t logs/ | head -n1) | grep "批量评分完成"
```

**期望结果**:

```
批量评分完成: LLM 成功 35 条 (70.0%)，后端评分 13 条 (26.0%)，规则兜底 2 条 (4.0%)
```

**验收标准**:
- [ ] LLM + 后端评分成功率 ≥90%（规则兜底 <10%）
- [ ] 日志中有"使用后端专项评分"（证明后端评分生效）
- [ ] 日志中有"使用严格 JSON 模式重试"（证明重试机制生效）
- [ ] 日志中有"修正越界分数"或"补充缺失字段"（证明自动修正生效）
- [ ] 无"整批失败"现象
- [ ] 飞书表格正常写入

---

### 6.2 压力测试

**测试步骤**:

```bash
# 模拟大量候选（修改 config/sources.yaml）
arxiv:
  max_results: 100  # 从 50 增加到 100

# 运行采集
.venv/bin/python -m src.main
```

**验收标准**:
- [ ] LLM + 后端评分成功率 ≥90%（即使 100 个候选）
- [ ] 无 API 限流错误
- [ ] 评分时间 < 15 分钟

---

### 6.3 后端 Benchmark 验证

**测试步骤**:

```bash
# 1. 检查飞书表格
# 验证是否有 TechEmpower/DB-Engines 来源的候选

# 2. 检查评分模型
tail -200 logs/$(ls -t logs/ | head -n1) | grep "使用后端专项评分"
```

**验收标准**:
- [ ] TechEmpower 候选 ≥5 个
- [ ] DB-Engines 候选 ≥10 个
- [ ] 后端候选使用后端专项评分（日志有记录）
- [ ] 后端候选平均分 6.0-7.5
- [ ] 后端候选优先级分布合理（High 30-40%）

---

## 七、代码质量要求

### 7.1 PEP8 规范

- 使用 `black` 格式化：`black .`
- 使用 `ruff` 检查：`ruff check .`
- 函数最大嵌套 ≤3 层
- 魔法数字定义在 `src/common/constants.py`

### 7.2 Docstring

所有新增函数必须有 Docstring：

```python
def function_name(arg1: Type1, arg2: Type2) -> ReturnType:
    """简短描述

    详细说明（可选）

    Args:
        arg1: 参数1说明
        arg2: 参数2说明

    Returns:
        返回值说明

    Raises:
        Exception: 异常说明
    """
```

### 7.3 中文注释

关键逻辑必须写中文注释：
- 数据采集策略
- 评分模型算法
- 过滤规则
- 重试逻辑

### 7.4 日志规范

```python
logger.info("开始批量评分: %d 个候选", len(candidates))
logger.warning("LLM 返回非法 JSON (尝试 %d/%d): %s", attempt, max_retries, exc)
logger.error("候选 #%d (%s) LLM 评分失败: %s", i, title, exc)
```

---

## 八、交付清单

### Phase 1 交付物

- [ ] 修改后的 `config/sources.yaml`
- [ ] 运行日志
- [ ] 飞书表格截图
- [ ] 后端候选样例（≥3个）

### Phase 2 交付物

- [ ] `src/collectors/techempower_collector.py`
- [ ] `src/collectors/dbengines_collector.py`
- [ ] 修改后的 `src/common/constants.py`
- [ ] 修改后的 `config/sources.yaml`
- [ ] 修改后的 `src/main.py`
- [ ] 运行日志
- [ ] 飞书表格截图
- [ ] TechEmpower 候选样例（≥5个）
- [ ] DB-Engines 候选样例（≥10个）

### Phase 3 交付物

- [ ] `src/scorer/backend_scorer.py`
- [ ] 修改后的 `src/scorer/llm_scorer.py`
- [ ] 运行日志
- [ ] 评分对比分析
- [ ] 飞书表格截图

### LLM 评分保障交付物

- [ ] 修改后的 `src/common/constants.py`
- [ ] 修改后的 `src/scorer/llm_scorer.py`
- [ ] 功能测试日志（成功率 ≥90%）
- [ ] 压力测试报告（100 个候选）
- [ ] 重试机制验证（日志中有"严格 JSON 模式"）

---

## 九、常见问题

### Q1: TechEmpower API 超时怎么办？

**A**: 增加超时时间：

```python
TECHEMPOWER_TIMEOUT_SECONDS: Final[int] = 20  # 从 15s 增加到 20s
```

### Q2: DB-Engines 网页结构变化怎么办？

**A**: 检查 HTML 结构，调整选择器：

```python
# 如果选择器失效，需要重新分析 HTML
rows = soup.select("新的选择器")
```

### Q3: 后端评分模型过于激进/保守？

**A**: 调整权重参数：

```python
WEIGHTS = {
    "engineering_value": 0.30,  # 可调整
    "performance_coverage": 0.25,
    "reproducibility": 0.20,
    "industry_adoption": 0.15,
    "relevance": 0.10,
}
```

### Q4: LLM 评分成功率仍然不高？

**A**: 检查配置：

1. 增加重试次数：`LLM_MAX_RETRIES = 7`
2. 增加超时：`LLM_TIMEOUT_SECONDS = 90`
3. 进一步降低并发：`SCORE_CONCURRENCY = 3`

### Q5: 后端候选被误判为通用候选？

**A**: 扩充 `backend_signals` 列表：

```python
backend_signals = [
    "backend",
    "api",
    # ... 添加更多信号词
    "web server",
    "http server",
    "framework performance",
]
```

---

## 十、验收流程

1. **Codex 提交代码** → 在开发文档中说明所有修改点
2. **Claude Code 审核代码** → 检查代码质量、错误处理、日志
3. **Claude Code 执行测试** → 运行功能测试、压力测试、后端验证
4. **Claude Code 编写测试报告** → `docs/backend-expansion-test-report.md`
5. **验收通过/打回修改**

---

## 十一、开发顺序建议

**建议按以下顺序开发**（渐进式）：

1. **Phase 1**: 配置扩充（15分钟）
   - 修改 `config/sources.yaml`
   - 立即测试，验证效果

2. **Phase 2**: 新增数据源（2-3小时）
   - 开发 `TechEmpowerCollector`
   - 开发 `DBEnginesCollector`
   - 集成到主流程
   - 测试采集

3. **LLM 评分保障**（1-2小时）
   - 修改 `constants.py`
   - 增强 `llm_scorer.py`
   - 测试评分成功率

4. **Phase 3**: 后端评分模型（1-2小时）
   - 开发 `backend_scorer.py`
   - 集成到 `llm_scorer.py`
   - 测试后端评分

**总开发时间**: 4-8 小时

---

**开始开发前，请确认已理解以上所有要求。如有疑问，请在开发文档中提出。**
