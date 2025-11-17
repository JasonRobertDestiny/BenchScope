# BenchScope 字段对齐分析报告

**生成时间**: 2025-11-17
**验证工具**: `scripts/verify_all_fields.py`

---

## 1. 核心问题总结

### ❌ 严重问题 (1个)

**【任务领域】字段类型不匹配**
- **飞书配置**: 单选 (Single Select)
- **代码处理**: 多选数组 (`task_domain_list = [d.strip() for d in task_domain.split(",")]`)
- **影响**: 代码发送数组到单选字段，可能导致写入失败或数据截断
- **修复方案**:
  1. **推荐**: 修改飞书字段为"多选" (允许Benchmark归属多个领域，如 "Coding,Backend")
  2. **备选**: 修改代码只取第一个领域（损失信息）

---

## 2. 缺失关键字段 (3个)

### 2.1 论文URL (paper_url) ⭐⭐⭐

**重要性**: 非常高 - Benchmark通常有配套论文

**当前状态**:
- ✅ 模型字段存在: `paper_url: Optional[str]`
- ❌ 飞书字段不存在
- ❌ 存储映射缺失

**数据来源**:
- arXiv采集器: 自动提取论文URL
- GitHub采集器: 可从README解析
- Semantic Scholar: 直接返回论文链接

**修复步骤**:
1. 在飞书表格添加字段 "论文URL" (类型: 超链接)
2. 在 `FeishuStorage.FIELD_MAPPING` 添加映射:
   ```python
   "paper_url": "论文URL",
   ```
3. 在 `_to_feishu_record` 添加处理逻辑:
   ```python
   if hasattr(candidate, "paper_url") and candidate.paper_url:
       fields[self.FIELD_MAPPING["paper_url"]] = {"link": candidate.paper_url}
   ```

---

### 2.2 复现脚本URL (reproduction_script_url) ⭐⭐⭐

**重要性**: 非常高 - 直接关系可复现性评分

**当前状态**:
- ✅ 模型字段存在: `reproduction_script_url: Optional[str]`
- ❌ 飞书字段不存在
- ❌ 存储映射缺失

**数据来源**:
- GitHub采集器: 从README提取评估脚本链接
- 评分时LLM可补充（如果摘要中提到）

**修复步骤**:
1. 在飞书表格添加字段 "复现脚本" (类型: 超链接)
2. 在 `FeishuStorage.FIELD_MAPPING` 添加映射:
   ```python
   "reproduction_script_url": "复现脚本",
   ```
3. 在 `_to_feishu_record` 添加处理逻辑:
   ```python
   if hasattr(candidate, "reproduction_script_url") and candidate.reproduction_script_url:
       fields[self.FIELD_MAPPING["reproduction_script_url"]] = {"link": candidate.reproduction_script_url}
   ```

---

### 2.3 任务类型 (task_type) ⭐⭐

**重要性**: 高 - 辅助分类和筛选

**当前状态**:
- ✅ 模型字段存在: `task_type: Optional[str]`
- ❌ 飞书字段不存在
- ❌ 存储映射缺失

**数据来源**:
- 各采集器规则提取（如 "code generation", "web automation", "reasoning"）
- LLM评分时可补充

**修复步骤**:
1. 在飞书表格添加字段 "任务类型" (类型: 文本)
2. 在 `FeishuStorage.FIELD_MAPPING` 添加映射:
   ```python
   "task_type": "任务类型",
   ```
3. 在 `_to_feishu_record` 添加处理逻辑:
   ```python
   if hasattr(candidate, "task_type") and candidate.task_type:
       fields[self.FIELD_MAPPING["task_type"]] = candidate.task_type
   ```

---

## 3. 可选增强字段 (9个)

### 3.1 原始字段组 (raw_*)

**字段列表**:
- `raw_authors` - 原始作者信息
- `raw_baselines` - 原始Baseline列表
- `raw_dataset_size` - 原始数据集规模描述
- `raw_institutions` - 原始机构信息
- `raw_metrics` - 原始评估指标

**建议**: 暂不添加到飞书，保留在代码中用于调试和质量控制

**原因**:
1. 飞书已有LLM清洗后的版本（如 `metrics`, `baselines`）
2. 原始数据通常格式不统一，展示价值低
3. 如需追溯，可从SQLite fallback查询

---

### 3.2 evaluation_metrics (原始评估指标)

**状态**: 已有 `metrics` (LLM抽取后)

**建议**: 暂不添加，与 `metrics` 重复

---

### 3.3 custom_total_score (自定义总分)

**状态**: 模型中存在但未使用

**建议**: 如需支持人工调整评分，可添加；否则使用默认 `total_score`

---

## 4. 飞书系统字段 (2个)

**创建时间** / **最后修改时间**
- 飞书系统自动维护
- 无需代码处理
- ✅ 正常

---

## 5. 完美对齐字段 (24个)

以下字段已完美对齐，数据流畅通无阻：

| 模型字段 | 飞书字段 | 类型 | 数据覆盖率 |
|---------|---------|-----|----------|
| title | 标题 | 文本 | 100% |
| url | URL | 超链接 | 100% |
| source | 来源 | 多选 | 100% |
| abstract | 摘要 | 文本 | ~95% |
| github_stars | GitHub Stars | 数字 | ~40% |
| github_url | GitHub URL | 超链接 | ~40% |
| publish_date | 发布日期 | 日期 | ~80% |
| license_type | 许可证 | 文本 | ~60% |
| dataset_url | 数据集URL | 超链接 | ~50% |
| dataset_size | 数据集规模 | 数字 | ~30% |
| dataset_size_description | 数据集规模描述 | 文本 | ~40% |
| authors | 作者 | 文本 | ~70% |
| institution | 机构 | 文本 | ~60% |
| metrics | 评估指标 | 文本 | ~80% |
| baselines | 基准模型 | 文本 | ~70% |
| task_domain | 任务领域 | ⚠️ 单选 | ~90% |
| activity_score | 活跃度 | 数字 | 100% |
| reproducibility_score | 可复现性 | 数字 | 100% |
| license_score | 许可合规 | 数字 | 100% |
| novelty_score | 新颖性 | 数字 | 100% |
| relevance_score | MGX适配度 | 数字 | 100% |
| total_score | 总分 | 数字 | 100% |
| priority | 优先级 | 多选 | 100% |
| reasoning | 评分依据 | 文本 | 100% |

**注**: 数据覆盖率基于实际运行数据估算

---

## 6. 修复优先级

### 🔴 P0 - 立即修复 (影响核心功能)

1. **修复任务领域字段类型**
   - 飞书: 单选 → 多选
   - 或代码: 数组 → 取第一个元素

### 🟡 P1 - 本周修复 (影响数据完整性)

2. **添加论文URL字段** (paper_url)
3. **添加复现脚本字段** (reproduction_script_url)
4. **添加任务类型字段** (task_type)

### 🟢 P2 - 未来优化 (Nice to have)

5. 考虑是否需要 `custom_total_score` (人工调分)
6. 考虑是否需要展示 `raw_*` 字段（调试用）

---

## 7. 执行清单

### 步骤1: 修复任务领域字段类型 (P0)

**推荐方案**: 修改飞书字段为"多选"

1. 打开飞书多维表格
2. 编辑"任务领域"字段
3. 类型: 单选 → 多选
4. 保留所有现有选项 (10个)
5. 测试写入数据

**备选方案**: 修改代码只取第一个领域

```python
# src/storage/feishu_storage.py:235-244 修改为:
if getattr(candidate, "task_domain", None):
    task_domain = candidate.task_domain
    if isinstance(task_domain, str):
        # 取第一个领域（如果是逗号分隔）
        primary_domain = task_domain.split(",")[0].strip()
        fields[self.FIELD_MAPPING["task_domain"]] = primary_domain
    elif isinstance(task_domain, list):
        # 取第一个元素
        fields[self.FIELD_MAPPING["task_domain"]] = task_domain[0]
```

---

### 步骤2: 添加3个缺失字段 (P1)

**2.1 在飞书表格添加字段**:
- "论文URL" (类型: 超链接)
- "复现脚本" (类型: 超链接)
- "任务类型" (类型: 文本)

**2.2 更新 `src/storage/feishu_storage.py`**:

```python
# 在 FIELD_MAPPING 添加 (约第30-55行):
FIELD_MAPPING = {
    # ... 现有字段 ...

    # Phase 8.5: 补充关键字段
    "paper_url": "论文URL",
    "reproduction_script_url": "复现脚本",
    "task_type": "任务类型",
}

# 在 _to_feishu_record 添加 (约第267行后):
if hasattr(candidate, "paper_url") and candidate.paper_url:
    fields[self.FIELD_MAPPING["paper_url"]] = {"link": candidate.paper_url}

if hasattr(candidate, "reproduction_script_url") and candidate.reproduction_script_url:
    fields[self.FIELD_MAPPING["reproduction_script_url"]] = {
        "link": candidate.reproduction_script_url
    }

if hasattr(candidate, "task_type") and candidate.task_type:
    fields[self.FIELD_MAPPING["task_type"]] = candidate.task_type[:100]
```

---

### 步骤3: 验证修复

```bash
# 运行验证脚本
.venv/bin/python scripts/verify_all_fields.py

# 预期输出:
# ✅ 所有字段完美对齐！模型、存储映射、飞书表格三者同步。
# 总计差异: 0个
```

---

### 步骤4: 测试数据流

```bash
# 运行完整流程测试
.venv/bin/python -m src.main

# 检查飞书表格:
# 1. "任务领域"字段应支持多个标签（如 "Coding, Backend"）
# 2. "论文URL"、"复现脚本"、"任务类型" 应有数据
# 3. 无写入错误日志
```

---

## 8. 数据质量改进建议

### 提高数据覆盖率策略

1. **论文URL** (目标: 70% → 90%)
   - arXiv采集器: 已100%覆盖 ✅
   - GitHub采集器: 增强README解析，提取论文链接
   - Semantic Scholar: 已100%覆盖 ✅

2. **复现脚本** (目标: 30% → 60%)
   - GitHub采集器: 智能搜索 "eval.py", "reproduce.sh", "benchmark.py"
   - LLM评分: 从摘要中抽取脚本链接

3. **任务类型** (目标: 新增字段，60%覆盖)
   - 各采集器: 规则映射（如 GitHub topic → task_type）
   - LLM评分: 补充未识别的任务类型

4. **数据集规模** (目标: 30% → 50%)
   - 增强正则表达式提取（"1000 samples", "10K examples"）
   - LLM评分: 从摘要中抽取数字

---

## 9. 附录: 字段完整清单

### 9.1 ScoredCandidate 模型 (33字段)

```python
@dataclass
class ScoredCandidate:
    # 基础信息 (4)
    title: str                              # ✅ 已映射
    url: str                                # ✅ 已映射
    source: SourceType                      # ✅ 已映射
    abstract: Optional[str]                 # ✅ 已映射

    # GitHub信息 (3)
    github_stars: Optional[int]             # ✅ 已映射
    github_url: Optional[str]               # ✅ 已映射
    license_type: Optional[str]             # ✅ 已映射

    # 时间与作者 (4)
    publish_date: Optional[datetime]        # ✅ 已映射
    authors: Optional[List[str]]            # ✅ 已映射
    institution: Optional[str]              # ✅ 已映射
    task_type: Optional[str]                # ❌ 缺失 (P1)

    # 数据集信息 (4)
    dataset_url: Optional[str]              # ✅ 已映射
    dataset_size: Optional[int]             # ✅ 已映射
    dataset_size_description: Optional[str] # ✅ 已映射
    evaluation_metrics: Optional[List[str]] # ⚠️ 有metrics替代

    # 评估信息 (3)
    metrics: Optional[List[str]]            # ✅ 已映射
    baselines: Optional[List[str]]          # ✅ 已映射
    task_domain: Optional[str]              # ⚠️ 类型不匹配 (P0)

    # 链接信息 (2)
    paper_url: Optional[str]                # ❌ 缺失 (P1)
    reproduction_script_url: Optional[str]  # ❌ 缺失 (P1)

    # 评分信息 (6)
    activity_score: float                   # ✅ 已映射
    reproducibility_score: float            # ✅ 已映射
    license_score: float                    # ✅ 已映射
    novelty_score: float                    # ✅ 已映射
    relevance_score: float                  # ✅ 已映射
    score_reasoning: str                    # ✅ 已映射 (as reasoning)

    # 原始数据 (5) - 调试用
    raw_metadata: Dict[str, str]            # ⚠️ 不需映射
    raw_metrics: Optional[List[str]]        # ⚠️ 不需映射
    raw_baselines: Optional[List[str]]      # ⚠️ 不需映射
    raw_authors: Optional[str]              # ⚠️ 不需映射
    raw_institutions: Optional[str]         # ⚠️ 不需映射
    raw_dataset_size: Optional[str]         # ⚠️ 不需映射

    # 自定义评分 (1)
    custom_total_score: Optional[float]     # ⚠️ 可选 (P2)
```

---

### 9.2 飞书表格字段 (26字段 + 待添加3字段)

**现有字段 (26个)**:
1. 标题 [文本] ✅
2. URL [超链接] ✅
3. 来源 [多选] ✅
4. 摘要 [文本] ✅
5. 发布日期 [日期] ✅
6. GitHub Stars [数字] ✅
7. GitHub URL [超链接] ✅
8. 许可证 [文本] ✅
9. 数据集URL [超链接] ✅
10. 数据集规模 [数字] ✅
11. 数据集规模描述 [文本] ✅
12. 作者 [文本] ✅
13. 机构 [文本] ✅
14. 评估指标 [文本] ✅
15. 基准模型 [文本] ✅
16. 任务领域 [单选] ⚠️ 需改为多选 (P0)
17. 活跃度 [数字] ✅
18. 可复现性 [数字] ✅
19. 许可合规 [数字] ✅
20. 新颖性 [数字] ✅
21. MGX适配度 [数字] ✅
22. 总分 [数字] ✅
23. 优先级 [多选] ✅
24. 评分依据 [文本] ✅
25. 创建时间 [系统] ✅
26. 最后修改时间 [系统] ✅

**待添加字段 (3个)**:
27. 论文URL [超链接] ❌ (P1)
28. 复现脚本 [超链接] ❌ (P1)
29. 任务类型 [文本] ❌ (P1)

---

## 10. 总结

### 当前状态
- ✅ 完美对齐: 24/33 字段 (72.7%)
- ⚠️ 类型不匹配: 1 字段 (任务领域)
- ❌ 缺失关键字段: 3 字段 (论文URL, 复现脚本, 任务类型)
- ✅ 数据流畅通: 评分→存储→飞书 核心链路正常

### 修复后预期
- ✅ 完美对齐: 27/33 字段 (81.8%)
- ✅ 所有核心字段覆盖
- ✅ 数据完整性大幅提升

### 预计工作量
- 飞书配置: 15分钟
- 代码修改: 30分钟
- 测试验证: 30分钟
- **总计**: 1.5小时
