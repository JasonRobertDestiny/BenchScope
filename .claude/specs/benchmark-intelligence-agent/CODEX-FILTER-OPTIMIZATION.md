# Codex开发指令：优化预筛选过滤率（降低漏检）

## 快速执行卡
- 目标：预筛选通过率 20–35%，FP≤20%，每日新增学术基准 ≥5 条
- 立即动作：扩充关键词 + arXiv 白名单，保持 30 天窗口
- 验证：运行对比测试脚本，抽样 10 条人工复核
- 回滚：使用备份或 `git revert`，命令见后文

## 现状与根因（2025-11-22验证）

**✅ GitHub问题已解决**：
- GitHub采集器已使用 `created:>=`（首次创建时间）
- 不会再采集swebench/uitars/camel等老项目 ✅

**❌ 核心问题**：过滤率过高86.7%
- 最近运行：arXiv=50条 → 预筛选留2条（过滤率86.7%）
- GitHub=14条 → 预筛选留0条（过滤率100%）
- 主要原因：`keyword_rule` + 关键词覆盖不足

**根本原因**：
1. 关键词过少（只覆盖code/web/agent领域）
2. arXiv未在TRUSTED_SOURCES白名单（重复过滤）
3. 新学术领域（reasoning/multimodal/knowledge）无关键词覆盖

## 方案概览
- 阶段1（本次执行）：扩充关键词；arXiv 加入 `TRUSTED_SOURCES`；保持 30 天窗口
- 阶段2（本次执行）：对比测试 + 人工抽样
- 阶段3-5（后续）：LLM 自动扩词、参数微调、持续监控

## 操作手册（阶段1）

### 1) 扩充关键词
- 位置：`src/common/constants.py`
- 动作：替换 `PREFILTER_REQUIRED_KEYWORDS`

```python
PREFILTER_REQUIRED_KEYWORDS: Final[list[str]] = [
    # ====== Benchmark核心术语（通用） ======
    "benchmark", "benchmarking", "evaluation", "leaderboard", "dataset",
    "corpus", "test set", "test suite", "testbed", "baseline", "validation",
    "benchmark suite", "benchmark collection",

    # ====== Code相关 ======
    "code", "coding", "program", "programming", "software", "repository",
    "code generation", "code benchmark", "execution benchmark",

    # ====== Web/GUI ======
    "web", "browser", "gui", "ui", "automation", "web automation",

    # ====== Agent/Tool Use ======
    "agent", "multi-agent", "tool", "tool use", "api", "workflow", "planning",
    "agent benchmark",

    # ====== Backend/Performance ======
    "backend", "database", "sql", "microservices", "system-design",
    "performance", "framework", "server", "software benchmark",

    # ====== Reasoning（新增）======
    "reasoning", "logic", "logical reasoning", "chain-of-thought", "cot",
    "reasoning benchmark", "math", "mathematics", "mathematical reasoning",
    "problem solving",

    # ====== Knowledge（新增）======
    "knowledge", "question answering", "qa", "knowledge graph",
    "fact checking", "factual", "world knowledge",

    # ====== Multimodal（新增）======
    "multimodal", "vision-language", "image-text", "visual", "vision",
    "video", "audio", "speech",

    # ====== Language Understanding（新增）======
    "language", "nlp", "natural language", "text", "linguistic",
    "language understanding", "comprehension", "reading comprehension",

    # ====== Task相关（新增）======
    "task", "tasks", "challenge", "competition",
]
```

### 2) arXiv 白名单
- 位置：`src/prefilter/rule_filter.py`
- 修改：
```python
TRUSTED_SOURCES: set[str] = {"arxiv", "techempower", "dbengines", "helm"}
```
- 效果：arXiv 直接跳过 `_passes_keyword_rules`，避免二次过滤

### 3) 时间窗口
- 配置保持不变：`config/sources.yaml` 中 arXiv `lookback_hours: 720`、GitHub `lookback_days: 30`

### 4) 备份（可选）
```bash
cp src/common/constants.py src/common/constants.py.backup-20251122
cp src/prefilter/rule_filter.py src/prefilter/rule_filter.py.backup-20251122
```

## 验证（阶段2）
- 运行对比测试脚本：`.venv/bin/python scripts/test_prefilter_improvement.py`
- 验收门槛：
  - 通过率 20–35%
  - 输出数量 ≥20 条
  - 抽样 10 条，FP ≤2
- 手工抽样记录模板：
```
| # | 标题 | 来源 | 是否Benchmark | 是否FP | 备注 |
```

## 监控与回滚
- 日志监控：`.venv/bin/python scripts/monitor_prefilter.py`（按来源统计）
- 回滚：
```bash
cp src/common/constants.py.backup-20251122 src/common/constants.py
cp src/prefilter/rule_filter.py.backup-20251122 src/prefilter/rule_filter.py
# 或 git revert <commit>
```

## 附录
- 对比测试脚本：`scripts/test_prefilter_improvement.py`（含采集、预筛选、通过率统计、样本打印）
- 回滚脚本示例：`scripts/rollback_prefilter.sh`
- 监控脚本示例：`scripts/monitor_prefilter.py`
