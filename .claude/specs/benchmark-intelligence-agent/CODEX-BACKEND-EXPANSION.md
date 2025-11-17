# CODEX 开发指令：后端 Benchmark 扩展

**开发阶段**: Backend Benchmark Expansion (Phase 6.5)
**开发时间**: 2025-11-16
**开发者**: Codex
**验收者**: Claude Code

---

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

#### 1.2 GitHub Topics 扩展

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

    # ===== P1 - GUI/Agents (现有) =====
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

#### 1.3 HuggingFace 关键词扩展

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

**验收标准**:
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
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime
from src.models import RawCandidate
from src.config import get_settings
import logging

logger = logging.getLogger(__name__)


class TechEmpowerCollector:
    """TechEmpower Framework Benchmarks 采集器"""

    BASE_URL = "https://tfb-status.techempower.com"

    def __init__(self):
        settings = get_settings()
        config = settings.sources.get("techempower", {})
        self.enabled = config.get("enabled", True)
        self.timeout = config.get("timeout_seconds", 15)
        self.min_composite_score = config.get("min_composite_score", 50.0)

    async def collect(self) -> List[RawCandidate]:
        """采集最新一轮性能测试结果"""

        if not self.enabled:
            logger.info("TechEmpower collector 已禁用")
            return []

        try:
            candidates = []

            # Step 1: 获取最新测试轮次
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"正在获取 TechEmpower 最新测试轮次...")

                runs_resp = await client.get(f"{self.BASE_URL}/runs")
                runs_resp.raise_for_status()
                runs = runs_resp.json().get("runs", [])

                if not runs:
                    logger.warning("未找到任何测试轮次")
                    return []

                latest_run = runs[0]  # 最新轮次
                run_uuid = latest_run["uuid"]
                run_name = latest_run.get("name", "Unknown")
                run_date = latest_run.get("started", "")

                logger.info(f"最新轮次: {run_name} ({run_date})")

                # Step 2: 获取测试框架列表
                results_resp = await client.get(
                    f"{self.BASE_URL}/results/{run_uuid}"
                )
                results_resp.raise_for_status()
                frameworks = results_resp.json().get("frameworks", [])

                logger.info(f"共 {len(frameworks)} 个框架参与测试")

                # Step 3: 过滤并转换为候选项
                for fw in frameworks:
                    composite_score = fw.get("composite", 0)

                    # 过滤低分框架
                    if composite_score < self.min_composite_score:
                        continue

                    # 提取元数据
                    metadata = self._extract_metadata(fw, latest_run)

                    candidates.append(
                        RawCandidate(
                            title=f"TechEmpower Benchmark - {fw['name']}",
                            source="TechEmpower",
                            url=f"{self.BASE_URL}/results/{run_uuid}#{fw['name']}",
                            description=self._generate_description(fw, metadata),
                            metadata=metadata,
                        )
                    )

            logger.info(f"TechEmpower 采集完成: {len(candidates)} 条")
            return candidates

        except httpx.TimeoutException:
            logger.error(f"TechEmpower API 超时 (>{self.timeout}s)")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"TechEmpower API 请求失败: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"TechEmpower 采集异常: {e}", exc_info=True)
            return []

    def _extract_metadata(self, fw: Dict[str, Any], run_info: Dict[str, Any]) -> Dict[str, Any]:
        """提取框架元数据"""

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

    def _generate_description(self, fw: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """生成候选项描述"""

        lang = metadata["language"]
        framework_name = metadata["framework"]
        composite = metadata["composite_score"]

        desc = f"Web框架性能测试: {lang} - {framework_name} (综合得分: {composite:.1f})\n\n"

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

#### 2.2 开发 DB-Engines Collector

**文件**: `src/collectors/dbengines_collector.py`

```python
"""
DB-Engines 数据库排名采集器

DB-Engines 追踪数据库流行度排名，可以找到：
- 新兴数据库的 benchmark
- 数据库性能对比
- 数据库技术趋势

官网: https://db-engines.com/en/ranking
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from src.models import RawCandidate
from src.config import get_settings
import logging

logger = logging.getLogger(__name__)


class DBEnginesCollector:
    """DB-Engines 数据库排名采集器"""

    BASE_URL = "https://db-engines.com/en"

    def __init__(self):
        settings = get_settings()
        config = settings.sources.get("dbengines", {})
        self.enabled = config.get("enabled", True)
        self.timeout = config.get("timeout_seconds", 15)
        self.max_results = config.get("max_results", 50)

    async def collect(self) -> List[RawCandidate]:
        """采集数据库排名 + benchmark 链接"""

        if not self.enabled:
            logger.info("DB-Engines collector 已禁用")
            return []

        try:
            candidates = []

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"正在抓取 DB-Engines 排名...")

                resp = await client.get(f"{self.BASE_URL}/ranking")
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.select("table.dbi tbody tr")

                logger.info(f"找到 {len(rows)} 个数据库")

                for i, row in enumerate(rows[: self.max_results]):
                    try:
                        # 提取基本信息
                        rank_cell = row.select_one("td:nth-child(1)")
                        name_cell = row.select_one("td:nth-child(2) a")
                        type_cell = row.select_one("td:nth-child(3)")
                        score_cell = row.select_one("td:nth-child(4)")

                        if not all([rank_cell, name_cell, type_cell, score_cell]):
                            continue

                        rank = rank_cell.text.strip()
                        name = name_cell.text.strip()
                        db_type = type_cell.text.strip()
                        score = score_cell.text.strip()

                        # 构造详情页 URL
                        detail_url = name_cell.get("href", "")
                        if detail_url and not detail_url.startswith("http"):
                            detail_url = f"{self.BASE_URL}/{detail_url}"

                        metadata = {
                            "database": name,
                            "type": db_type,
                            "ranking_score": score,
                            "rank": rank,
                            "detail_url": detail_url,
                        }

                        candidates.append(
                            RawCandidate(
                                title=f"DB-Engines - {name} Performance Benchmark",
                                source="DB-Engines",
                                url=detail_url or f"{self.BASE_URL}/ranking",
                                description=self._generate_description(metadata),
                                metadata=metadata,
                            )
                        )

                    except Exception as e:
                        logger.warning(f"解析第 {i+1} 行失败: {e}")
                        continue

            logger.info(f"DB-Engines 采集完成: {len(candidates)} 条")
            return candidates

        except httpx.TimeoutException:
            logger.error(f"DB-Engines 超时 (>{self.timeout}s)")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"DB-Engines 请求失败: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"DB-Engines 采集异常: {e}", exc_info=True)
            return []

    def _generate_description(self, metadata: Dict[str, Any]) -> str:
        """生成候选项描述"""

        name = metadata["database"]
        db_type = metadata["type"]
        score = metadata["ranking_score"]
        rank = metadata["rank"]

        desc = f"{db_type} 数据库性能评测\n\n"
        desc += f"排名: #{rank}\n"
        desc += f"流行度评分: {score}\n"
        desc += f"数据库类型: {db_type}\n\n"
        desc += "DB-Engines 是追踪数据库流行度的权威平台，"
        desc += "可以找到该数据库的性能 benchmark、技术文档、使用案例。"

        return desc
```

#### 2.3 配置文件扩展

**文件**: `config/sources.yaml`

在文件末尾添加：

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

#### 2.4 集成到主流程

**文件**: `src/main.py`

修改采集器列表：

```python
from src.collectors import (
    ArxivCollector,
    GitHubCollector,
    HuggingFaceCollector,
    HelmCollector,
    TechEmpowerCollector,  # 新增
    DBEnginesCollector,    # 新增
)

async def run_collectors() -> List[RawCandidate]:
    """运行所有采集器"""

    collectors = [
        ArxivCollector(),
        GitHubCollector(),
        HuggingFaceCollector(),
        HelmCollector(),
        TechEmpowerCollector(),  # 新增
        DBEnginesCollector(),    # 新增
    ]

    all_candidates = []

    for collector in collectors:
        try:
            logger.info(f"运行 {collector.__class__.__name__}...")
            candidates = await collector.collect()
            all_candidates.extend(candidates)
            logger.info(f"  ✓ {collector.__class__.__name__}: {len(candidates)}条")
        except Exception as e:
            logger.error(f"  ✗ {collector.__class__.__name__} 失败: {e}")

    return all_candidates
```

**验收标准**:
- [ ] `src/collectors/techempower_collector.py` 开发完成
- [ ] `src/collectors/dbengines_collector.py` 开发完成
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

```python
"""
后端开发能力 Benchmark 专项评分模型

评分维度:
1. 工程实践价值 (30%) - 是否解决真实后端问题
2. 性能覆盖面 (25%) - 覆盖多少性能维度（延迟/吞吐/并发/内存）
3. 可复现性 (20%) - 是否易于复现和验证
4. 行业采用度 (15%) - GitHub stars、知名来源
5. MGX业务相关性 (10%) - 与 Vibe Coding 的关联度
"""

from typing import Dict
from src.models import RawCandidate, ScoredCandidate
import logging

logger = logging.getLogger(__name__)


class BackendBenchmarkScorer:
    """后端开发能力 benchmark 专项评分"""

    WEIGHTS = {
        "engineering_value": 0.30,     # 工程实践价值
        "performance_coverage": 0.25,  # 性能覆盖面
        "reproducibility": 0.20,       # 可复现性
        "industry_adoption": 0.15,     # 行业采用度
        "relevance": 0.10,             # MGX业务相关性
    }

    def score(self, candidate: RawCandidate) -> ScoredCandidate:
        """评分"""

        logger.debug(f"使用后端专项评分: {candidate.title}")

        scores = {
            "engineering_value": self._score_engineering_value(candidate),
            "performance_coverage": self._score_performance_coverage(candidate),
            "reproducibility": self._score_reproducibility(candidate),
            "industry_adoption": self._score_industry_adoption(candidate),
            "relevance": self._score_relevance(candidate),
        }

        # 加权总分
        total = sum(scores[dim] * self.WEIGHTS[dim] for dim in scores)

        return ScoredCandidate(
            **candidate.model_dump(),
            scores=scores,
            total_score=round(total, 2),
            priority=self._assign_priority(total),
            score_rationale=self._generate_rationale(scores),
        )

    def _score_engineering_value(self, candidate: RawCandidate) -> float:
        """工程实践价值 (0-10)

        关注是否解决真实后端问题:
        - 生产环境性能优化
        - 真实负载测试
        - 行业标准 benchmark
        - 可扩展性/可靠性/延迟优化
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

        desc_lower = (candidate.description or "").lower()
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
            stars = candidate.metadata.get("stars", 0)
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

        desc_lower = (candidate.description or "").lower()
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
        """

        score = 0.0

        # GitHub 仓库
        github_url = candidate.metadata.get("github_url", "")
        if github_url:
            score += 4.0

            # README 长度
            readme_len = candidate.metadata.get("readme_length", 0)
            if readme_len > 1000:
                score += 2.0
            elif readme_len > 500:
                score += 1.0

        # 数据集链接
        if candidate.metadata.get("dataset_url"):
            score += 2.0

        # 开源许可
        license_type = candidate.metadata.get("license", "").lower()
        if any(lic in license_type for lic in ["mit", "apache", "bsd"]):
            score += 2.0

        return min(10.0, score)

    def _score_industry_adoption(self, candidate: RawCandidate) -> float:
        """行业采用度 (0-10)

        评估行业认可度:
        - GitHub stars
        - 知名来源
        - 引用次数
        """

        # GitHub stars
        stars = candidate.metadata.get("stars", 0)
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

        # 论文引用
        citations = candidate.metadata.get("citations", 0)
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

        desc_lower = (candidate.description or "").lower()
        relevance_count = sum(1 for kw in mgx_keywords if kw in desc_lower)

        # 即使没有直接提到 AI，后端 benchmark 本身也有价值
        # 因为 MGX 最终生成的是后端代码，需要性能评测
        base_score = 5.0  # 后端 benchmark 基础分
        bonus = relevance_count * 1.5

        return min(10.0, base_score + bonus)

    def _assign_priority(self, total_score: float) -> str:
        """分配优先级"""
        if total_score >= 8.0:
            return "High"
        elif total_score >= 6.0:
            return "Medium"
        else:
            return "Low"

    def _generate_rationale(self, scores: Dict[str, float]) -> str:
        """生成评分依据"""

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

#### 3.2 修改 LLMScorer 分流逻辑

**文件**: `src/scorer/llm_scorer.py`

在文件开头导入：

```python
from src.scorer.backend_scorer import BackendBenchmarkScorer
```

在 `LLMScorer` 类的 `__init__` 方法中添加：

```python
def __init__(self):
    # 现有代码...
    self.backend_scorer = BackendBenchmarkScorer()
```

修改 `score_candidate` 方法：

```python
async def score_candidate(self, candidate: RawCandidate) -> ScoredCandidate:
    """评分单个候选项"""

    # 检测是否为后端 benchmark
    if self._is_backend_benchmark(candidate):
        logger.info(f"使用后端专项评分: {candidate.title}")
        return self.backend_scorer.score(candidate)
    else:
        # 使用现有的通用评分模型
        return await self._score_with_llm(candidate)
```

在类中添加判断方法：

```python
def _is_backend_benchmark(self, candidate: RawCandidate) -> bool:
    """判断是否为后端 benchmark

    判断依据:
    1. 来源是 TechEmpower/DB-Engines → 肯定是后端
    2. 标题/描述包含 ≥2 个后端信号词 → 判定为后端
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
    desc_lower = (candidate.description or "").lower()
    title_lower = candidate.title.lower()
    combined = desc_lower + " " + title_lower

    signal_count = sum(1 for sig in backend_signals if sig in combined)

    # 至少2个后端信号才判定为后端 benchmark
    return signal_count >= 2
```

**验收标准**:
- [ ] `src/scorer/backend_scorer.py` 开发完成
- [ ] `src/scorer/llm_scorer.py` 集成完成
- [ ] 运行测试，后端候选使用后端评分模型
- [ ] 非后端候选仍使用 LLM 评分
- [ ] 后端候选平均分 6.0-7.5（不再虚高）
- [ ] High 优先级占比 30-40%
- [ ] 评分依据清晰可解释

---

## 三、测试验收标准

### 3.1 功能测试

**Phase 1 验收**:

```bash
# 1. 修改配置后运行采集
.venv/bin/python -m src.main

# 2. 检查日志
tail -100 logs/$(ls -t logs/ | head -n1) | grep -i backend

# 3. 检查飞书表格
# 验证是否出现后端相关候选，来源包含 GitHub/arXiv
```

**期望结果**:
- GitHub 采集到 ≥3 个后端 topic 仓库
- arXiv 采集到 ≥1 篇后端论文
- 总候选数增加 20-30%

---

**Phase 2 验收**:

```bash
# 1. 运行采集
.venv/bin/python -m src.main

# 2. 检查新采集器日志
tail -100 logs/$(ls -t logs/ | head -n1) | grep -E "(TechEmpower|DB-Engines)"

# 3. 检查飞书表格
# 验证是否出现 TechEmpower/DB-Engines 来源的候选
```

**期望结果**:
- TechEmpower 采集到 ≥5 个框架
- DB-Engines 采集到 ≥10 个数据库
- 飞书表格正常写入
- 飞书通知包含新来源

---

**Phase 3 验收**:

```bash
# 1. 运行采集
.venv/bin/python -m src.main

# 2. 检查评分模型使用
tail -100 logs/$(ls -t logs/ | head -n1) | grep "使用后端专项评分"

# 3. 导出飞书表格数据，分析评分分布
.venv/bin/python scripts/analyze_feishu_data.py

# 4. 对比新旧评分差异
```

**期望结果**:
- 后端候选使用后端评分模型（日志有"使用后端专项评分"）
- 后端候选平均分 6.0-7.5
- High 优先级占比 30-40%
- 评分依据包含"工程实践价值"、"性能覆盖面"等维度

---

### 3.2 性能测试

| 指标 | 现状 | Phase 1 | Phase 2 | Phase 3 |
|------|------|---------|---------|---------|
| 采集时间 | ~80s | ~90s | ~120s | ~120s |
| 候选数/次 | 20-30 | 25-40 | 35-50 | 35-50 |
| 后端占比 | <5% | 10-15% | 25-35% | 30-40% |

**验收标准**:
- [ ] 采集时间 < 180s
- [ ] 后端候选占比 ≥30%
- [ ] 采集成功率 >95%

---

### 3.3 质量测试

**手动验证**:

1. 随机抽取 10 个后端候选
2. 检查是否真正评估后端开发能力
3. 评分是否合理

**验收标准**:
- [ ] 真实后端 benchmark 占比 ≥80%
- [ ] 评分依据清晰可解释
- [ ] 优先级分配合理

---

## 四、代码质量要求

### 4.1 PEP8 规范

- 使用 `black` 格式化
- 使用 `ruff` 检查
- 函数最大嵌套 ≤3 层
- 魔法数字定义在 `src/common/constants.py`

### 4.2 中文注释

关键逻辑必须写中文注释：
- 数据采集策略
- 评分模型算法
- 过滤规则

### 4.3 错误处理

- 所有网络请求必须有超时
- 所有异常必须捕获并记录日志
- 采集器失败不影响其他采集器

### 4.4 日志规范

```python
logger.info(f"TechEmpower 采集完成: {len(candidates)} 条")
logger.warning(f"DB-Engines 超时 (>{self.timeout}s)")
logger.error(f"采集异常: {e}", exc_info=True)
```

---

## 五、交付清单

### Phase 1 交付物

- [ ] 修改后的 `config/sources.yaml`
- [ ] 运行日志
- [ ] 飞书表格截图
- [ ] 后端候选样例（≥3个）

### Phase 2 交付物

- [ ] `src/collectors/techempower_collector.py`
- [ ] `src/collectors/dbengines_collector.py`
- [ ] 修改后的 `src/main.py`
- [ ] 修改后的 `config/sources.yaml`
- [ ] 运行日志
- [ ] 飞书表格截图
- [ ] TechEmpower 候选样例（≥5个）
- [ ] DB-Engines 候选样例（≥10个）

### Phase 3 交付物

- [ ] `src/scorer/backend_scorer.py`
- [ ] 修改后的 `src/scorer/llm_scorer.py`
- [ ] 运行日志
- [ ] 评分对比分析（新旧模型）
- [ ] 飞书表格截图
- [ ] 评分依据样例（≥5个）

---

## 六、开发建议

### 6.1 渐进式开发

1. **先做 Phase 1**（最小改动）
   - 验证假设：扩充关键词是否有效
   - 成本低，风险小

2. **Phase 1 成功后再做 Phase 2**
   - 如果 Phase 1 就能采集足够多后端候选 → 暂停
   - 如果效果不佳 → 继续 Phase 2

3. **最后做 Phase 3**
   - 如果评分明显不合理 → 上 Phase 3
   - 如果现有评分可接受 → 暂缓

### 6.2 测试驱动

每完成一个 Phase，立即测试：

```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志
tail -100 logs/$(ls -t logs/ | head -n1)

# 检查飞书表格
# 手动登录飞书多维表格，查看新增候选
```

### 6.3 错误处理优先

- 网络请求必须有超时和重试
- 异常必须捕获并记录
- 采集器失败不影响主流程

### 6.4 日志清晰

```python
logger.info(f"正在获取 TechEmpower 最新测试轮次...")
logger.info(f"最新轮次: {run_name} ({run_date})")
logger.info(f"共 {len(frameworks)} 个框架参与测试")
logger.info(f"TechEmpower 采集完成: {len(candidates)} 条")
```

---

## 七、常见问题

### Q1: TechEmpower API 超时怎么办？

**A**: 增加超时时间，添加重试：

```python
timeout_seconds: 20  # 从 15s 增加到 20s
max_retries: 3
```

### Q2: DB-Engines 网页结构变化怎么办？

**A**: 添加结构校验，失败时记录日志：

```python
if not all([rank_cell, name_cell, type_cell, score_cell]):
    logger.warning(f"第 {i+1} 行结构异常，跳过")
    continue
```

### Q3: 后端评分模型过于激进/保守？

**A**: 调整权重参数：

```python
WEIGHTS = {
    "engineering_value": 0.30,     # 可调整
    "performance_coverage": 0.25,
    "reproducibility": 0.20,
    "industry_adoption": 0.15,
    "relevance": 0.10,
}
```

### Q4: 后端候选被误判为通用候选？

**A**: 扩充 `backend_signals` 列表：

```python
backend_signals = [
    "backend",
    "api",
    # ... 添加更多信号词
]
```

---

## 八、验收流程

1. **Codex 提交代码** → `.claude/specs/benchmark-intelligence-agent/PHASE-BACKEND-IMPLEMENTATION.md`
2. **Claude Code 审核代码** → 检查代码质量、错误处理、日志
3. **Claude Code 执行测试** → 运行采集、检查飞书表格、分析日志
4. **Claude Code 编写测试报告** → `docs/phase-backend-test-report.md`
5. **验收通过/打回修改**

---

**开始开发前，请确认已理解以上所有要求。**

**有任何疑问，请在开发文档中提出。**
