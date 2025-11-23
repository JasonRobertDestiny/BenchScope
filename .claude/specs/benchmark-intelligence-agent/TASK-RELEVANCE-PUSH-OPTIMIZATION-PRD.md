# 任务相关性推送优化方案（修订版）

**创建时间**: 2025-11-23
**问题等级**: P0（严重影响产品价值）
**核心目标**: 最新且任务相关、减少低质/重复、提升域覆盖（特别是Backend）

## 修订摘要（2025-11-23）
- 聚焦“最新且任务相关”，不再拆分多分区或来源精选。
- 飞书卡片格式：主标题“中优先级候选推荐”，子块仅“最新推荐”，展示完整标题+来源/领域/分数/日期，移除图片与缺失提示。
- 推送前过滤（已上线）：无日期且<8 丢弃；>30天且<8 丢弃；标题归一去重；上限12条。
- LLM 评分自愈增强：最小推理字符100，自愈重试3次，长度告警降为调试级别。
- 去重脚本已就绪但因飞书配额不足暂未执行；待配额恢复后再单独推进。

---

## 一、问题重新定义

### 1.1 数据诊断（基于1000条记录）

**来源分布**：
- arXiv: 396条 (39.6%)
- **DBEngines: 256条 (25.6%)** ← 全部缺失发布日期
- HuggingFace: 190条 (19.0%)
- HELM: 84条 (8.4%)
- GitHub: 72条 (7.2%)
- TechEmpower: 2条 (0.2%)

**任务域分布**：
- Other: 354条 (35.4%)
- **Backend: 232条 (23.2%)** ← **其中170条来自dbengines（73.3%）**
- Reasoning: 232条 (23.2%)
- Coding: 64条 (6.4%)
- Collaboration: 60条 (6.0%)
- ToolUse: 24条 (2.4%)
- WebDev/GUI/LLM Ops: 极低

**评分质量**：
- 低分 (<6): 954条 (95.4%)
- 平均分: 3.38
- **DBEngines平均分: 1.81（全部<6）**

**时间分布**：
- 最近7天: 484条 (48.4%)
- 最近30天: 132条 (13.2%)
- 无日期: 256条 (25.6%) ← 全部来自dbengines

**重复问题**：
- 重复标题: 276个（主要是HELM重复）

### 1.2 核心问题

**问题1：Backend供给严重不足，质量极低**

- Backend域73.3%依赖dbengines
- 但dbengines是"数据库排名榜单"，不是真正的benchmark
- 平均分1.81，全部<6分
- **如果禁用dbengines**：Backend域将损失73.3%供给，但保留的也全是低质量数据

**问题2：真正的后端benchmark来源缺失**

- TechEmpower仅2条（0.2%）
- 缺少：数据库性能benchmark、API性能benchmark、微服务benchmark
- 缺少：后端框架benchmark、ORM性能benchmark、缓存性能benchmark

**问题3：推送噪音高，任务相关性差**

- 95.4%低分数据
- 35.4%分类为"Other"
- 25.6%无发布日期

---

## 二、优化方案（3层防御）

### 第1层：推送层过滤与卡片（已上线）
- 过滤规则：无发布日期且分<8 丢弃；发布日期超过30天且分<8 丢弃；标题归一去重；最多12条。
- 排版：仅“最新推荐”分区，完整标题加粗，来源/领域/分数/日期一行；去掉图片与缺失提示。
- 日志降噪：LLM长度不足警告降级，Redis连接失败仅提示一次。
- 现状：平均分已抬升，卡片信息密度更高。

### 第2层：采集日期补全（待办，1-2天）
目标：将无发布日期占比从 25.6% 降到 <5%，避免被“无日期低分”过滤掉。
- dbengines：用榜单更新时间或当月1号填充 `publish_date`。
- TechEmpower：写入 round 日期。
- HuggingFace：使用 `lastModified`/`created_at`。
- 验收：再跑 `scripts/analyze_bitable.py`，无日期 <5%。

### 第3层：Backend 供给增强（待办，3-5天）
目标：替换/补强当前低质 Backend 供给，减少对 dbengines 排名的依赖。
- 重构 dbengines 采集：改采真实 benchmark（TPC-C/H、YCSB、sysbench、pgbench…），若无法完成则暂时禁用该源入库。
- 扩展 TechEmpower：抓最近3轮，多测试类型（json/db/query/fortune/update）。
- 新增 backend_benchmark_collector：按关键词在 GitHub/ArXiv 搜索数据库/微服务/API/ORM/缓存/MQ benchmark，筛活跃度≥4.5。
- 配置新增后端关键词（arxiv/github）。

### 可选：核心域补位（如后续仍有缺口再开启）
当 WebDev/GUI/ToolUse 等仍缺失时，为缺席域放宽阈值到 ≥4.5，补1条最新候选；默认关闭以保持简洁。

### 第2层：采集日期补全（1-2天）

#### 2.3 各采集器日期补全逻辑

**问题**：25.6%数据缺失发布日期（全部来自dbengines）

**方案**：在采集阶段尽量补全日期

```python
# src/collectors/dbengines_collector.py

async def collect(self) -> List[RawCandidate]:
    """采集DBEngines排名，补全发布日期"""
    candidates = []

    for db in self._fetch_rankings():
        candidate = RawCandidate(
            title=f"DB-Engines - {db['name']} Benchmark",
            source="dbengines",
            url=db["url"],
            abstract=db["description"],

            # 补全日期：使用榜单更新日期
            publish_date=self._get_ranking_update_date(),  # 新增

            # 其他字段...
        )
        candidates.append(candidate)

    return candidates

def _get_ranking_update_date(self) -> datetime:
    """获取DBEngines榜单更新日期"""
    # 方法1：从网页抓取"Last update: YYYY-MM-DD"
    # 方法2：固定为每月1日（DBEngines每月更新）
    # 方法3：使用当前日期

    # 暂用方法2：每月1日
    now = datetime.now()
    return datetime(now.year, now.month, 1)
```

**其他采集器类似逻辑**：
- **arXiv**：已有`published`字段，无需修改
- **HuggingFace**：使用`lastModified`或`created_at`
- **HELM**：使用scenario配置文件的更新日期
- **GitHub**：使用`created_at`或`updated_at`
- **TechEmpower**：使用榜单发布日期

**预期效果**：
- 无日期数据从25.6% → <5%
- 推送层过滤更准确

### 第3层：Backend Benchmark供给增强（关键）

#### 2.4 优化dbengines采集逻辑

**问题**：当前采集"数据库排名榜单"，不是真正的benchmark

**方案**：改为采集"数据库相关的benchmark"

```python
# src/collectors/dbengines_collector.py

# 当前逻辑（错误）
def collect():
    # 采集排名榜单：Oracle, MySQL, PostgreSQL...
    # 结果：全是排名，不是benchmark

# 优化后逻辑
def collect():
    """采集数据库性能benchmark（不是排名榜单）"""
    candidates = []

    # 方法1：从DBEngines的"Benchmark"页面采集
    # https://db-engines.com/en/ranking_benchmark

    # 方法2：采集知名数据库benchmark项目
    KNOWN_DB_BENCHMARKS = [
        {
            "name": "TPC-C",
            "url": "http://www.tpc.org/tpcc/",
            "description": "OLTP benchmark for database performance",
            "github": "https://github.com/tpc-c/tpc-c"
        },
        {
            "name": "TPC-H",
            "url": "http://www.tpc.org/tpch/",
            "description": "OLAP benchmark for data warehouse",
            "github": "https://github.com/tpc-h/tpc-h"
        },
        {
            "name": "YCSB",
            "url": "https://github.com/brianfrankcooper/YCSB",
            "description": "Yahoo! Cloud Serving Benchmark",
            "github": "https://github.com/brianfrankcooper/YCSB"
        },
        {
            "name": "sysbench",
            "url": "https://github.com/akopytov/sysbench",
            "description": "Database and system benchmark",
            "github": "https://github.com/akopytov/sysbench"
        },
        # ... 更多
    ]

    for benchmark in KNOWN_DB_BENCHMARKS:
        # 检查GitHub活跃度
        if self._is_active(benchmark["github"]):
            candidates.append(self._to_candidate(benchmark))

    return candidates
```

**预期效果**：
- dbengines从"排名榜单"变为"真实benchmark"
- 评分从1.81提升到5.0+

#### 2.5 新增后端benchmark来源

**新增采集器**：`src/collectors/backend_benchmark_collector.py`

```python
class BackendBenchmarkCollector:
    """专门采集后端开发benchmark"""

    BACKEND_BENCHMARKS = {
        # 数据库性能
        "database": [
            "TPC-C", "TPC-H", "YCSB", "sysbench",
            "pgbench", "mysqlslap"
        ],

        # Web框架性能（已有TechEmpower，扩展）
        "web_framework": [
            "TechEmpower Framework Benchmarks",
            "wrk", "ab", "siege", "locust"
        ],

        # API性能
        "api": [
            "httpbin", "httpstat", "hey",
            "k6", "artillery", "vegeta"
        ],

        # 微服务
        "microservices": [
            "DeathStarBench",
            "chaos-mesh",
            "Istio Performance Benchmark"
        ],

        # ORM性能
        "orm": [
            "ORMBenchmark",
            "SQLAlchemy Benchmark",
            "Prisma Benchmark"
        ],

        # 缓存性能
        "cache": [
            "Redis Benchmark",
            "Memcached Benchmark",
            "CacheBench"
        ],

        # 消息队列
        "message_queue": [
            "Kafka Performance",
            "RabbitMQ Benchmark",
            "OpenMessaging Benchmark"
        ]
    }

    async def collect(self) -> List[RawCandidate]:
        """采集后端benchmark"""
        candidates = []

        for category, benchmarks in self.BACKEND_BENCHMARKS.items():
            for benchmark_name in benchmarks:
                # 在GitHub搜索
                github_repos = await self._search_github(benchmark_name)

                # 在arXiv搜索相关论文
                arxiv_papers = await self._search_arxiv(f"{benchmark_name} performance")

                candidates.extend(self._to_candidates(github_repos, category))
                candidates.extend(self._to_candidates(arxiv_papers, category))

        return candidates
```

**预期效果**：
- Backend供给从232条 → 350+条
- Backend质量从平均2.0 → 5.5+
- 减少对dbengines低质量数据的依赖

#### 2.6 扩展TechEmpower采集

**问题**：TechEmpower仅2条（0.2%），但它是最权威的Web框架benchmark

**方案**：增加采集频率和覆盖范围

```python
# src/collectors/techempower_collector.py

async def collect(self) -> List[RawCandidate]:
    """采集TechEmpower Web框架benchmark"""
    candidates = []

    # 当前逻辑：只采集最新一轮测试
    # 优化后：采集最近3轮测试

    recent_rounds = await self._fetch_recent_rounds(count=3)

    for round_data in recent_rounds:
        # 每轮测试有多个benchmark类型
        for test_type in ["json", "db", "query", "fortune", "update"]:
            candidate = RawCandidate(
                title=f"TechEmpower - {test_type.upper()} Benchmark - Round {round_data['round']}",
                source="techempower",
                url=f"https://www.techempower.com/benchmarks/#section=data-r{round_data['round']}&test={test_type}",
                abstract=f"Web framework performance benchmark: {test_type}",
                publish_date=round_data["date"],
                task_domain=["Backend", "WebDev"],
                # ...
            )
            candidates.append(candidate)

    return candidates
```

**预期效果**：
- TechEmpower从2条 → 15条
- 覆盖更多Web框架benchmark类型

---

## 三、实施步骤（分阶段）

### 阶段1：紧急止血（今天完成）

**Step 1.1：推送层终极过滤**

```bash
# 修改 src/notifier/feishu_notifier.py
# 添加 _apply_ultimate_filter() 函数
# 在 _send_medium_priority_summary() 中调用

# 测试
.venv/bin/python -c "
import asyncio
from src.main import main
asyncio.run(main())
"

# 检查推送卡片：
# - 无超过30天的低分条目
# - 无重复标题
# - 条目数≤12
```

**Step 1.2：标题去重验证**

```bash
# 运行分析脚本
.venv/bin/python scripts/analyze_bitable.py

# 检查：重复标题数量应显著下降
```

**预期效果**：
- 推送条目从20+ → 12条
- 重复标题从276 → <50
- 平均分从3.38 → 5.0+（过滤掉低分后）

### 阶段2：日期补全（1-2天）

**Step 2.1：dbengines日期补全**

```python
# 修改 src/collectors/dbengines_collector.py
# 添加 _get_ranking_update_date() 方法
# 在 collect() 中补充 publish_date 字段
```

**Step 2.2：其他采集器日期验证**

```bash
# 检查各采集器的日期字段
.venv/bin/python -c "
import asyncio
from src.collectors import *

async def test():
    for Collector in [ArxivCollector, GitHubCollector, HuggingFaceCollector, HelmCollector]:
        collector = Collector()
        candidates = await collector.collect()

        missing_date = [c for c in candidates if c.publish_date is None]
        print(f'{Collector.__name__}: {len(missing_date)}/{len(candidates)} 缺失日期')

asyncio.run(test())
"
```

**预期效果**：
- 无日期数据从25.6% → <5%

### 阶段3：Backend供给增强（3-5天，关键）

**Step 3.1：重构dbengines采集器**

```bash
# 备份当前版本
cp src/collectors/dbengines_collector.py src/collectors/dbengines_collector.py.bak

# 重写采集逻辑（改为采集真实benchmark）
# 参考2.4节的方案
```

**Step 3.2：创建backend_benchmark_collector**

```bash
# 新建采集器
touch src/collectors/backend_benchmark_collector.py

# 实现2.5节的逻辑
# 注册到 src/collectors/__init__.py
```

**Step 3.3：扩展TechEmpower采集**

```bash
# 修改 src/collectors/techempower_collector.py
# 增加采集轮次（1轮 → 3轮）
# 增加测试类型（json/db/query/fortune/update）
```

**Step 3.4：配置启用新采集器**

```yaml
# config/sources.yaml

backend_benchmarks:
  enabled: true
  categories:
    - database
    - web_framework
    - api
    - microservices
    - orm
    - cache
    - message_queue
```

**预期效果**：
- Backend供给从232条 → 350+条
- Backend平均分从2.0 → 5.5+
- 后端benchmark覆盖7个子类别

### 阶段4：可选优化（1周后）

**Step 4.1：核心域补位**

```python
# 在 src/notifier/feishu_notifier.py 中添加
# _add_domain_backfill() 函数
# 允许低分兜底（分≥4.5）
```

**Step 4.2：采集关键词扩展**

```yaml
# config/sources.yaml

arxiv:
  keywords:
    # 当前
    - "benchmark"
    - "evaluation"

    # 新增（后端相关）
    - "database performance"
    - "API benchmark"
    - "microservices benchmark"
    - "ORM performance"
    - "cache benchmark"

github:
  topics:
    - "benchmark"
    - "performance"

    # 新增
    - "database-benchmark"
    - "api-benchmark"
    - "web-framework-benchmark"
```

---

## 四、预期效果（量化指标）

### 阶段1效果（推送层过滤后）

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| 推送条目数 | 20+ | ≤12 | -40% |
| 重复标题 | 276 | <50 | -82% |
| 推送平均分 | 3.38 | 5.0+ | +48% |
| 超过30天低分 | 多 | 0 | -100% |

### 阶段2效果（日期补全后）

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| 无日期数据 | 25.6% | <5% | -80% |
| dbengines无日期 | 100% | 0% | -100% |

### 阶段3效果（Backend增强后）

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| Backend供给 | 232条 | 350+ | +51% |
| Backend平均分 | 2.0 | 5.5+ | +175% |
| Backend来源多样性 | 主要dbengines | 7个子类别 | +600% |
| 真实Backend benchmark占比 | <30% | ≥70% | +133% |

### 最终效果（所有优化完成后）

| 指标 | 当前值 | 目标值 | 达成 |
|------|--------|--------|------|
| 整体平均分 | 3.38 | 5.5+ | ✅ |
| 推送相关性 | 低 | 高 | ✅ |
| Backend质量 | 极低 | 中高 | ✅ |
| 核心域覆盖 | 6/12 | 10/12 | ✅ |

---

## 五、成功标准与验收

### 立即验收（阶段1完成）

```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查推送卡片
# - [ ] 条目数≤12
# - [ ] 无重复标题
# - [ ] 无超过30天的低分条目
# - [ ] 平均分≥5.0

# 运行分析
.venv/bin/python scripts/analyze_bitable.py
# - [ ] 重复标题<50个
```

### 1周验收（阶段3完成）

```bash
# 检查Backend供给
.venv/bin/python << 'EOF'
import asyncio
from src.storage.feishu_storage import FeishuStorage

async def check_backend():
    storage = FeishuStorage()
    records = await storage.read_brief_records()

    backend_records = [
        r for r in records
        if r.get("task_domain") and "Backend" in r["task_domain"]
    ]

    backend_sources = {}
    for r in backend_records:
        source = r.get("source", "Unknown")
        backend_sources[source] = backend_sources.get(source, 0) + 1

    print(f"Backend总数: {len(backend_records)}")
    print("来源分布:")
    for source, count in sorted(backend_sources.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")

asyncio.run(check_backend())
