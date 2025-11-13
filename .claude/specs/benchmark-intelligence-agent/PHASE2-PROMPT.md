# BenchScope Phase 2: 功能增强开发指令

## 当前状态 ✅

**Phase 1 (MVP) 已完成**：
- ✓ 多源数据采集 (arXiv, GitHub Trending, Papers with Code)
- ✓ LLM智能评分 (gpt-4o + Redis缓存)
- ✓ 飞书多维表格存储 + SQLite降级
- ✓ 飞书Webhook通知
- ✓ GitHub Actions自动化
- ✓ 仓库已部署: https://github.com/JasonRobertDestiny/BenchScope

**代码质量**：
- 单元测试覆盖
- PEP8规范
- 完整文档
- 成本优化 (¥1/月)

---

## Phase 2 目标

在MVP基础上增强以下能力：

### 1️⃣ 数据源扩展
- **HuggingFace Hub**: 监控新增Benchmark数据集
- **Leaderboard追踪**: 监控MMLU、HumanEval等榜单变化
- **Twitter监控**: 关键词实时追踪 (可选)

### 2️⃣ 性能优化
- **并发采集**: asyncio.gather优化，10x提速
- **批量写入**: 飞书API批量优化 (20→100条/批)
- **增量更新**: 避免重复采集已处理数据

### 3️⃣ 智能增强
- **相似度去重**: 使用向量相似度检测重复Benchmark
- **趋势分析**: 识别研究热点和新兴方向
- **智能推荐**: 基于团队历史偏好推荐

### 4️⃣ 监控与告警
- **错误告警**: 飞书机器人推送采集失败通知
- **质量监控**: 统计每日采集成功率、评分分布
- **成本追踪**: OpenAI API使用量监控

---

## 开发任务清单

### Task 1: HuggingFace数据集监控 (优先级: 高)

**目标**: 采集HuggingFace上新增的Benchmark相关数据集

**实现要点**:
```python
# src/collectors/huggingface_collector.py
from huggingface_hub import HfApi, DatasetFilter

class HuggingFaceCollector:
    async def collect(self) -> list[RawCandidate]:
        """采集HuggingFace Benchmark数据集"""
        api = HfApi()
        datasets = api.list_datasets(
            filter=DatasetFilter(task_categories=["text-generation", "question-answering"]),
            search="benchmark OR evaluation",
            sort="lastModified",
            limit=50
        )

        candidates = []
        for ds in datasets:
            if self._is_benchmark_dataset(ds):
                candidates.append(self._to_candidate(ds))

        return candidates

    def _is_benchmark_dataset(self, dataset) -> bool:
        """判断是否为Benchmark数据集"""
        # 检查关键词: benchmark, evaluation, test set
        # 检查README内容
        # 检查下载量 >100
        pass
```

**依赖**: `huggingface_hub>=0.20.0`

**配置**:
```yaml
# config/sources.yaml
huggingface:
  keywords: ["benchmark", "evaluation", "leaderboard"]
  task_categories: ["text-generation", "question-answering", "code"]
  min_downloads: 100
  update_interval: "daily"
```

**验证**:
- [ ] 能够采集到最新Benchmark数据集
- [ ] 正确提取标题、描述、下载量
- [ ] 过滤掉非Benchmark数据集

---

### Task 2: 排行榜变化追踪 (优先级: 高)

**目标**: 监控Papers with Code排行榜SOTA变化

**实现要点**:
```python
# src/tracker/leaderboard_tracker.py
class LeaderboardTracker:
    async def track_changes(self, task: str) -> list[LeaderboardChange]:
        """追踪排行榜变化"""
        current = await self._fetch_leaderboard(task)
        previous = await self._load_from_cache(task)

        changes = []
        for metric in current.metrics:
            if metric.value != previous.get(metric.name):
                changes.append(LeaderboardChange(
                    task=task,
                    metric=metric.name,
                    old_value=previous.get(metric.name),
                    new_value=metric.value,
                    model=metric.model_name,
                    timestamp=datetime.now()
                ))

        await self._save_to_cache(task, current)
        return changes
```

**追踪任务**:
- MMLU (多任务语言理解)
- HumanEval (代码生成)
- GSM8K (数学推理)
- MATH (数学问题)
- SWE-bench (软件工程)

**通知格式**:
```
🏆 排行榜更新 - MMLU
🥇 新纪录: GPT-4.5 达到 92.3% (+2.1%)
📈 超越: GPT-4 (90.2%)
📅 更新时间: 2025-11-13
```

**验证**:
- [ ] 能够检测到SOTA变化
- [ ] 通知包含新旧对比
- [ ] 缓存避免重复检查

---

### Task 3: 并发采集优化 (优先级: 中)

**目标**: 采集速度从串行20分钟 → 并发5分钟

**实现要点**:
```python
# src/main.py
async def main():
    """并发采集流程"""
    collectors = [
        ArxivCollector(),
        GitHubCollector(),
        PwCCollector(),
        HuggingFaceCollector(),  # 新增
    ]

    # 并发采集
    results = await asyncio.gather(
        *[collector.collect() for collector in collectors],
        return_exceptions=True  # 容错
    )

    # 合并结果
    all_candidates = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"采集器 {collectors[i].__class__.__name__} 失败: {result}")
        else:
            all_candidates.extend(result)

    # 并发评分 (批量10个)
    scorer = LLMScorer()
    scored = []
    for batch in batched(all_candidates, 10):  # Python 3.12+
        scored.extend(await asyncio.gather(
            *[scorer.score(c) for c in batch]
        ))

    # 批量存储 (100条/批)
    storage = StorageManager()
    await storage.batch_save(scored, batch_size=100)
```

**性能目标**:
- 采集时间: <5分钟
- LLM评分并发度: 10 (受API限制)
- 飞书批量写入: 100条/批

**验证**:
- [ ] 总执行时间 <10分钟
- [ ] API限流正确处理
- [ ] 并发错误不影响其他采集器

---

### Task 4: 向量去重 (优先级: 中)

**目标**: 检测重复或高度相似的Benchmark

**实现要点**:
```python
# src/dedup/vector_dedup.py
from sentence_transformers import SentenceTransformer

class VectorDeduplicator:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.threshold = 0.85  # 相似度阈值

    async def deduplicate(self, candidates: list[RawCandidate]) -> list[RawCandidate]:
        """向量去重"""
        if not candidates:
            return []

        # 编码所有候选
        texts = [f"{c.title} {c.abstract}" for c in candidates]
        embeddings = self.model.encode(texts, show_progress_bar=False)

        # 计算相似度矩阵
        from sklearn.metrics.pairwise import cosine_similarity
        sim_matrix = cosine_similarity(embeddings)

        # 贪心去重
        keep = []
        used = set()
        for i, candidate in enumerate(candidates):
            if i in used:
                continue
            keep.append(candidate)
            # 标记相似项
            for j in range(i+1, len(candidates)):
                if sim_matrix[i][j] > self.threshold:
                    used.add(j)
                    logger.info(f"去重: {candidates[j].title} (与 {candidate.title} 相似度 {sim_matrix[i][j]:.2f})")

        return keep
```

**依赖**: `sentence-transformers>=2.2.0`, `scikit-learn>=1.3.0`

**验证**:
- [ ] 能够识别高度相似的Benchmark
- [ ] 去重率合理 (10-20%)
- [ ] 不误删真正不同的Benchmark

---

### Task 5: 错误告警系统 (优先级: 低)

**目标**: 采集失败时飞书告警

**实现要点**:
```python
# src/notifier/error_notifier.py
class ErrorNotifier:
    async def notify_failure(self, error: Exception, context: dict):
        """发送错误告警"""
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "⚠️ BenchScope 采集失败"}},
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**错误类型**: {type(error).__name__}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**错误信息**: {str(error)}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**采集器**: {context['collector']}"}},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}},
                ]
            }
        }
        await self._send_card(card)
```

**触发条件**:
- 采集器连续失败3次
- LLM评分成功率 <50%
- 飞书写入失败

**验证**:
- [ ] 错误时收到告警
- [ ] 告警信息完整
- [ ] 避免告警风暴 (5分钟内最多1条)

---

### Task 6: 趋势分析 (优先级: 低)

**目标**: 识别研究热点

**实现要点**:
```python
# src/analytics/trend_analyzer.py
class TrendAnalyzer:
    async def analyze_trends(self, days=30) -> list[Trend]:
        """分析趋势"""
        # 从SQLite读取30天数据
        candidates = await self._load_recent_candidates(days)

        # 提取关键词
        keywords = self._extract_keywords(candidates)

        # 统计频率变化
        trends = []
        for keyword, frequency in keywords.items():
            baseline = self._get_baseline_frequency(keyword, days=60)
            if frequency / baseline > 1.5:  # 增长50%+
                trends.append(Trend(
                    keyword=keyword,
                    frequency=frequency,
                    growth_rate=(frequency - baseline) / baseline,
                    related_papers=[c.title for c in candidates if keyword in c.title.lower()]
                ))

        return sorted(trends, key=lambda t: t.growth_rate, reverse=True)
```

**周报内容**:
- 本周热点关键词 Top 10
- 新兴Benchmark类型
- 研究领域分布变化

**验证**:
- [ ] 能够识别热点关键词
- [ ] 增长率计算准确
- [ ] 周报自动生成

---

## 技术规范

### 代码质量
- **类型注解**: 所有公共函数必须有类型标注
- **文档字符串**: 关键逻辑用中文注释
- **错误处理**: 使用`try-except`并记录日志
- **单元测试**: 新功能覆盖率 >80%

### 性能要求
- **并发度**: 采集器并发，评分10并发
- **超时控制**: 单次API调用 <30秒
- **缓存策略**: Redis 7天 + SQLite持久化

### 兼容性
- **向后兼容**: 不破坏Phase 1功能
- **配置隔离**: 新功能通过`config/`控制开关
- **降级策略**: 新数据源失败不影响原有采集

---

## 验证清单

Phase 2开发完成后，必须通过以下验证：

### 功能验证
- [ ] HuggingFace采集成功 (≥5个数据集)
- [ ] 排行榜变化检测正确
- [ ] 并发采集时间 <10分钟
- [ ] 向量去重率 10-20%
- [ ] 错误告警触发正常

### 性能验证
- [ ] 总执行时间 <10分钟
- [ ] LLM成本 <¥10/天
- [ ] 内存占用 <500MB
- [ ] 并发无死锁

### 质量验证
- [ ] 单元测试通过
- [ ] PEP8检查通过 (`ruff check .`)
- [ ] 类型检查通过 (`mypy src/`)
- [ ] 无安全漏洞

---

## 部署流程

### 1. 本地开发测试
```bash
# 安装新依赖
pip install -r requirements.txt

# 运行单元测试
pytest tests/ -v

# 本地测试运行
python -m src.main
```

### 2. 更新文档
- 更新 `README.md` 新功能说明
- 更新 `CLAUDE.md` 技术栈
- 创建 `docs/phase2-features.md`

### 3. 提交代码
```bash
git add .
git commit -m "feat(phase2): add HuggingFace collector and leaderboard tracking

- Add HuggingFace dataset monitoring
- Implement leaderboard change tracking for MMLU/HumanEval/etc
- Optimize with concurrent collection (5x speedup)
- Add vector-based deduplication
- Implement error notification system
- Add trend analysis for weekly reports"

git push origin main
```

### 4. GitHub Actions测试
- 手动触发workflow验证
- 检查日志确认新功能运行正常
- 验证飞书通知包含新数据源

---

## 成功标准

| 指标 | Phase 1 | Phase 2 目标 |
|------|---------|-------------|
| 数据源数量 | 3 | 5+ |
| 日采集量 | 20-50 | 50-100 |
| 执行时间 | 20分钟 | <10分钟 |
| 去重准确率 | N/A | >90% |
| 成本 | ¥1/天 | <¥5/天 |
| 自动化程度 | 数据采集 | 数据+分析+告警 |

---

## 风险提示

1. **API限流**: HuggingFace/Twitter可能有限流，需要实现退避策略
2. **成本增加**: 新数据源增加LLM评分次数，需监控成本
3. **复杂度上升**: 并发调试难度增加，需要完善日志
4. **向量计算**: sentence-transformers模型较大 (90MB)，首次下载慢

---

## 下一步行动

**立即开始 (必须)**:
1. 添加HuggingFace采集器
2. 实现并发采集优化

**近期完成 (推荐)**:
3. 排行榜追踪
4. 向量去重

**可选增强**:
5. 错误告警
6. 趋势分析

**Codex执行命令**:
```bash
# 按顺序实现Task 1-6
# 每个Task完成后运行测试
# 最后更新文档并提交
```

---

**当前仓库**: https://github.com/JasonRobertDestiny/BenchScope
**Phase 1完成度**: 100% ✅
**Phase 2目标**: 6周内完成核心功能 🚀
