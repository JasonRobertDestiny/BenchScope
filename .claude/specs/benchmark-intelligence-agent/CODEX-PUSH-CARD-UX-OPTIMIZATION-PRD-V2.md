# 飞书推送卡片UX优化PRD v2.0（简化版）

## 文档信息

- **创建时间**: 2025-11-23
- **版本**: v2.0（简化版，采用方案B）
- **目标**: 优化飞书推送卡片，聚焦"最新且任务相关"
- **实施者**: Codex
- **验收者**: Claude Code

---

## 一、核心目标

**推送最新且任务相关的候选，保证核心任务域覆盖**

设计原则：
1. **最新优先**：发布时间越近越靠前
2. **任务相关**：relevance_score ≥ 5.5
3. **核心域兜底**：10个核心域缺席时用补位区提醒

---

## 二、当前问题

### 2.1 现有中优摘要卡结构（src/notifier/feishu_notifier.py:404-551）

```python
async def _send_medium_priority_summary(...):
    # 当前分区：
    # 1. Top N 推荐（按总分排序）
    # 2. 按来源精选
    # 3. 按任务类型补位
    # 4. Latest Papers / Datasets
```

**问题**：
1. **排序规则错误**：Top N按总分排序，导致15天前的高分项排在3天前的中分项之前
2. **分区过多**：4个分区，用户需要理解每个分区的含义
3. **最新候选不突出**："Latest Papers"放在最后，容易被忽略
4. **核心域范围窄**：补位只考虑8个域，遗漏了LLM/AgentOps/DeepResearch

### 2.2 数据分析（513条记录）

- **非GitHub源100%低分**：arXiv均分3.67, HELM 4.22, HuggingFace 3.45
- **任务域严重失衡**：WebDev 0.2%（1条），GUI 1.2%（6条）
- **时效性差**：≤14天候选仅占~30%

---

## 三、解决方案：方案B（两分区架构）

### 3.1 新卡片结构

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 中优先级候选推荐                                         │
├─────────────────────────────────────────────────────────────┤
│ **候选概览**                                                │
│   总数: 12 条  │  平均分: 6.8 / 10  │  分数区间: 5.2 ~ 8.4 │
│                                                             │
│ **最新推荐**（最新且任务相关）                               │
│ 1. [arXiv] GUI操作代理新基准 | 7.2分 | 3d前                │
│    GUI | 相关8.5 新颖7.0 活跃6.0 复现6.5 → [查看论文]       │
│                                                             │
│ 2. [GitHub] Python代码生成评测 | 8.1分 | 5d前              │
│    Coding | 相关7.5 新颖6.0 活跃8.0 复现7.0 → [查看仓库]   │
│                                                             │
│ 3. [HELM] 多模态推理榜单更新 | 6.5分 | 8d前                │
│    Reasoning | 相关7.0 新颖5.5 活跃6.0 复现7.5 → [查看榜单]│
│                                                             │
│ ... (共12条)                                                │
│                                                             │
│ **任务域补位**（核心域缺失时显示）                           │
│ • WebDev: xxx （评分5.2，45d前，arXiv）补位 → [查看]        │
│ ⚠️ 本批缺失: DeepResearch                                   │
│                                                             │
│ [查看完整表格]                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心域定义（10个全量域）

```python
CORE_DOMAINS = [
    "Coding",
    "Backend",
    "WebDev",
    "GUI",
    "ToolUse",
    "Collaboration",
    "LLM/AgentOps",
    "Reasoning",
    "DeepResearch",
    "Other",
]
```

### 3.3 排序规则（最新优先）

**主推荐区排序**：
1. **发布时间**（越新越前）：按 `publish_date` 降序
2. **相关性**（越高越前）：时间相同时按 `relevance_score` 降序
3. **总分**（越高越前）：时间和相关性都相同时按 `total_score` 降序

```python
def sort_key(candidate: ScoredCandidate) -> tuple:
    # 发布时间：越新越小（天数越少）
    age_days = self._age_days(candidate)

    # 返回排序键：(天数↑, -相关性↓, -总分↓)
    return (age_days, -candidate.relevance_score, -candidate.total_score)

# 排序
candidates = sorted(candidates, key=sort_key)
```

### 3.4 筛选规则（保持不变）

**预过滤**（src/notifier/feishu_notifier.py:198-250，已实现）：
- `relevance_score >= 5.5`（任务相关）
- 发布≤30天 或 `total_score >= 8.0`（最新或高质量）
- 总量上限15条

**主推荐区**：
- 取预过滤后的前12条（按排序规则）

**任务域补位区**：
- 从剩余候选（包括low_candidates）中筛选
- 条件：
  - 任务域在核心域列表中
  - 任务域在主推荐区未覆盖
  - `total_score >= 5.0`（最低质量要求）
- 每个缺席域取1条（按发布时间↑排序）

---

## 四、代码实现

### 4.1 常量配置新增

**文件**: `src/common/constants.py`

```python
# ==================== 推送卡片配置（方案B：两分区） ====================

# 核心任务域定义（10个全量域）
CORE_DOMAINS: Final[List[str]] = [
    "Coding",
    "Backend",
    "WebDev",
    "GUI",
    "ToolUse",
    "Collaboration",
    "LLM/AgentOps",
    "Reasoning",
    "DeepResearch",
    "Other",
]

# 主推荐区配置
MAIN_RECOMMENDATION_LIMIT: Final[int] = 12  # 最新推荐区最多12条

# 任务域补位配置
TASK_FILL_MIN_SCORE: Final[float] = 5.0  # 补位候选最低分数
TASK_FILL_PER_DOMAIN_LIMIT: Final[int] = 1  # 每个缺席域最多1条补位
TASK_FILL_SHOW_MISSING: Final[bool] = True  # 显示缺失域提示

# 候选格式化配置
TITLE_TRUNCATE_CARD: Final[int] = 60  # 标题截断60字符（中英混合）
```

### 4.2 核心函数：重构中优摘要卡

**文件**: `src/notifier/feishu_notifier.py`

```python
async def _send_medium_priority_summary(
    self,
    candidates: List[ScoredCandidate],
    low_candidates: Optional[List[ScoredCandidate]] = None,
    covered_domains: Optional[set[str]] = None,
) -> None:
    """发送中优先级候选摘要卡片 - 方案B（两分区：最新推荐 + 任务域补位）。

    分区1: 最新推荐（≤12条，按 时间↑ → 相关性↓ → 总分↓ 排序）
    分区2: 任务域补位（核心域缺席时从low池提取，标"补位"）
    """
    # === 概览统计 ===
    avg_score = sum(c.total_score for c in candidates) / len(candidates) if candidates else 0
    scores = [c.total_score for c in candidates]
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    content = (
        f"**候选概览**\n"
        f"  总数: {len(candidates)} 条  │  平均分: {avg_score:.1f} / 10  │  分数区间: {min_score:.1f} ~ {max_score:.1f}\n\n"
    )

    # === 分区1: 最新推荐（按时间优先排序）===
    content += "**最新推荐**（最新且任务相关）\n\n"

    # 排序：时间↑ → 相关性↓ → 总分↓
    def sort_key(c: ScoredCandidate) -> tuple:
        age_days = self._age_days(c)
        return (age_days, -c.relevance_score, -c.total_score)

    sorted_candidates = sorted(candidates, key=sort_key)

    # 取前12条
    main_picks = sorted_candidates[: constants.MAIN_RECOMMENDATION_LIMIT]

    # 收集已覆盖域（用于补位判断）
    present_domains: set[str] = set()

    for i, cand in enumerate(main_picks, 1):
        # 标题截断
        title = cand.title
        if len(title) > constants.TITLE_TRUNCATE_CARD:
            title = title[:constants.TITLE_TRUNCATE_CARD] + "..."

        # 来源Badge
        source_badge = self._format_source_badge(cand.source)

        # 发布时间
        age_days = self._age_days(cand)
        age_text = f"{age_days}d前" if age_days > 0 else "今日"

        # 任务域
        domain = cand.task_domain or constants.DEFAULT_TASK_DOMAIN
        present_domains.add(domain)

        # 主链接
        link_text = self._get_primary_link_text(cand)
        primary_link = self._primary_link(cand)

        # 格式化（两行紧凑格式）
        content += (
            f"{i}. {source_badge} {title} | {cand.total_score:.1f}分 | {age_text}\n"
            f"   {domain} | "
            f"相关{cand.relevance_score:.1f} "
            f"新颖{cand.novelty_score:.1f} "
            f"活跃{cand.activity_score:.1f} "
            f"复现{cand.reproducibility_score:.1f} "
            f"→ [{link_text}]({primary_link})\n\n"
        )

    # === 分区2: 任务域补位（核心域缺席时触发）===
    fill_section = self._build_task_fill_section_v2(
        present_domains,
        low_candidates or [],
    )
    if fill_section:
        content += "**任务域补位**（核心域缺失时显示）\n\n"
        content += fill_section + "\n"

    # 其余候选提示
    if len(sorted_candidates) > len(main_picks):
        content += f"\n其余 {len(sorted_candidates) - len(main_picks)} 条候选可在飞书表格查看\n"

    # 构建卡片
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "中优先级候选推荐"},
                "template": "yellow",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "content": "查看完整表格",
                                "tag": "plain_text",
                            },
                            "url": constants.FEISHU_BENCH_TABLE_URL,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }

    await self._send_webhook(card)


def _format_source_badge(self, source: Optional[str]) -> str:
    """生成来源Badge（方括号格式）。"""
    source_lower = (source or "unknown").lower()

    badge_map = {
        "arxiv": "[arXiv]",
        "github": "[GitHub]",
        "helm": "[HELM]",
        "huggingface": "[HF]",
        "techempower": "[TE]",
        "dbengines": "[DB]",
        "semantic_scholar": "[S2]",
    }

    return badge_map.get(source_lower, "[Other]")


def _get_primary_link_text(self, candidate: ScoredCandidate) -> str:
    """根据来源返回主链接的显示文本。"""
    source_lower = (candidate.source or "").lower()

    link_text_map = {
        "arxiv": "查看论文",
        "semantic_scholar": "查看论文",
        "github": "查看仓库",
        "huggingface": "查看数据集",
        "helm": "查看榜单",
        "techempower": "查看基准",
        "dbengines": "查看排名",
    }

    return link_text_map.get(source_lower, "查看详情")


def _build_task_fill_section_v2(
    self,
    present_domains: set[str],
    low_candidates: List[ScoredCandidate],
) -> str:
    """任务域补位区（核心域缺席时从low池提取）。

    Args:
        present_domains: 主推荐区已覆盖的域
        low_candidates: 低优先级候选池

    Returns:
        补位区内容（Markdown）
    """
    if not low_candidates:
        return ""

    # 筛选：按时间排序
    sorted_low = sorted(
        low_candidates,
        key=lambda c: self._age_days(c),
    )

    lines: list[str] = []
    missing_domains: list[str] = []

    # 遍历核心域，查找缺席域
    for domain in constants.CORE_DOMAINS:
        if domain in present_domains:
            continue

        # 查找该域的补位候选
        found = False
        for cand in sorted_low:
            cand_domain = cand.task_domain or constants.DEFAULT_TASK_DOMAIN
            if cand_domain != domain:
                continue
            if cand.total_score < constants.TASK_FILL_MIN_SCORE:
                continue

            # 格式化补位项
            title = (
                cand.title[:constants.TITLE_TRUNCATE_CARD] + "..."
                if len(cand.title) > constants.TITLE_TRUNCATE_CARD
                else cand.title
            )
            age_days = self._age_days(cand)
            age_text = f"{age_days}d前" if age_days > 0 else "今日"
            source_name = self._format_source_name(cand.source)
            link_text = self._get_primary_link_text(cand)
            primary_link = self._primary_link(cand)

            lines.append(
                f"• {domain}: {title} （评分{cand.total_score:.1f}，{age_text}，来源{source_name}）补位 → [{link_text}]({primary_link})"
            )

            found = True
            break

        # 如果该域无补位候选，记录为缺失
        if not found:
            missing_domains.append(domain)

    if not lines and not missing_domains:
        return ""

    # 构建分区内容
    section_lines = lines

    # 显示缺失域警告
    if constants.TASK_FILL_SHOW_MISSING and missing_domains:
        missing_str = "、".join(missing_domains)
        section_lines.append(f"⚠️ 本批缺失: {missing_str}")

    return "\n".join(section_lines)
```

### 4.3 统计摘要卡增强

**文件**: `src/notifier/feishu_notifier.py`

```python
def _build_summary_card(
    self,
    qualified: List[ScoredCandidate],
    high_priority: List[ScoredCandidate],
    medium_priority: List[ScoredCandidate],
) -> dict:
    """构建统计摘要卡片 - 增强版（新增任务域覆盖 + 时效性统计）。"""
    avg_score = sum(c.total_score for c in qualified) / len(qualified) if qualified else 0

    # 数据源分布
    source_counts = {}
    for c in qualified:
        source_counts[c.source] = source_counts.get(c.source, 0) + 1
    source_items = [
        f"{self._format_source_name(src)} {cnt}"
        for src, cnt in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    source_breakdown = "  |  ".join(source_items)

    # 分数分布
    excellent = len([c for c in qualified if c.total_score >= 9.0])
    good = len([c for c in qualified if 8.0 <= c.total_score < 9.0])
    medium = len([c for c in qualified if 7.0 <= c.total_score < 8.0])
    pass_level = len([c for c in qualified if 6.0 <= c.total_score < 7.0])
    low = len([c for c in qualified if c.total_score < 6.0])

    # 质量评级
    if avg_score >= constants.QUALITY_EXCELLENT_THRESHOLD:
        quality_indicator = "优质"
    elif avg_score >= constants.QUALITY_GOOD_THRESHOLD:
        quality_indicator = "良好"
    elif avg_score >= constants.QUALITY_PASS_THRESHOLD:
        quality_indicator = "合格"
    else:
        quality_indicator = "一般"

    # === 新增：任务域覆盖统计 ===
    domain_counts = {}
    for c in qualified:
        domain = c.task_domain or constants.DEFAULT_TASK_DOMAIN
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    # 核心域覆盖状态（10个域）
    core_coverage_items = []
    for domain in constants.CORE_DOMAINS:
        count = domain_counts.get(domain, 0)
        if count >= 2:
            status = "✅"
        elif count == 1:
            status = "⚠️"
        else:
            status = "❌"
        core_coverage_items.append(f"{status}{domain} {count}")
    core_coverage_line = "  ".join(core_coverage_items)

    # === 新增：时效性统计 ===
    now = datetime.now()
    within_7d = 0
    within_14d = 0

    for c in qualified:
        if c.publish_date:
            publish_dt = c.publish_date
            if publish_dt.tzinfo is None:
                publish_dt = publish_dt.replace(tzinfo=timezone.utc)
            age_days = (now.replace(tzinfo=timezone.utc) - publish_dt).days

            if age_days <= 7:
                within_7d += 1
                within_14d += 1
            elif age_days <= 14:
                within_14d += 1

    percent_7d = (within_7d / len(qualified) * 100) if qualified else 0
    percent_14d = (within_14d / len(qualified) * 100) if qualified else 0

    # 紧凑排版
    content = (
        f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}**  |  "
        f"共 {len(qualified)} 条候选  |  "
        f"平均 {avg_score:.1f}分 ({quality_indicator})\n\n"
        f"**优先级**: 高 {len(high_priority)} 条 (已详细卡片)  |  "
        f"中 {len(medium_priority)} 条 (已摘要)\n\n"
        f"**分数分布**: 9.0+ {excellent}  |  8.0~8.9 {good}  |  7.0~7.9 {medium}  |  6.0~6.9 {pass_level}  |  <6.0 {low}\n\n"
        f"**数据源**: {source_breakdown}\n\n"
        f"**任务域覆盖**: {core_coverage_line}\n\n"
        f"**时效性**: ≤7天 {within_7d}条 ({percent_7d:.0f}%)  |  ≤14天 {within_14d}条 ({percent_14d:.0f}%)\n\n"
        f"[查看飞书表格]({constants.FEISHU_BENCH_TABLE_URL})"
    )

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📈 推送统计摘要"},
                "template": "blue",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
            ],
        },
    }
```

---

## 五、实施步骤

### Step 1: 更新常量配置（2分钟）

**文件**: `src/common/constants.py`

**操作**：
```python
# 在文件末尾添加（或替换现有配置）

# ==================== 推送卡片配置（方案B：两分区） ====================

# 核心任务域定义（10个全量域）
CORE_DOMAINS: Final[List[str]] = [
    "Coding",
    "Backend",
    "WebDev",
    "GUI",
    "ToolUse",
    "Collaboration",
    "LLM/AgentOps",
    "Reasoning",
    "DeepResearch",
    "Other",
]

# 主推荐区配置
MAIN_RECOMMENDATION_LIMIT: Final[int] = 12  # 最新推荐区最多12条

# 任务域补位配置
TASK_FILL_MIN_SCORE: Final[float] = 5.0  # 补位候选最低分数
TASK_FILL_PER_DOMAIN_LIMIT: Final[int] = 1  # 每个缺席域最多1条补位
TASK_FILL_SHOW_MISSING: Final[bool] = True  # 显示缺失域提示

# 候选格式化配置
TITLE_TRUNCATE_CARD: Final[int] = 60  # 标题截断60字符（中英混合）
```

**验证**：
```bash
.venv/bin/python -c "from src.common import constants; print(len(constants.CORE_DOMAINS))"
# 期望输出: 10
```

### Step 2: 添加辅助函数（5分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 在 `_primary_link()` 函数后添加：
  - `_format_source_badge()` - 来源Badge
  - `_get_primary_link_text()` - 链接文本

**代码**：详见4.2节

### Step 3: 重构中优摘要卡主函数（15分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
1. 备份现有 `_send_medium_priority_summary()` 函数（注释掉或重命名为 `_send_medium_priority_summary_old()`）
2. 替换为新实现（详见4.2节）
3. 替换 `_build_task_fill_section()` 为 `_build_task_fill_section_v2()`（详见4.2节）

**验证**：
```bash
# 检查函数签名
.venv/bin/python -c "
from src.notifier import FeishuNotifier
import inspect
sig = inspect.signature(FeishuNotifier._send_medium_priority_summary)
print(sig)
"
# 期望输出: (self, candidates: List[src.models.ScoredCandidate], low_candidates: Optional[List[src.models.ScoredCandidate]] = None, covered_domains: Optional[set[str]] = None) -> None
```

### Step 4: 更新统计摘要卡（5分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 替换 `_build_summary_card()` 函数（详见4.3节）

**验证**：
- 检查函数中是否包含"任务域覆盖"和"时效性"统计

### Step 5: 删除旧代码（2分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 删除或注释掉以下旧函数（不再使用）：
  - `_build_low_pick_section()` - 已移除Latest Papers分区
  - `_build_task_fill_section()` - 已替换为v2版本

### Step 6: 代码格式化（1分钟）

**操作**：
```bash
black src/notifier/feishu_notifier.py src/common/constants.py
ruff check --fix src/notifier/feishu_notifier.py src/common/constants.py
```

### Step 7: 完整流程测试（10分钟）

**操作**：
```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志
tail -100 logs/$(ls -t logs/ | head -n1)

# 期望看到：
# - "推送预过滤后: X条"
# - "最新推荐: 12条"（或更少）
# - "任务域补位: Y个域"（或"无需补位"）
```

---

## 六、测试验证

### 6.1 单元测试

**测试用例**：

1. **排序规则测试**
   - 输入：3个候选（3天前评分7.0, 5天前评分8.5, 3天前评分8.0）
   - 期望排序：3天前8.0 > 3天前7.0 > 5天前8.5

2. **补位逻辑测试**
   - 输入：主推荐区覆盖{Coding, Backend}，低优池有{WebDev 1条, GUI 0条}
   - 期望：补位区显示WebDev 1条，缺失提示"GUI"

3. **核心域覆盖统计测试**
   - 输入：qualified包含Coding 3条, WebDev 1条, Other 5条
   - 期望统计：✅Coding 3, ⚠️WebDev 1, ❌GUI 0, ❌ToolUse 0 ...

### 6.2 集成测试

**测试场景1：正常推送**
```bash
.venv/bin/python -m src.main
```
期望结果：
- 飞书中优摘要卡包含"最新推荐"分区（≤12条）
- 候选按时间优先排序（最新的在前面）
- 如果核心域缺失，补位区显示补位项和缺失提示

**测试场景2：全域覆盖**
- 构造测试数据：10个核心域各2条候选
- 期望：主推荐区12条，补位区为空（无缺失域）

**测试场景3：缺失域补位**
- 构造测试数据：仅Coding/Backend候选
- 期望：补位区显示WebDev/GUI/ToolUse等域的补位项（如果有）+ 缺失提示

### 6.3 手动验收检查清单

- [ ] 中优摘要卡只有2个分区（最新推荐 + 任务域补位）
- [ ] 最新推荐区最多12条
- [ ] 候选按时间优先排序（3天前排在5天前之前）
- [ ] 相同时间按相关性排序（相关8.5排在相关7.0之前）
- [ ] 补位区仅在核心域缺失时显示
- [ ] 补位项标记"补位"字样
- [ ] 缺失域提示正确（例如"⚠️ 本批缺失: GUI、DeepResearch"）
- [ ] 统计摘要显示10个核心域的覆盖状态（✅/⚠️/❌）
- [ ] 统计摘要显示时效性占比（≤7天 X%, ≤14天 Y%）
- [ ] arXiv论文链接点击跳转到paper_url
- [ ] GitHub项目链接点击跳转到url

---

## 七、成功标准

### 7.1 功能完整性

- [x] 主推荐区按"时间↑ → 相关性↓ → 总分↓"排序
- [x] 核心域扩展到10个（包含LLM/AgentOps/DeepResearch）
- [x] 补位区仅在核心域缺失时显示
- [x] 补位区标记"补位"字样
- [x] 缺失域提示功能
- [x] 统计摘要增强（任务域覆盖 + 时效性）

### 7.2 性能指标

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 最新候选优先展示 | 100% | 检查推送卡片，3天前候选排在5天前之前 |
| 核心域覆盖率 | ≥80% | 统计摘要卡"任务域覆盖"行 |
| 补位准确性 | 100% | 缺失域补位项任务域正确 |
| 卡片简洁性 | 2个分区 | 人工验收 |

### 7.3 代码质量

- [ ] 所有新增函数有中文注释
- [ ] 常量配置集中在 `constants.py`
- [ ] 函数嵌套层级 ≤3
- [ ] PEP8合规（运行`black`和`ruff`）

---

## 八、风险与应对

### 风险1: 某些核心域长期无候选

**问题**：DeepResearch/ToolUse等域可能长期无更新

**应对**：
- 补位区明确显示缺失提示（"⚠️ 本批缺失: DeepResearch"）
- 统计摘要用❌标记（"❌DeepResearch 0"）
- 接受现实：不强制推送低质量候选（total<5.0）

### 风险2: 所有候选都>30天

**问题**：某些时段可能无最近30天候选（数据源更新慢）

**应对**：
- 预过滤规则允许>30天但total≥8.0的候选通过
- 日志记录"推送预过滤: 0条（无符合时间窗口的候选）"
- 考虑降级策略：无候选时推送空卡片（或跳过推送）

### 风险3: 时间排序可能埋没高分项

**问题**：15天前的9.0分项排在3天前的6.0分项之后

**应对**：
- 这是设计预期："最新优先"目标
- 用户可以通过飞书表格按总分排序查看高分项
- 如需调整，可以修改排序规则权重

---

## 九、总结

### 9.1 设计亮点

1. **聚焦核心目标**：排序规则直接体现"最新且相关"
2. **简化分区**：2个分区（vs 原方案5个分区），降低认知负担
3. **兜底机制**：补位区保证核心域曝光，统计摘要明确标注缺失
4. **实施简单**：代码改动集中在1个主函数，工作量<30分钟

### 9.2 预期效果

- **最新候选优先展示**：3天前候选100%排在5天前之前
- **核心域覆盖保障**：10个核心域缺失时补位+提示
- **卡片简洁**：2个分区，用户扫视时间<30秒

### 9.3 工作量估算

- 开发时间：30分钟
- 测试时间：10分钟
- 总计：40分钟

---

## 十、附录

### A. 代码文件清单

| 文件 | 修改内容 | 行数变化 |
|------|----------|----------|
| `src/common/constants.py` | 新增配置 | +15行 |
| `src/notifier/feishu_notifier.py` | 重构中优摘要卡 + 统计增强 | +150行, -100行（删除旧代码） |

### B. 核心域列表（10个）

```python
CORE_DOMAINS = [
    "Coding",           # 代码生成/理解
    "Backend",          # 后端开发/数据库/性能
    "WebDev",           # Web开发/前端
    "GUI",              # 图形界面/桌面应用
    "ToolUse",          # 工具使用/API调用
    "Collaboration",    # 多智能体协作
    "LLM/AgentOps",     # LLM运维/部署
    "Reasoning",        # 推理/规划
    "DeepResearch",     # 深度研究/文献综述
    "Other",            # 其他领域
]
```

### C. 排序规则示例

**输入候选**：
```
A: arXiv, 3天前, relevance 8.5, total 7.2
B: GitHub, 5天前, relevance 7.5, total 8.1
C: arXiv, 3天前, relevance 7.0, total 6.8
D: HELM, 10天前, relevance 8.0, total 6.5
```

**排序结果**：
```
1. A (3天前, 相关8.5, 总分7.2)  ← 时间最新 + 相关性最高
2. C (3天前, 相关7.0, 总分6.8)  ← 时间相同，相关性次之
3. B (5天前, 相关7.5, 总分8.1)  ← 时间次新
4. D (10天前, 相关8.0, 总分6.5)  ← 时间最旧
```

---

**下一步行动**：
Codex根据本PRD实施代码修改，完成后提交代码并通知Claude Code进行测试验收。
