# Codex开发指令：为高优先级卡片添加机构和Stars显示

## 文档元信息
- **创建时间**: 2025-11-22
- **创建者**: Claude Code
- **执行者**: Codex
- **优先级**: P2 (改进)
- **预计工作量**: 15分钟
- **前置条件**: 已完成中优先级卡片增强 (CODEX-CARD-ENHANCEMENT.md)

---

## 需求说明

### 用户反馈
中优先级卡片已添加机构和stars显示，但高优先级卡片仍然缺少这些信息。需要保持一致性，为高优先级卡片也添加机构和stars显示。

### 当前格式（高优先级卡片）

**文件**: `src/notifier/feishu_notifier.py` (第267-365行)

当前高优先级卡片格式：
```
**标题**
[图片预览]（如果有）
---
综合评分: 6.7 / 10  |  优先级: 高优先级

评分细项
活跃度 7.0  |  可复现性 5.0  |  许可合规 8.0  |  任务新颖性 6.0  |  MGX适配度 5.5

来源: GitHub

评分依据
[LLM推理文本...]
---
[查看详情] [GitHub] [飞书表格]
```

### 期望格式（与中优先级卡片保持一致）

```
**标题**
[图片预览]（如果有）
---
综合评分: 6.7 / 10  |  优先级: 高优先级

评分细项
活跃度 7.0  |  可复现性 5.0  |  许可合规 8.0  |  任务新颖性 6.0  |  MGX适配度 5.5

来源: GitHub  |  机构: OpenAI  |  Stars: 1.2k

评分依据
[LLM推理文本...]
---
[查看详情] [GitHub] [飞书表格]
```

---

## 实施方案

### 修改位置

**文件**: `src/notifier/feishu_notifier.py`
**方法**: `_build_card`
**行数**: 第267-365行（重点关注第307-317行的detail_content构建）

### 关键变化

1. **复用已有方法**：使用 `_format_institution(candidate)` 和 `_format_stars(candidate.github_stars)`
2. **修改detail_content**：在"来源"行后添加机构和stars信息
3. **保持排版一致**：使用 `│` 分隔符，与中优先级卡片保持一致

---

## 详细实施步骤

### Step 1: 修改 `_build_card` 方法中的 detail_content 构建

**当前代码** (第307-317行):
```python
detail_content = (
    f"综合评分: **{candidate.total_score:.1f}** / 10  |  优先级: **{priority_label}**\n\n"
    "**评分细项**\n"
    f"活跃度 {candidate.activity_score:.1f}  |  "
    f"可复现性 {candidate.reproducibility_score:.1f}  |  "
    f"许可合规 {candidate.license_score:.1f}  |  "
    f"任务新颖性 {candidate.novelty_score:.1f}  |  "
    f"MGX适配度 {candidate.relevance_score:.1f}\n\n"
    f"**来源**: {source_name}\n\n"
    f"**评分依据**\n{candidate.reasoning}"
)
```

**修改后代码**:
```python
# 提取机构和Stars信息（复用中优先级卡片的方法）
institution = self._format_institution(candidate)
stars_text = self._format_stars(candidate.github_stars)

detail_content = (
    f"综合评分: **{candidate.total_score:.1f}** / 10  |  优先级: **{priority_label}**\n\n"
    "**评分细项**\n"
    f"活跃度 {candidate.activity_score:.1f}  |  "
    f"可复现性 {candidate.reproducibility_score:.1f}  |  "
    f"许可合规 {candidate.license_score:.1f}  |  "
    f"任务新颖性 {candidate.novelty_score:.1f}  |  "
    f"MGX适配度 {candidate.relevance_score:.1f}\n\n"
    f"**来源**: {source_name}  |  {institution}  |  {stars_text}\n\n"
    f"**评分依据**\n{candidate.reasoning}"
)
```

**关键变化**:
- 新增第1-2行：提取机构和stars信息
- 修改"来源"行（倒数第3行）：追加 `|  {institution}  |  {stars_text}`

---

## 完整代码对比

### 修改前 (第307-317行)

```python
detail_content = (
    f"综合评分: **{candidate.total_score:.1f}** / 10  |  优先级: **{priority_label}**\n\n"
    "**评分细项**\n"
    f"活跃度 {candidate.activity_score:.1f}  |  "
    f"可复现性 {candidate.reproducibility_score:.1f}  |  "
    f"许可合规 {candidate.license_score:.1f}  |  "
    f"任务新颖性 {candidate.novelty_score:.1f}  |  "
    f"MGX适配度 {candidate.relevance_score:.1f}\n\n"
    f"**来源**: {source_name}\n\n"
    f"**评分依据**\n{candidate.reasoning}"
)
```

### 修改后

```python
# 提取机构和Stars信息（复用已有方法）
institution = self._format_institution(candidate)
stars_text = self._format_stars(candidate.github_stars)

detail_content = (
    f"综合评分: **{candidate.total_score:.1f}** / 10  |  优先级: **{priority_label}**\n\n"
    "**评分细项**\n"
    f"活跃度 {candidate.activity_score:.1f}  |  "
    f"可复现性 {candidate.reproducibility_score:.1f}  |  "
    f"许可合规 {candidate.license_score:.1f}  |  "
    f"任务新颖性 {candidate.novelty_score:.1f}  |  "
    f"MGX适配度 {candidate.relevance_score:.1f}\n\n"
    f"**来源**: {source_name}  |  {institution}  |  {stars_text}\n\n"
    f"**评分依据**\n{candidate.reasoning}"
)
```

**完整修改位置** (第307行之前插入，第317行修改)：
```python
# 在第307行之前插入（约第305-306行位置）
institution = self._format_institution(candidate)
stars_text = self._format_stars(candidate.github_stars)

# 修改第315行（原来的"来源"行）
# 从：f"**来源**: {source_name}\n\n"
# 改为：f"**来源**: {source_name}  |  {institution}  |  {stars_text}\n\n"
```

---

## 测试验证计划

### 测试1: GitHub项目（有Stars）

**测试数据**:
```python
candidate = ScoredCandidate(
    title="universal-tool-calling-protocol/code-mode",
    source="github",
    github_stars=1234,
    authors=["John Doe", "Jane Smith"],
    total_score=9.5,  # 高优先级
    priority="high",
    # ...
)
```

**预期输出**:
```
**universal-tool-calling-protocol/code-mode**
---
综合评分: 9.5 / 10  |  优先级: 高优先级

评分细项
活跃度 9.0  |  可复现性 9.5  |  ...

来源: GitHub  |  作者: John Doe, Jane Smith  |  Stars: 1.2k

评分依据
...
```

### 测试2: arXiv论文（有机构，无Stars）

**测试数据**:
```python
candidate = ScoredCandidate(
    title="Natural Language Interfaces for Databases",
    source="arxiv",
    raw_institutions="Stanford University",
    authors=["Alice Wang", "Bob Lee"],
    total_score=9.2,
    priority="high",
    # ...
)
```

**预期输出**:
```
**Natural Language Interfaces for Databases**
---
综合评分: 9.2 / 10  |  优先级: 高优先级

评分细项
...

来源: arXiv  |  机构: Stanford University  |  Stars: --

评分依据
...
```

### 测试3: 无机构无Stars

**预期输出**:
```
来源: GitHub  |  机构: 未知  |  Stars: --
```

---

## 成功标准和检查清单

### 代码修改检查
- [ ] `_build_card` 方法已修改（新增机构+Stars行）
- [ ] 复用已有的 `_format_institution` 和 `_format_stars` 方法
- [ ] 代码符合PEP8规范
- [ ] 与中优先级卡片格式保持一致

### 功能验证检查
- [ ] 高优先级卡片包含机构信息
- [ ] 高优先级卡片包含Stars数（格式化）
- [ ] 机构+Stars+来源在同一行
- [ ] 各种边界情况正常（无机构、无Stars等）

### 格式验证检查
- [ ] Stars数格式化正确（1.2k）
- [ ] 机构名过长时截断（≤50字符）
- [ ] 作者列表格式化正确（前2位 + et al.）
- [ ] 飞书卡片排版美观，无错位

---

## 边界情况处理

所有边界情况的处理逻辑已在 `_format_institution()` 和 `_format_stars()` 方法中实现，直接复用即可：

### 情况1: 机构名过长
**处理**: 自动截断至50字符（`_format_institution` 方法）

### 情况2: 作者列表过长
**处理**: 只显示前2位 + et al.（`_format_institution` 方法）

### 情况3: 无任何信息
**处理**: 显示占位符 `机构: 未知`（`_format_institution` 方法）

### 情况4: Stars为0或None
**处理**: 显示为 `Stars: --`（`_format_stars` 方法）

---

## 风险评估与缓解

### 风险1: 飞书卡片宽度超限

**风险**: 机构名+Stars行可能过宽，导致卡片显示异常

**影响**: 飞书推送卡片错位或截断

**缓解措施**:
1. 机构名最大50字符，超过则截断（已在 `_format_institution` 中实现）
2. Stars数格式化缩短（12.3k而非12345，已在 `_format_stars` 中实现）
3. 使用 `│` 分隔符保持紧凑
4. 与中优先级卡片格式一致，已验证可行

### 风险2: 字段缺失

**风险**: 部分来源（如HELM, DBEngines）可能无机构和Stars

**影响**: 显示 `机构: 未知  │  Stars: --`

**缓解措施**:
1. 提供占位符 `未知` 和 `--`（已实现）
2. 保持格式一致，不会因缺失而错位

---

## 后续优化建议

### 优化1: 统一卡片样式
中优先级和高优先级卡片现在都包含机构和Stars信息，保持了一致性。未来如果需要修改显示格式，只需修改 `_format_institution` 和 `_format_stars` 两个方法即可。

### 优化2: 可配置显示
在 `constants.py` 中增加配置开关：
```python
FEISHU_CARD_SHOW_INSTITUTION = True
FEISHU_CARD_SHOW_STARS = True
```

---

## 附录：精确修改位置

### 文件: `src/notifier/feishu_notifier.py`

**修改位置**: 第267-365行的 `_build_card` 方法

**精确修改步骤**:

1. **在第307行之前插入**（约第305-306行位置）:
   ```python
   # 提取机构和Stars信息（复用已有方法）
   institution = self._format_institution(candidate)
   stars_text = self._format_stars(candidate.github_stars)
   ```

2. **修改第315行**（原来的"来源"行）:
   ```python
   # 原代码（第315行）：
   f"**来源**: {source_name}\n\n"

   # 修改为：
   f"**来源**: {source_name}  |  {institution}  |  {stars_text}\n\n"
   ```

**完整修改后的代码段** (第305-318行):
```python
title_content = f"**{candidate.title[:constants.TITLE_TRUNCATE_LONG]}**"

# 提取机构和Stars信息（复用已有方法）
institution = self._format_institution(candidate)
stars_text = self._format_stars(candidate.github_stars)

detail_content = (
    f"综合评分: **{candidate.total_score:.1f}** / 10  |  优先级: **{priority_label}**\n\n"
    "**评分细项**\n"
    f"活跃度 {candidate.activity_score:.1f}  |  "
    f"可复现性 {candidate.reproducibility_score:.1f}  |  "
    f"许可合规 {candidate.license_score:.1f}  |  "
    f"任务新颖性 {candidate.novelty_score:.1f}  |  "
    f"MGX适配度 {candidate.relevance_score:.1f}\n\n"
    f"**来源**: {source_name}  |  {institution}  |  {stars_text}\n\n"
    f"**评分依据**\n{candidate.reasoning}"
)
```

---

**文档结束**
