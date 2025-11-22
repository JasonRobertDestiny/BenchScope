# Codex开发指令文档：优化飞书中优先级推送卡片

## 文档元信息
- **创建时间**: 2025-11-22
- **创建者**: Claude Code
- **执行者**: Codex
- **优先级**: P2 (改进)
- **预计工作量**: 30分钟

---

## 需求说明

### 用户反馈
希望在飞书中优先级推送卡片中添加以下信息：
1. **机构信息**（authors/institutions）
2. **GitHub Stars数**
3. **这些信息放在同一行**（与URL查看详情按钮同行）

### 当前格式

**文件**: `src/notifier/feishu_notifier.py` (第120-133行)

当前推送格式：
```
**1. universal-tool-calling-protocol/code-mode**
   来源: GitHub  │  评分: 6.7  │  活跃度: 7.0  │  可复现性: 5.0
   [查看详情](https://github.com/...)
```

### 期望格式

```
**1. universal-tool-calling-protocol/code-mode**
   来源: GitHub  │  评分: 6.7  │  活跃度: 7.0  │  可复现性: 5.0
   机构: OpenAI  │  Stars: 1.2k  │  [查看详情](https://github.com/...)
```

---

## 实施方案

### 修改位置

**文件**: `src/notifier/feishu_notifier.py`
**方法**: `_send_medium_priority_summary`
**行数**: 第120-133行

### 关键变化

1. **提取机构信息**：优先使用 `raw_institutions`，备选 `authors` 前2位
2. **格式化Stars数**：1234 → 1.2k
3. **新增一行**：机构 + Stars + 查看详情

---

## 详细实施步骤

### Step 1: 修改循环体中的内容构建逻辑

**当前代码** (第120-133行):
```python
for i, c in enumerate(top_candidates, 1):
    title = (
        c.title[: constants.TITLE_TRUNCATE_MEDIUM] + "..."
        if len(c.title) > constants.TITLE_TRUNCATE_MEDIUM
        else c.title
    )
    source_name = self._format_source_name(c.source)

    content += (
        f"**{i}. {title}**\n"
        f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
        f"活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}\n"
        f"   [查看详情]({c.url})\n\n"
    )
```

**修改后代码**:
```python
for i, c in enumerate(top_candidates, 1):
    title = (
        c.title[: constants.TITLE_TRUNCATE_MEDIUM] + "..."
        if len(c.title) > constants.TITLE_TRUNCATE_MEDIUM
        else c.title
    )
    source_name = self._format_source_name(c.source)

    # 提取机构信息
    institution = self._format_institution(c)

    # 格式化Stars数
    stars_text = self._format_stars(c.github_stars)

    # 构建内容（新增机构+Stars行）
    content += (
        f"**{i}. {title}**\n"
        f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
        f"活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}\n"
        f"   {institution}  │  {stars_text}  │  [查看详情]({c.url})\n\n"
    )
```

**关键变化**:
- 新增调用 `_format_institution(c)` 提取机构
- 新增调用 `_format_stars(c.github_stars)` 格式化Stars
- 新增第三行：`机构  │  Stars  │  [查看详情]`

---

### Step 2: 新增辅助方法 `_format_institution`

**添加位置**: `FeishuNotifier` 类中，建议在 `_format_source_name` 方法后

**新增代码**:
```python
@staticmethod
def _format_institution(candidate: ScoredCandidate) -> str:
    """提取并格式化机构/作者信息"""

    # 优先使用raw_institutions（arXiv论文有此字段）
    if candidate.raw_institutions:
        # 截断过长机构名
        institutions = candidate.raw_institutions[:50]
        return f"机构: {institutions}"

    # 备选：使用authors前2位
    if candidate.authors and len(candidate.authors) > 0:
        if len(candidate.authors) == 1:
            author_text = candidate.authors[0]
        elif len(candidate.authors) == 2:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]}"
        else:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]} et al."

        # 截断过长作者名
        if len(author_text) > 50:
            author_text = author_text[:47] + "..."

        return f"作者: {author_text}"

    # 都没有则返回占位符
    return "机构: 未知"
```

**说明**:
- 优先级1: `raw_institutions`（arXiv论文有此字段）
- 优先级2: `authors` 前2位（GitHub项目可能有contributors）
- 最大长度50字符，避免卡片过宽
- 返回格式: `机构: XXX` 或 `作者: XXX`

---

### Step 3: 新增辅助方法 `_format_stars`

**添加位置**: `_format_institution` 方法后

**新增代码**:
```python
@staticmethod
def _format_stars(stars: Optional[int]) -> str:
    """格式化GitHub Stars数（1234 → 1.2k）"""

    if stars is None or stars == 0:
        return "Stars: --"

    if stars >= 10000:
        return f"Stars: {stars/1000:.1f}k"
    elif stars >= 1000:
        return f"Stars: {stars/1000:.1f}k"
    else:
        return f"Stars: {stars}"
```

**说明**:
- `None` 或 `0` → `Stars: --`
- `1234` → `Stars: 1.2k`
- `12345` → `Stars: 12.3k`
- `< 1000` → `Stars: 234`（保持原数字）

---

## 完整代码对比

### 修改前 (第120-133行)

```python
for i, c in enumerate(top_candidates, 1):
    title = (
        c.title[: constants.TITLE_TRUNCATE_MEDIUM] + "..."
        if len(c.title) > constants.TITLE_TRUNCATE_MEDIUM
        else c.title
    )
    source_name = self._format_source_name(c.source)

    content += (
        f"**{i}. {title}**\n"
        f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
        f"活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}\n"
        f"   [查看详情]({c.url})\n\n"
    )
```

### 修改后

```python
for i, c in enumerate(top_candidates, 1):
    title = (
        c.title[: constants.TITLE_TRUNCATE_MEDIUM] + "..."
        if len(c.title) > constants.TITLE_TRUNCATE_MEDIUM
        else c.title
    )
    source_name = self._format_source_name(c.source)

    # 提取机构信息
    institution = self._format_institution(c)

    # 格式化Stars数
    stars_text = self._format_stars(c.github_stars)

    # 构建内容（新增机构+Stars行）
    content += (
        f"**{i}. {title}**\n"
        f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
        f"活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}\n"
        f"   {institution}  │  {stars_text}  │  [查看详情]({c.url})\n\n"
    )
```

**关键差异**:
- Line 9-12: 新增机构和Stars格式化
- Line 17: 新增第三行：`{institution}  │  {stars_text}  │  [查看详情]`

---

## 新增方法的完整代码

### 方法1: `_format_institution`

```python
@staticmethod
def _format_institution(candidate: ScoredCandidate) -> str:
    """提取并格式化机构/作者信息

    优先级：
    1. raw_institutions (arXiv论文)
    2. authors前2位 (GitHub项目)
    3. 占位符 "未知"

    Returns:
        格式化的机构/作者字符串，如 "机构: OpenAI" 或 "作者: John Doe, Jane Smith"
    """

    # 优先使用raw_institutions（arXiv论文有此字段）
    if candidate.raw_institutions:
        # 截断过长机构名
        institutions = candidate.raw_institutions[:50]
        if len(candidate.raw_institutions) > 50:
            institutions += "..."
        return f"机构: {institutions}"

    # 备选：使用authors前2位
    if candidate.authors and len(candidate.authors) > 0:
        if len(candidate.authors) == 1:
            author_text = candidate.authors[0]
        elif len(candidate.authors) == 2:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]}"
        else:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]} et al."

        # 截断过长作者名
        if len(author_text) > 50:
            author_text = author_text[:47] + "..."

        return f"作者: {author_text}"

    # 都没有则返回占位符
    return "机构: 未知"
```

### 方法2: `_format_stars`

```python
@staticmethod
def _format_stars(stars: Optional[int]) -> str:
    """格式化GitHub Stars数

    转换规则：
    - None/0 → "Stars: --"
    - 1234 → "Stars: 1.2k"
    - 12345 → "Stars: 12.3k"
    - 234 → "Stars: 234"

    Args:
        stars: GitHub stars数量

    Returns:
        格式化的Stars字符串
    """

    if stars is None or stars == 0:
        return "Stars: --"

    if stars >= 1000:
        return f"Stars: {stars/1000:.1f}k"
    else:
        return f"Stars: {stars}"
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
    total_score=6.7,
    # ...
)
```

**预期输出**:
```
**1. universal-tool-calling-protocol/code-mode**
   来源: GitHub  │  评分: 6.7  │  活跃度: 7.0  │  可复现性: 5.0
   作者: John Doe, Jane Smith  │  Stars: 1.2k  │  [查看详情](...)
```

### 测试2: arXiv论文（有机构）

**测试数据**:
```python
candidate = ScoredCandidate(
    title="Natural Language Interfaces for Databases",
    source="arxiv",
    raw_institutions="Stanford University",
    authors=["Alice Wang", "Bob Lee"],
    total_score=7.2,
    # ...
)
```

**预期输出**:
```
**1. Natural Language Interfaces for Databases**
   来源: arXiv  │  评分: 7.2  │  活跃度: 6.0  │  可复现性: 8.0
   机构: Stanford University  │  Stars: --  │  [查看详情](...)
```

### 测试3: 无机构无Stars

**测试数据**:
```python
candidate = ScoredCandidate(
    title="EverMind-AI/EverMemOS",
    source="github",
    github_stars=None,
    authors=None,
    total_score=6.3,
    # ...
)
```

**预期输出**:
```
**1. EverMind-AI/EverMemOS**
   来源: GitHub  │  评分: 6.3  │  活跃度: 6.0  │  可复现性: 5.0
   机构: 未知  │  Stars: --  │  [查看详情](...)
```

---

## 成功标准和检查清单

### 代码修改检查
- [ ] `_send_medium_priority_summary` 方法已修改（增加机构+Stars行）
- [ ] 新增 `_format_institution` 静态方法
- [ ] 新增 `_format_stars` 静态方法
- [ ] 代码符合PEP8规范
- [ ] 添加docstring说明

### 功能验证检查
- [ ] 运行完整流程无错误
- [ ] 飞书推送卡片包含机构信息
- [ ] 飞书推送卡片包含Stars数（格式化）
- [ ] 机构+Stars+查看详情在同一行
- [ ] 各种边界情况正常（无机构、无Stars等）

### 格式验证检查
- [ ] Stars数格式化正确（1.2k）
- [ ] 机构名过长时截断（≤50字符）
- [ ] 作者列表格式化正确（前2位 + et al.）
- [ ] 飞书卡片排版美观，无错位

---

## 边界情况处理

### 情况1: 机构名过长

**输入**: `raw_institutions = "National Key Laboratory for Novel Software Technology at Nanjing University"`

**处理**: 截断至50字符
```
机构: National Key Laboratory for Novel Software T...
```

### 情况2: 作者列表过长

**输入**: `authors = ["Alice", "Bob", "Charlie", "David"]`

**处理**: 只显示前2位 + et al.
```
作者: Alice, Bob et al.
```

### 情况3: 无任何信息

**输入**: `raw_institutions = None, authors = None`

**处理**: 显示占位符
```
机构: 未知
```

### 情况4: Stars为0

**输入**: `github_stars = 0`

**处理**: 显示为 `--`
```
Stars: --
```

---

## 风险评估与缓解

### 风险1: 飞书卡片宽度超限

**风险**: 机构名+Stars行可能过宽，导致卡片显示异常

**影响**: 飞书推送卡片错位或截断

**缓解措施**:
1. 机构名最大50字符，超过则截断
2. Stars数格式化缩短（12.3k而非12345）
3. 使用 `│` 分隔符保持紧凑

### 风险2: 字段缺失

**风险**: 部分来源（如HELM, DBEngines）可能无机构和Stars

**影响**: 显示 `机构: 未知  │  Stars: --`

**缓解措施**:
1. 提供占位符 `未知` 和 `--`
2. 保持格式一致，不会因缺失而错位

### 风险3: 中文字符宽度

**风险**: 中文字符比英文字符宽，可能导致排版问题

**影响**: 飞书卡片对齐异常

**缓解措施**:
1. 使用飞书Markdown自动处理
2. 测试包含中文机构名的情况
3. 必要时调整截断长度

---

## 后续优化建议

### 优化1: 动态显示字段

根据来源类型显示不同字段：
- **GitHub**: 显示Stars + Contributors
- **arXiv**: 显示机构 + 引用数
- **HuggingFace**: 显示Downloads

### 优化2: 可配置显示

在 `constants.py` 中增加配置：
```python
FEISHU_CARD_SHOW_INSTITUTION = True
FEISHU_CARD_SHOW_STARS = True
```

### 优化3: 图标化

使用emoji图标增强可读性：
```
🏫 机构: Stanford University  │  ⭐ Stars: 1.2k  │  [查看详情](...)
```

---

## 参考资料

### 飞书卡片Markdown格式

- 支持 `**粗体**`
- 支持链接 `[文本](URL)`
- 支持分隔符 `│`（U+2502 BOX DRAWINGS LIGHT VERTICAL）
- 自动换行，无需手动处理宽度

### ScoredCandidate字段

```python
class ScoredCandidate:
    authors: Optional[List[str]]          # 作者列表
    raw_institutions: Optional[str]       # 机构信息（原始）
    github_stars: Optional[int]           # GitHub stars数
```

---

## 附录：完整修改示例

### 修改文件: `src/notifier/feishu_notifier.py`

**修改1**: 在 `_format_source_name` 方法后新增两个方法（约第97行后）

```python
@staticmethod
def _format_source_name(source: str) -> str:
    """统一来源展示名称，避免多处硬编码"""
    # ... 现有代码 ...

@staticmethod
def _format_institution(candidate: ScoredCandidate) -> str:
    """提取并格式化机构/作者信息"""

    # 优先使用raw_institutions（arXiv论文有此字段）
    if candidate.raw_institutions:
        institutions = candidate.raw_institutions[:50]
        if len(candidate.raw_institutions) > 50:
            institutions += "..."
        return f"机构: {institutions}"

    # 备选：使用authors前2位
    if candidate.authors and len(candidate.authors) > 0:
        if len(candidate.authors) == 1:
            author_text = candidate.authors[0]
        elif len(candidate.authors) == 2:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]}"
        else:
            author_text = f"{candidate.authors[0]}, {candidate.authors[1]} et al."

        if len(author_text) > 50:
            author_text = author_text[:47] + "..."

        return f"作者: {author_text}"

    return "机构: 未知"

@staticmethod
def _format_stars(stars: Optional[int]) -> str:
    """格式化GitHub Stars数（1234 → 1.2k）"""

    if stars is None or stars == 0:
        return "Stars: --"

    if stars >= 1000:
        return f"Stars: {stars/1000:.1f}k"
    else:
        return f"Stars: {stars}"
```

**修改2**: 更新 `_send_medium_priority_summary` 方法中的循环体（第120-133行）

```python
for i, c in enumerate(top_candidates, 1):
    title = (
        c.title[: constants.TITLE_TRUNCATE_MEDIUM] + "..."
        if len(c.title) > constants.TITLE_TRUNCATE_MEDIUM
        else c.title
    )
    source_name = self._format_source_name(c.source)

    # 提取机构信息
    institution = self._format_institution(c)

    # 格式化Stars数
    stars_text = self._format_stars(c.github_stars)

    # 构建内容（新增机构+Stars行）
    content += (
        f"**{i}. {title}**\n"
        f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
        f"活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}\n"
        f"   {institution}  │  {stars_text}  │  [查看详情]({c.url})\n\n"
    )
```

---

**文档结束**
