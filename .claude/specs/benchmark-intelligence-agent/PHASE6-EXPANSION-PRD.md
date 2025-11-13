# Phase 6 开发PRD：信息源扩展与数据完善

**文档版本**: v1.0
**创建时间**: 2025-11-13
**目标**: 扩展信息源覆盖，完善数据字段，提升采集质量
**预计工期**: 2-3周
**负责人**: Claude Code (规划) + Codex (实现)

---

## 问题诊断

### Phase 2-5实施后的问题

基于2025-11-13的Pipeline测试（logs/pipeline_test_20251113.log），发现以下问题：

#### 1. 信息源覆盖不足 (严重度: P0)

**当前状态**:
- ✅ arXiv (但不稳定，本次测试0条)
- ✅ GitHub (15条，但质量不符合预期)
- ✅ HuggingFace (0条，过滤过严)
- ❌ ACL Anthology
- ❌ NeurIPS/ICLR/ICML Proceedings
- ❌ 评测榜单 (PwC已移除，其它榜单未接入)
- ❌ 社交媒体 (Twitter/X)
- ❌ 团队线索 (飞书群聊/Slack)

**影响**:
- 只能覆盖30%的Benchmark来源（arXiv + GitHub）
- 错过高质量会议论文（ACL/NeurIPS等）
- 错过评测榜单（HELM/EvalPlus/LMSys等）
- 依赖人工补充社媒和团队线索

#### 2. 采集质量问题 (严重度: P0)

**测试发现**:
```
采集到的GitHub仓库示例:
- awesome-selfhosted/awesome-selfhosted (awesome list)
- donnemartin/system-design-primer (教程)
- Significant-Gravitas/AutoGPT (Agent框架)
- avelino/awesome-go (awesome list)
- ollama/ollama (模型运行工具)
```

**问题分析**:
- 关键词"benchmark"太宽泛，匹配到非评测项目
- GitHub搜索未限定Benchmark特征（如包含评估脚本、数据集、Leaderboard）
- 预筛选规则未过滤awesome lists和工具类仓库

**影响**:
- 噪音率>80%（15条中仅2-3条是真Benchmark）
- 浪费LLM评分成本
- 研究员筛选负担重

#### 3. 数据字段不完整 (严重度: P1)

**当前飞书表格字段**:
```
标题, 来源, URL, 摘要, 活跃度, 可复现性, 许可合规,
任务新颖性, MGX适配度, 总分, 优先级, 评分依据, 状态
```

**缺失字段**:
- 论文URL (与GitHub仓库URL分离)
- 数据集URL (已采集dataset_url但未写入)
- 复现脚本URL (未提取)
- 评估指标 (如Accuracy/F1/BLEU)
- 开源时间 (已采集publish_date但未写入)
- GitHub stars (已采集但未��入)
- 作者信息 (已采集但未写入)
- 任务类型 (如"Code Generation", "QA"等分类)
- License类型 (已评分但未写入具体类型)

**影响**:
- 研究员需要手动补充关键信息
- 无法快速判断Benchmark可用性
- 不符合原始PRD"一键添加"的目标

#### 4. 评分准确性问题 (严重度: P2)

**测试结果**:
- 平均分: 8.61/10 (过高)
- 高优先级: 13/15 (86.7%)
- 中优先级: 2/15 (13.3%)
- 低优先级: 0/15 (0%)

**问题分析**:
- LLM对awesome lists也打高分（因为stars高、文档完善）
- 没有区分"工具"和"Benchmark"
- MGX适配度评分过于宽松

---

## 目标与范围

### 总体目标

1. **信息源完整性**: 覆盖≥80%的Benchmark来源
2. **采集质量**: 真实Benchmark占比≥60%（当前<20%）
3. **数据完整性**: 补全所有PRD要求的字段
4. **自动化程度**: 减少人工补录工作量50%

### Phase 6 范围

**核心任务**:
1. 扩展会议论文采集 (ACL/NeurIPS/ICLR/ICML)
2. 接入评测榜单 (HELM/EvalPlus/Open LLM Leaderboard)
3. 优化GitHub搜索策略 (排除awesome lists)
4. 完善飞书表格字段
5. 优化预筛选规则和评分Prompt

**可选任务**:
1. 社交媒体监听 (Twitter/X)
2. 团队线索集成 (飞书群聊/Slack)
3. HuggingFace Spaces采集

---

## 详细需求

### Task 6.1: 扩展会议论文采集器 (P0)

#### 需求背景
当前仅有arXiv采集器，且不稳定（本次测试0条）。需要覆盖顶会论文源。

#### 实现方案

**方案A: ACL Anthology API** (推荐)
- **数据源**: https://aclanthology.org/
- **API**: ACL Anthology提供JSON导出
- **覆盖会议**: ACL, EMNLP, NAACL, CoNLL等
- **更新频率**: 会议结束后1-2周
- **优点**: 官方API稳定，元数据完整
- **缺点**: 仅覆盖NLP领域

**方案B: Semantic Scholar API** (推荐)
- **数据源**: https://www.semanticscholar.org/
- **API**: https://api.semanticscholar.org/
- **覆盖会议**: NeurIPS, ICLR, ICML, ACL, CVPR等全领域
- **关键字过滤**: "benchmark", "evaluation", "dataset"
- **优点**: 覆盖广、API免费、元数据丰富（引用数、作者）
- **缺点**: 需要API key（免费额度100请求/5分钟）

**方案C: OpenReview API**
- **数据源**: https://openreview.net/
- **API**: https://api.openreview.net/
- **覆盖会议**: ICLR, NeurIPS (部分), ICML (部分)
- **优点**: 包含review信息
- **缺点**: 仅覆盖部分会议

**推荐组合**: Semantic Scholar (主) + ACL Anthology (NLP补充)

#### 采集器设计

**文件**: `src/collectors/semantic_scholar_collector.py`

```python
class SemanticScholarCollector:
    """Semantic Scholar 采集器 (覆盖多领域会议论文)"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.venues = [
            "NeurIPS", "ICLR", "ICML", "ACL", "EMNLP",
            "CVPR", "ICCV", "KDD", "WWW"
        ]
        self.keywords = [
            "benchmark", "evaluation", "dataset",
            "leaderboard", "test set"
        ]
        self.lookback_years = 2  # 最近2年论文

    async def collect(self) -> List[RawCandidate]:
        """采集最近2年会议论文中包含benchmark关键词的论文"""
        candidates = []

        for venue in self.venues:
            query = f'venue:{venue} AND ({" OR ".join(self.keywords)})'
            params = {
                'query': query,
                'year': f'{datetime.now().year - self.lookback_years}-',
                'fields': 'paperId,title,abstract,authors,year,venue,citationCount,url',
                'limit': 100
            }

            papers = await self._search_papers(query, params)
            candidates.extend(self._to_raw_candidates(papers))

        return candidates

    def _to_raw_candidates(self, papers: List[dict]) -> List[RawCandidate]:
        """转换为统一数据结构"""
        candidates = []
        for paper in papers:
            candidate = RawCandidate(
                title=paper['title'],
                url=paper['url'],
                source='semantic_scholar',
                abstract=paper.get('abstract'),
                authors=[a['name'] for a in paper.get('authors', [])],
                publish_date=datetime(paper['year'], 1, 1),
                raw_metadata={
                    'paper_id': paper['paperId'],
                    'venue': paper['venue'],
                    'citation_count': paper.get('citationCount', 0)
                }
            )
            candidates.append(candidate)
        return candidates
```

**配置常量** (`src/common/constants.py`):
```python
# Semantic Scholar配置
SEMANTIC_SCHOLAR_LOOKBACK_YEARS: Final[int] = 2
SEMANTIC_SCHOLAR_VENUES: Final[List[str]] = [
    "NeurIPS", "ICLR", "ICML", "ACL", "EMNLP",
    "CVPR", "ICCV", "KDD", "WWW"
]
SEMANTIC_SCHOLAR_KEYWORDS: Final[List[str]] = [
    "benchmark", "evaluation", "dataset",
    "leaderboard", "test set"
]
```

#### 验收标准

```bash
# 1. 单元测试
pytest tests/unit/test_semantic_scholar_collector.py -v

# 2. 手动测试
python << 'EOF'
import asyncio
from src.collectors.semantic_scholar_collector import SemanticScholarCollector

async def test():
    collector = SemanticScholarCollector(api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"))
    candidates = await collector.collect()
    print(f"采集到 {len(candidates)} 条会议论文")
    for c in candidates[:5]:
        print(f"- {c.title} ({c.raw_metadata['venue']} {c.publish_date.year})")

asyncio.run(test())
EOF

# 预期输出: 20-50条近2年会议论文
```

---

### Task 6.2: 接入评测榜单 (P0)

#### 需求背景
Papers with Code已移除，需要接入其它主流榜单。

#### 目标榜单

| 榜单 | 覆盖领域 | API可用性 | 优先级 |
|------|---------|-----------|--------|
| [HELM](https://crfm.stanford.edu/helm/) | 语言模型综合评测 | ✅ 有API | P0 |
| [Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard) | LLM排行榜 | ✅ HF API | P0 |
| [EvalPlus](https://evalplus.github.io/) | Code Generation | ✅ GitHub数据 | P1 |
| [LMSys Chatbot Arena](https://chat.lmsys.org/) | 对话模型 | ❌ 仅网页 | P2 |
| [Big-Bench](https://github.com/google/BIG-bench) | 多任务评测 | ✅ GitHub | P2 |

#### 实现方案

**方案A: HELM Leaderboard Scraper**

```python
class HELMCollector:
    """HELM评测榜单采集器"""

    def __init__(self):
        self.base_url = "https://crfm.stanford.edu/helm/latest/"
        self.scenarios_url = f"{self.base_url}?groups=1"

    async def collect(self) -> List[RawCandidate]:
        """采集HELM评测场景"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.scenarios_url)
            soup = BeautifulSoup(resp.text, 'html.parser')

            scenarios = self._parse_scenarios(soup)
            return [self._to_candidate(s) for s in scenarios]

    def _parse_scenarios(self, soup) -> List[dict]:
        """解析HELM场景列表"""
        # 实现HTML解析逻辑
        # 提取: scenario name, description, metrics, datasets
        pass

    def _to_candidate(self, scenario: dict) -> RawCandidate:
        return RawCandidate(
            title=f"HELM: {scenario['name']}",
            url=f"https://crfm.stanford.edu/helm/latest/?scenario={scenario['id']}",
            source='helm',
            abstract=scenario['description'],
            raw_metadata={
                'metrics': scenario['metrics'],
                'datasets': scenario['datasets']
            }
        )
```

**方案B: Open LLM Leaderboard (HuggingFace API)**

```python
class OpenLLMLeaderboardCollector:
    """Open LLM Leaderboard采集器"""

    def __init__(self):
        self.space_id = "HuggingFaceH4/open_llm_leaderboard"
        self.api_url = "https://huggingface.co/api/spaces/{}/discussions"

    async def collect(self) -> List[RawCandidate]:
        """采集榜单中的评测任务"""
        # 方法1: 解析Leaderboard页面
        # 方法2: 从Space的README提取benchmark信息
        # 方法3: 查询使用的评测数据集
        pass
```

#### 验收标准

```bash
# 1. HELM采集测试
python << 'EOF'
import asyncio
from src.collectors.helm_collector import HELMCollector

async def test():
    collector = HELMCollector()
    candidates = await collector.collect()
    print(f"HELM场景: {len(candidates)} 个")
    for c in candidates[:3]:
        print(f"- {c.title}")
        print(f"  Metrics: {c.raw_metadata['metrics']}")

asyncio.run(test())
EOF

# 预期输出: 50+ HELM评测场景
```

---

### Task 6.3: 优化GitHub搜索策略 (P0)

#### 问题分析

**当前问题**:
```
搜索query: "benchmark in:name,description,readme"
结果: awesome-selfhosted, system-design-primer, AutoGPT (非Benchmark)
```

**根本原因**:
1. 关键词过于宽泛
2. 未排除awesome lists
3. 未验证仓库是否包含评测代码

#### 优化方案

**方案A: 增强搜索query**

```python
# 当前query (Phase 3)
query = f"{topic} benchmark in:name,description,readme pushed:>={lookback_date}"

# 优化后query
exclude_terms = "-awesome -tutorial -guide -course -book"
required_features = "evaluation OR leaderboard OR metrics"
query = (
    f"{topic} benchmark {exclude_terms} "
    f"({required_features}) "
    f"in:name,description,readme "
    f"pushed:>={lookback_date}"
)
```

**方案B: 后处理过滤**

```python
def _is_benchmark_repo(self, repo: dict, readme: str) -> bool:
    """严格验证是否为Benchmark仓库"""

    # 1. 排除awesome lists
    if "awesome" in repo['name'].lower():
        return False

    # 2. 检查README关键词
    benchmark_indicators = [
        'evaluation', 'benchmark', 'leaderboard',
        'test set', 'metrics', 'performance'
    ]
    if not any(kw in readme.lower() for kw in benchmark_indicators):
        return False

    # 3. 检查仓库结构 (需要包含评测代码)
    required_files = ['eval', 'benchmark', 'test', 'evaluate']
    has_eval_code = any(
        pattern in readme.lower()
        for pattern in required_files
    )

    # 4. 排除纯工具类仓库
    tool_keywords = ['framework', 'library', 'sdk', 'api']
    if any(kw in repo['description'].lower() for kw in tool_keywords):
        if not has_eval_code:
            return False

    return True
```

#### 验收标准

```bash
# 运行优化后的采集器
python src/main.py

# 检查采集结果
# 预期: 真实Benchmark占比 ≥ 60% (当前<20%)
```

---

### Task 6.4: 完善飞书表格字段 (P1)

#### 当前字段vs需求对比

| 字段 | 当前状态 | 需求 | 操作 |
|------|---------|------|------|
| 标题 | ✅ | ✅ | 保留 |
| 来源 | ✅ | ✅ | 保留 |
| URL | ✅ | ✅ | 保留 |
| 摘要 | ✅ | ✅ | 保留 |
| **论文URL** | ❌ | ✅ | **新增** |
| **数据集URL** | ❌ (已采集未写入) | ✅ | **新增** |
| **复现脚本URL** | ❌ | ✅ | **新增** |
| **评估指标** | ❌ | ✅ | **新增** |
| **开源时间** | ❌ (已采集未写入) | ✅ | **新增** |
| **GitHub Stars** | ❌ (已采集未写入) | ✅ | **新增** |
| **作者** | ❌ (已采集未写入) | ✅ | **新增** |
| **任务类型** | ❌ | ✅ | **新增** |
| **License** | ❌ (仅评分) | ✅ | **新增** |
| 活跃度 | ✅ | ✅ | 保留 |
| 可复现性 | ✅ | ✅ | 保留 |
| 许可合规 | ✅ | ✅ | 保留 |
| 任务新颖性 | ✅ | ✅ | 保留 |
| MGX适配度 | ✅ | ✅ | 保留 |
| 总分 | ✅ | ✅ | 保留 |
| 优先级 | ✅ | ✅ | 保留 |
| 评分依据 | ✅ | ✅ | 保留 |
| 状态 | ✅ | ✅ | 保留 |

#### 实现方案

**Step 1: 扩展数据模型**

```python
@dataclass(slots=True)
class ScoredCandidate:
    # ... 现有字段 ...

    # 新增字段
    paper_url: Optional[str] = None          # 论文URL (独立于github_url)
    reproduction_script_url: Optional[str] = None  # 复现脚本URL
    evaluation_metrics: Optional[List[str]] = None  # 评估指标列表
    task_type: Optional[str] = None          # 任务类型 (Code/QA/Reasoning等)
    license_type: Optional[str] = None       # 具体License类型
```

**Step 2: 更新飞书存储字段映射**

```python
FIELD_MAPPING: Dict[str, str] = {
    # 现有字段...
    "paper_url": "论文URL",
    "dataset_url": "数据集URL",
    "reproduction_script_url": "复现脚本URL",
    "evaluation_metrics": "评估指标",
    "publish_date": "开源时间",
    "github_stars": "GitHub Stars",
    "authors": "作者",
    "task_type": "任务类型",
    "license_type": "License",
}

def _to_feishu_record(self, candidate: ScoredCandidate) -> dict:
    fields = {
        # ... 现有字段 ...

        # 新增字段
        self.FIELD_MAPPING["paper_url"]: {"link": candidate.paper_url} if candidate.paper_url else "",
        self.FIELD_MAPPING["dataset_url"]: {"link": candidate.dataset_url} if candidate.dataset_url else "",
        self.FIELD_MAPPING["reproduction_script_url"]: {"link": candidate.reproduction_script_url} if candidate.reproduction_script_url else "",
        self.FIELD_MAPPING["evaluation_metrics"]: ", ".join(candidate.evaluation_metrics or []),
        self.FIELD_MAPPING["publish_date"]: candidate.publish_date.strftime("%Y-%m-%d") if candidate.publish_date else "",
        self.FIELD_MAPPING["github_stars"]: candidate.github_stars or 0,
        self.FIELD_MAPPING["authors"]: ", ".join(candidate.authors or [])[:100],  # 限制长度
        self.FIELD_MAPPING["task_type"]: candidate.task_type or "Unknown",
        self.FIELD_MAPPING["license_type"]: candidate.license_type or "Unknown",
    }
    return {"fields": fields}
```

**Step 3: LLM提取逻辑**

```python
# 在src/scorer/llm_scorer.py中增强提取逻辑

extraction_prompt = """
请从以下Benchmark候选中提取关键信息:

标题: {title}
来源: {source}
摘要: {abstract}
GitHub README: {readme}

请提取:
1. 任务类型 (Code Generation/QA/Reasoning/Vision/Multimodal/Other)
2. 评估指标 (如Accuracy, F1, BLEU, Pass@k等)
3. 复现脚本URL (如果README中提到)
4. License类型 (MIT/Apache-2.0/GPL/BSD/Other)

以JSON格式返回:
{{
    "task_type": "...",
    "evaluation_metrics": ["...", "..."],
    "reproduction_script_url": "...",
    "license_type": "..."
}}
"""
```

#### 验收标准

```bash
# 1. 运行完整pipeline
python src/main.py

# 2. 检查飞书表格
# 访问飞书多维表格，验证所有新增字段都有数据填充

# 3. 字段完整性验证
python << 'EOF'
import sqlite3
conn = sqlite3.connect('data/benchmark.db')
cursor = conn.cursor()
cursor.execute("SELECT paper_url, dataset_url, evaluation_metrics FROM scored_candidates LIMIT 5")
for row in cursor.fetchall():
    print(row)
# 预期: 至少50%的记录有完整字段填充
EOF
```

---

### Task 6.5: 优化预筛选规则 (P1)

#### 问题分析

**当前问题**:
- 预筛选过滤率0% (本次测试15条全部通过)
- 没有区分"工具"和"Benchmark"
- awesome lists被误判为高质量候选

#### 优化方案

**新增规则: Benchmark特征检测**

```python
def _is_benchmark_candidate(candidate: RawCandidate) -> bool:
    """严格验证是否为Benchmark候选"""

    # 1. 排除awesome lists
    if "awesome" in candidate.title.lower():
        logger.debug("排除awesome list: %s", candidate.title)
        return False

    # 2. 检查标题/摘要关键词
    benchmark_keywords = [
        'benchmark', 'evaluation', 'leaderboard',
        'test set', 'dataset', 'metrics'
    ]
    text = f"{candidate.title} {candidate.abstract or ''}".lower()
    if not any(kw in text for kw in benchmark_keywords):
        logger.debug("缺少benchmark关键词: %s", candidate.title)
        return False

    # 3. 排除纯工具类项目 (需要同时包含benchmark关键词)
    tool_keywords = ['framework', 'library', 'sdk', 'api', 'tool']
    is_tool = any(kw in text for kw in tool_keywords)
    has_benchmark_feature = any(kw in text for kw in ['eval', 'test', 'benchmark'])

    if is_tool and not has_benchmark_feature:
        logger.debug("纯工具项目，非benchmark: %s", candidate.title)
        return False

    # 4. GitHub特殊规则: 检查README内容
    if candidate.source == 'github' and candidate.abstract:
        readme = candidate.abstract.lower()

        # 必须包含评测相关内容
        eval_indicators = ['accuracy', 'f1', 'precision', 'recall', 'performance']
        if not any(ind in readme for ind in eval_indicators):
            logger.debug("GitHub README缺少评测指标: %s", candidate.title)
            return False

    return True
```

**集成到预筛选流程**:

```python
def filter(self, candidates: List[RawCandidate]) -> List[RawCandidate]:
    """规则预筛选"""
    filtered = []

    for candidate in candidates:
        # 新增: Benchmark特征检测
        if not self._is_benchmark_candidate(candidate):
            continue

        # 现有规则: 活跃度/可复现性检查
        if candidate.source == "github":
            if not self._is_quality_github_repo(candidate):
                continue

        filtered.append(candidate)

    return filtered
```

#### 验收标准

```bash
# 运行优化后的预筛选
python src/main.py

# 检查日志
# 预期: 过滤率 30-50% (从0%提升)
# 预期: 被过滤的项目包含: awesome lists, 纯工具类项目
```

---

### Task 6.6: 优化LLM评分Prompt (P2)

#### 问题分析

**当前问题**:
- 平均分8.61/10过高
- 对awesome lists和工具类项目评分过于宽松
- MGX适配度评分不准确

#### 优化方案

**增强评分Prompt**:

```python
scoring_prompt = """
你是Benchmark评估专家。请对以下候选项进行严格评分。

候选项信息:
- 标题: {title}
- 来源: {source}
- 摘要: {abstract}
- GitHub Stars: {stars}

评分维度 (每维度0-10分):

1. 活跃度 (25%):
   - 开源时间、更新频率、社区活跃度
   - ⚠️ 注意: awesome lists通常stars很高但不是真Benchmark

2. 可复现性 (30%):
   - 是否提供代码、数据集、评估脚本
   - 文档完整性
   - ⚠️ 严格要求: 必须有完整的评测代码，不只是数据集

3. 许可合规 (20%):
   - License类型 (MIT/Apache优先)

4. 任务新颖性 (15%):
   - 是否评测新任务或新方法
   - ⚠️ 注意: 通用工具(如AutoGPT)不算Benchmark

5. MGX适配度 (10%):
   - 是否与多智能体、代码生成、Web自动化相关
   - ⚠️ 严格判断: 仅工具类项目不算适配

特殊规则:
- 如果是awesome list → 所有维度扣50%
- 如果是纯工具/框架 → 可复现性和MGX适配度扣50%
- 如果缺少评估脚本 → 可复现性最高5分

请以JSON格式返回评分和理由:
{{
    "activity_score": 7.5,
    "reproducibility_score": 8.0,
    "license_score": 9.0,
    "novelty_score": 6.5,
    "relevance_score": 7.0,
    "reasoning": "..."
}}
"""
```

#### 验收标准

```bash
# 运行优化后的评分
python src/main.py

# 检查评分分布
# 预期:
# - 平均分 6.0-7.5 (当前8.61)
# - 高优先级 30-50% (当前86.7%)
# - 中优先级 30-40% (当前13.3%)
# - 低优先级 10-30% (当前0%)
```

---

## 可选任务 (Phase 7+)

### Task 7.1: Twitter/X监听 (P2)

**需求**: 监控Twitter关键词 (#benchmark #evaluation #leaderboard)

**实现方案**:
- 使用Twitter API v2 (需要付费账号)
- 或使用nitter.net等第三方scraper
- 每日抓取最新推文
- 提取论文/GitHub链接

### Task 7.2: 飞书群聊集成 (P2)

**需求**: 团队成员在飞书群聊@机器人发送线索

**实现方案**:
- 飞书机器人接收消息
- 解析URL并加入采集队列
- 自动评分并加入候选池

### Task 7.3: HuggingFace Spaces监控 (P3)

**需求**: 监控HuggingFace Spaces中的评测应用

**实现方案**:
- 使用HF API搜索Spaces
- 过滤"benchmark", "evaluation"标签
- 提取评测数据集和指标

---

## 开发计划

### 时间安排

| 阶段 | 任务 | 工期 | 交付物 |
|------|------|------|--------|
| **Week 1** | Task 6.1 + 6.2 | 5天 | Semantic Scholar + HELM采集器 |
| **Week 2** | Task 6.3 + 6.4 | 5天 | GitHub优化 + 飞书字段扩展 |
| **Week 3** | Task 6.5 + 6.6 | 3天 | 预筛选优化 + 评分优化 |
| **Week 3** | 测试验收 | 2天 | 完整测试报告 |

### 实施步骤

1. **Claude Code**: 编写详细开发指令文档 (`.claude/specs/benchmark-intelligence-agent/CODEX-PHASE6-DETAILED.md`)
2. **Codex**: 按指令实现功能
3. **Claude Code**: 执行单元测试 + 手动测试
4. **Claude Code**: 验收并生成测试报告
5. **Git提交**: 按功能分批提交

---

## 验收标准

### 功能验收

- [ ] Semantic Scholar采集器返回20+条会议论文
- [ ] HELM采集器返回30+条评测场景
- [ ] GitHub采集真实Benchmark占比≥60% (当前<20%)
- [ ] 飞书表格包含所有新增字段 (论文URL/数据集URL等)
- [ ] 预筛选过滤率30-50% (当前0%)
- [ ] 评分分布合理 (高:中:低 = 3:4:3)

### 质量验收

- [ ] 所有单元测试通过
- [ ] 完整pipeline测试通过
- [ ] 手动验证飞书表格数据正确性
- [ ] 测试报告完整 (包含真实数据截图)

### 文档验收

- [ ] 更新README.md (新增数据源说明)
- [ ] 更新CLAUDE.md (Phase 6完成状态)
- [ ] 创建测试报告 (docs/phase6-test-report.md)
- [ ] Git commit符合规范

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Semantic Scholar API限流 | 中 | 高 | 增加重试逻辑 + Redis缓存 |
| HELM网页结构变化 | 低 | 中 | 增加HTML解析容错 |
| 飞书字段迁移失败 | 低 | 高 | 先在测试表格验证 |
| arXiv持续超时 | 高 | 中 | 增加Semantic Scholar覆盖 |

---

## 成本估算

| 项目 | 单价 | 数量 | 月成本 |
|------|------|------|--------|
| Semantic Scholar API | 免费 | - | ¥0 |
| LLM评分 (gpt-4o-mini) | ¥0.001/请求 | ~500次/日 | ¥15 |
| GitHub Actions | 免费 | 2000分钟/月 | ¥0 |
| Redis (可选) | ¥9.9/月 | 1实例 | ¥10 |
| **总计** | - | - | **¥25/月** |

---

## 参考文档

- [Semantic Scholar API文档](https://api.semanticscholar.org/)
- [HELM评测框架](https://crfm.stanford.edu/helm/)
- [Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard)
- [ACL Anthology](https://aclanthology.org/)
- [OpenReview API](https://docs.openreview.net/)

---

**文档结束**
