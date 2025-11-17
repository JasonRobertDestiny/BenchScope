# Backend Benchmark 扩展方案

**目标**: 让 BenchScope 能够采集到后端开发能力相关的 benchmark

**当前问题**: 现有配置聚焦代码生成/Web自动化/多智能体，完全没覆盖后端开发能力

---

## 一、后端开发能力 Benchmark 应该包含什么？

### 1. 系统设计与架构能力
- 微服务架构设计
- 分布式系统设计
- API设计 (REST/GraphQL/gRPC)
- 数据库schema设计
- 缓存策略设计

### 2. 性能与优化能力
- API响应时间优化
- 数据库查询优化 (SQL/NoSQL)
- 并发处理 (多线程/异步)
- 内存管理
- 负载均衡

### 3. 后端框架与技术栈
- Web框架 (Django/Flask/FastAPI/Express/Spring Boot)
- ORM使用 (SQLAlchemy/Prisma/Hibernate)
- 消息队列 (Redis/RabbitMQ/Kafka)
- 认证授权 (OAuth/JWT/Session)
- 容器化部署 (Docker/Kubernetes)

### 4. 工程实践
- 错误处理与异常管理
- 日志记录与监控
- 单元测试与集成测试
- CI/CD流程
- 文档编写

---

## 二、扩展方案 (渐进式)

### 方案A: 最小改动 - 扩充关键词 (15分钟)

**改动范围**: 仅修改 `config/sources.yaml`

#### 1. arXiv 关键词扩展

```yaml
arxiv:
  keywords:
    # 现有关键词保持不变
    - code generation benchmark
    - web agent benchmark
    - multi-agent benchmark

    # 新增：后端开发能力
    - backend development benchmark
    - API design benchmark
    - database query benchmark
    - microservices benchmark
    - distributed systems benchmark
    - system design evaluation
    - RESTful API benchmark
    - GraphQL performance
    - backend framework benchmark

  # 扩展分类
  categories:
    - cs.SE  # Software Engineering
    - cs.AI  # Artificial Intelligence
    - cs.CL  # Computation and Language
    - cs.DC  # Distributed Computing (新增)
    - cs.DB  # Databases (新增)
    - cs.NI  # Networking and Internet (新增)
```

#### 2. GitHub Topics 扩展

```yaml
github:
  topics:
    # 现有topics保持不变
    - code-generation
    - web-automation
    - agent-benchmark

    # 新增：后端开发
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
```

#### 3. HuggingFace 关键词扩展

```yaml
huggingface:
  keywords:
    # 现有关键词保持不变
    - code
    - programming

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
```

**预期效果**:
- 增加后端相关候选项 30-50%
- GitHub采集到 TechEmpower、API Benchmark 等仓库
- arXiv采集到分布式系统评测论文
- 实施成本: 修改配置文件 → 重新运行采集器

---

### 方案B: 中等改动 - 新增后端专项数据源 (2-3天)

**改动范围**: 新增 collector + 修改配置

#### 1. 新增 TechEmpower Collector

TechEmpower 是著名的 Web 框架性能 benchmark：
- https://www.techempower.com/benchmarks/
- 评估各语言框架的 API 性能 (JSON序列化、数据库查询、并发处理)

**实现**:

```python
# src/collectors/techempower_collector.py

import httpx
from typing import List
from src.models import RawCandidate
from src.config import get_settings

class TechEmpowerCollector:
    """TechEmpower Framework Benchmarks 采集器"""

    BASE_URL = "https://tfb-status.techempower.com"

    async def collect(self) -> List[RawCandidate]:
        """采集最新一轮性能测试结果"""

        # 获取最新测试轮次
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_URL}/runs")
            latest_run = resp.json()["runs"][0]

            # 获取测试框架列表
            frameworks_resp = await client.get(
                f"{self.BASE_URL}/results/{latest_run['uuid']}"
            )
            frameworks = frameworks_resp.json()["frameworks"]

        candidates = []
        for fw in frameworks:
            candidates.append(RawCandidate(
                title=f"TechEmpower Benchmark - {fw['name']}",
                source="TechEmpower",
                url=f"{self.BASE_URL}/results/{latest_run['uuid']}#{fw['name']}",
                description=f"Web框架性能测试: {fw['language']} - {fw['name']}",
                metadata={
                    "language": fw["language"],
                    "framework": fw["name"],
                    "json_score": fw.get("json", 0),
                    "db_score": fw.get("db", 0),
                    "composite_score": fw.get("composite", 0),
                    "github_url": fw.get("github"),
                }
            ))

        return candidates
```

#### 2. 新增 DB-Engines Collector

DB-Engines 追踪数据库流行度排名：
- https://db-engines.com/en/ranking
- 可以找到新兴数据库的 benchmark

**实现**:

```python
# src/collectors/dbengines_collector.py

import httpx
from bs4 import BeautifulSoup
from typing import List
from src.models import RawCandidate

class DBEnginesCollector:
    """DB-Engines 数据库排名采集器"""

    BASE_URL = "https://db-engines.com/en"

    async def collect(self) -> List[RawCandidate]:
        """采集数据库排名 + benchmark 链接"""

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_URL}/ranking")
            soup = BeautifulSoup(resp.text, "html.parser")

            rows = soup.select("table.dbi tbody tr")

        candidates = []
        for row in rows[:50]:  # Top 50
            name = row.select_one("td:nth-child(2) a").text.strip()
            db_type = row.select_one("td:nth-child(3)").text.strip()
            score = row.select_one("td:nth-child(4)").text.strip()

            # 尝试获取 benchmark 链接
            detail_url = f"{self.BASE_URL}/{name.lower().replace(' ', '-')}"

            candidates.append(RawCandidate(
                title=f"DB-Engines - {name} Performance Benchmark",
                source="DB-Engines",
                url=detail_url,
                description=f"{db_type} 数据库性能评测",
                metadata={
                    "database": name,
                    "type": db_type,
                    "ranking_score": score,
                }
            ))

        return candidates
```

#### 3. 配置文件扩展

```yaml
# config/sources.yaml

techempower:
  enabled: true
  base_url: "https://tfb-status.techempower.com"
  timeout_seconds: 15
  min_composite_score: 50.0  # 过滤低分框架

dbengines:
  enabled: true
  base_url: "https://db-engines.com/en"
  timeout_seconds: 15
  max_results: 50
```

**预期效果**:
- 每月采集到 Web 框架性能 benchmark
- 追踪新兴数据库的性能评测
- 发现 API/数据库优化相关资源
- 实施成本: 2-3天开发 + 测试

---

### 方案C: 完整方案 - 后端能力评分模型 (1-2周)

**改动范围**: 新增 scorer + 修改评分逻辑

#### 问题：现有评分模型不适合后端 benchmark

现有 5 维评分 (`src/scorer/llm_scorer.py`):
1. 活跃度 (25%) - GitHub stars/commits
2. 可复现性 (30%) - 代码/数据集开源
3. 许可合规 (20%) - MIT/Apache/BSD
4. 任务新颖性 (15%) - 与已有任务重叠度
5. MGX适配度 (10%) - LLM判断业务相关性

**问题**:
- 后端 benchmark 可能没有 GitHub 仓库 (如 TechEmpower 官网)
- "任务新颖性"不适用于性能测试
- 缺少"工程实践价值"维度

#### 方案：新增后端专项评分模型

```python
# src/scorer/backend_scorer.py

from typing import Dict
from src.models import RawCandidate, ScoredCandidate

class BackendBenchmarkScorer:
    """后端开发能力 benchmark 专项评分"""

    WEIGHTS = {
        "engineering_value": 0.30,    # 工程实践价值
        "performance_coverage": 0.25,  # 性能覆盖面
        "reproducibility": 0.20,       # 可复现性
        "industry_adoption": 0.15,     # 行业采用度
        "relevance": 0.10,             # MGX业务相关性
    }

    def score(self, candidate: RawCandidate) -> ScoredCandidate:
        """评分"""

        scores = {
            "engineering_value": self._score_engineering_value(candidate),
            "performance_coverage": self._score_performance_coverage(candidate),
            "reproducibility": self._score_reproducibility(candidate),
            "industry_adoption": self._score_industry_adoption(candidate),
            "relevance": self._score_relevance(candidate),
        }

        # 加权总分
        total = sum(
            scores[dim] * self.WEIGHTS[dim]
            for dim in scores
        )

        return ScoredCandidate(
            **candidate.model_dump(),
            scores=scores,
            total_score=total,
            priority=self._assign_priority(total),
            score_rationale=self._generate_rationale(scores),
        )

    def _score_engineering_value(self, candidate: RawCandidate) -> float:
        """工程实践价值 (0-10)"""

        # 关键词匹配
        value_keywords = [
            "production", "real-world", "industry",
            "scalability", "reliability", "latency",
            "throughput", "optimization", "monitoring",
        ]

        desc_lower = candidate.description.lower()
        match_count = sum(1 for kw in value_keywords if kw in desc_lower)

        # 来源加权
        if candidate.source == "TechEmpower":
            return min(10.0, 7.0 + match_count * 0.5)
        elif candidate.source == "GitHub" and candidate.metadata.get("stars", 0) > 1000:
            return min(10.0, 6.0 + match_count * 0.5)
        else:
            return min(10.0, match_count * 1.0)

    def _score_performance_coverage(self, candidate: RawCandidate) -> float:
        """性能覆盖面 (0-10)"""

        # 检查覆盖哪些性能维度
        dimensions = {
            "latency": ["latency", "response time", "p99", "p95"],
            "throughput": ["throughput", "qps", "rps", "requests per second"],
            "concurrency": ["concurrent", "parallel", "async", "multi-thread"],
            "memory": ["memory", "heap", "gc", "allocation"],
            "database": ["sql", "query", "database", "orm"],
        }

        desc_lower = candidate.description.lower()
        coverage = sum(
            1 for keywords in dimensions.values()
            if any(kw in desc_lower for kw in keywords)
        )

        return min(10.0, coverage * 2.0)

    def _score_reproducibility(self, candidate: RawCandidate) -> float:
        """可复现性 (0-10)"""

        score = 0.0

        # GitHub 仓库
        if candidate.metadata.get("github_url"):
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
        """行业采用度 (0-10)"""

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
        if candidate.source in ["TechEmpower", "DB-Engines"]:
            return 7.0

        return 2.0

    def _score_relevance(self, candidate: RawCandidate) -> float:
        """MGX业务相关性 (0-10)"""

        # 后端开发能力与 MGX 的 Vibe Coding 高度相关
        # 因为 AI 生成的后端代码需要性能优化

        mgx_keywords = [
            "code generation", "ai-generated", "llm",
            "automated", "synthesis", "agent",
        ]

        desc_lower = candidate.description.lower()
        relevance = sum(1 for kw in mgx_keywords if kw in desc_lower)

        # 即使没有直接提到 AI，后端 benchmark 本身也有价值
        return max(5.0, min(10.0, 5.0 + relevance * 1.5))

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

        rationale = "后端能力评分: "

        explanations = {
            "engineering_value": "工程实践价值高",
            "performance_coverage": "性能维度覆盖全面",
            "reproducibility": "易于复现",
            "industry_adoption": "行业采用度高",
            "relevance": "与MGX业务相关",
        }

        rationale += ", ".join(
            f"{explanations[dim]} ({score:.1f}/10)"
            for dim, score in top_dims
        )

        return rationale
```

#### 集成到主流程

```python
# src/scorer/llm_scorer.py (修改)

class LLMScorer:
    def __init__(self):
        # 现有代码...
        from src.scorer.backend_scorer import BackendBenchmarkScorer
        self.backend_scorer = BackendBenchmarkScorer()

    async def score_candidate(self, candidate: RawCandidate) -> ScoredCandidate:
        """评分单个候选项"""

        # 检测是否为后端 benchmark
        if self._is_backend_benchmark(candidate):
            return self.backend_scorer.score(candidate)
        else:
            # 使用现有的通用评分模型
            return await self._score_with_llm(candidate)

    def _is_backend_benchmark(self, candidate: RawCandidate) -> bool:
        """判断是否为后端 benchmark"""

        backend_signals = [
            "backend", "api", "database", "microservices",
            "performance", "latency", "throughput", "scalability",
            "web framework", "rest", "graphql", "sql",
        ]

        desc_lower = candidate.description.lower()
        title_lower = candidate.title.lower()

        # 检查标题/描述是否包含后端关键词
        signal_count = sum(
            1 for sig in backend_signals
            if sig in desc_lower or sig in title_lower
        )

        # 检查来源
        if candidate.source in ["TechEmpower", "DB-Engines"]:
            return True

        # 至少2个后端信号才判定为后端 benchmark
        return signal_count >= 2
```

**预期效果**:
- 后端 benchmark 评分更准确
- 不再依赖"代码生成"维度
- 突出工程实践价值
- 实施成本: 1-2周开发 + 测试

---

## 三、推荐实施路径

### Phase 1: 快速验证 (本周完成)

**目标**: 验证能否找到后端 benchmark

**任务**:
1. 修改 `config/sources.yaml` (方案A)
2. 运行一次完整采集
3. 检查飞书表格，看是否出现后端相关候选

**验收标准**:
- GitHub 采集到 ≥3 个后端 benchmark 仓库
- arXiv 采集到 ≥1 篇后端性能论文
- 总候选数增加 20-30%

### Phase 2: 专项数据源 (下周完成)

**目标**: 稳定采集 TechEmpower 等权威来源

**任务**:
1. 开发 TechEmpowerCollector (方案B)
2. 开发 DBEnginesCollector (可选)
3. 集成到主流程
4. 运行测试

**验收标准**:
- TechEmpower 每月采集到 ≥5 个框架性能 benchmark
- 飞书通知包含 TechEmpower 来源
- 采集成功率 >95%

### Phase 3: 专项评分 (月底完成)

**目标**: 后端 benchmark 评分更精准

**任务**:
1. 开发 BackendBenchmarkScorer (方案C)
2. 修改 LLMScorer 分流逻辑
3. 对比新旧评分差异
4. 调整权重参数

**验收标准**:
- 后端 benchmark 平均分 6.0-7.5 (现在 8.6 明显虚高)
- High 优先级占比 30-40%
- 评分依据可解释性强

---

## 四、预期效果

### 采集覆盖面

| 维度 | 现状 | Phase 1 | Phase 2 | Phase 3 |
|------|------|---------|---------|---------|
| 后端候选数/月 | 0-2 | 5-10 | 15-25 | 20-30 |
| 数据源数量 | 5 | 5 | 7 | 7 |
| 后端相关占比 | <5% | 10-15% | 25-35% | 30-40% |

### 评分准确性

| 指标 | 现状 | Phase 3 |
|------|------|---------|
| 平均总分 | 8.61 | 6.5-7.0 |
| High 优先级 | 80% | 30-40% |
| 后端专项维度 | 无 | 5维 |

### 实施成本

| 阶段 | 开发时间 | LLM成本增加 |
|------|----------|-------------|
| Phase 1 | 1小时 | ¥0 (仅改配置) |
| Phase 2 | 2-3天 | ¥2/月 (新数据源) |
| Phase 3 | 1-2周 | ¥0 (替换LLM) |

---

## 五、关键决策点

### 决策1: 是否需要后端专项评分模型？

**权衡**:
- ✅ 优点: 评分更准确，突出工程价值
- ❌ 缺点: 增加维护成本，需要调参

**建议**:
- Phase 1/2 先用现有评分模型
- 如果发现评分明显不合理（如后端 benchmark 都是 Low 优先级），再上 Phase 3

### 决策2: TechEmpower 是否值得单独开发 collector？

**权衡**:
- ✅ 优点: 权威来源，稳定更新，数据结构化
- ❌ 缺点: 2-3天开发成本，可能只产生 5-10 个候选/年

**建议**:
- 如果团队确实需要 Web 框架性能 benchmark → 开发
- 如果只是偶尔参考 → 手动添加到飞书即可

### 决策3: 是否需要扩展到云服务性能 benchmark？

**范围扩大**:
- AWS/Azure/GCP 性能对比
- Serverless 框架 benchmark
- Kubernetes 性能测试

**建议**:
- 暂不扩展，聚焦"开发能力" benchmark
- 云服务性能属于"运维能力"，不是当前重点

---

## 六、下一步行动

**如果你同意方案A (最小改动)**:

1. 我立即修改 `config/sources.yaml`
2. 运行一次完整采集 (手动执行)
3. 检查飞书表格结果
4. 根据结果决定是否继续 Phase 2/3

**如果你倾向方案B (新增数据源)**:

1. 先讨论 TechEmpower 是否值得单独开发
2. 我设计详细的实现方案
3. 开发 → 测试 → 集成

**如果你想直接上方案C (完整方案)**:

1. 我编写完整的开发文档 (类似 CODEX-PHASE7-IMPLEMENTATION.md)
2. 使用 Codex 开发
3. 测试验收

---

**请告诉我你倾向哪个方案，我立即开始实施。**
