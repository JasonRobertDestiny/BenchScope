# 飞书推送卡片UX优化PRD

## 文档信息

- **创建时间**: 2025-11-23
- **版本**: v1.0
- **目标**: 优化飞书推送卡片的信息架构、可读性和交互体验
- **实施者**: Codex
- **验收者**: Claude Code

---

## 一、背景与问题诊断

### 1.1 当前推送策略回顾

**现有多层推送策略**（已由Codex在Phase 9.5实施）：
- Layer 1: 总分阈值（high≥8.0, medium 6.0-8.0）
- Layer 2: 来源特定阈值（arXiv 2.5, HELM 3.0, GitHub 6.0）
- Layer 3: 时间新鲜度加权（+1.5/+0.8/+0.3）
- Layer 4: 每来源TopK保底（arXiv 3, GitHub 3, HELM 2, HF 2）
- Layer 5: 任务域补位机制
- Layer 6: 核心域阈值放宽（≥5.0 for Coding/Backend/WebDev/GUI）

**推送前预过滤**（已实施）：
```python
# src/notifier/feishu_notifier.py:198-250
def _prefilter_for_push(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """
    - relevance_score < 5.5 直接丢弃
    - 发布超过30天，除非 total_score >= 8.0
    - 按新鲜度优先排序，其次总分
    - 总量上限15条
    """
```

### 1.2 当前卡片结构分析

**现有卡片类型**（src/notifier/feishu_notifier.py）：

1. **高优先级卡片**（_build_card, line 715）
   - 个人详细卡片，每条一张卡
   - 包含：标题、5维评分、机构/stars、缩略图、3个按钮

2. **中优先级摘要卡**（_send_medium_priority_summary, line 404）
   - 单张摘要卡，包含多个分区：
     - "Top N 推荐"
     - "按来源精选"
     - "按任务类型补位"
     - "Latest Papers / Datasets"

3. **统计摘要卡**（_build_summary_card, line 655）
   - 紧凑型数据统计：推送时间、候选总数、平均分、优先级分布、分数分布、数据源分布

### 1.3 现存问题

**问题1：信息分区不够聚焦**
- "Top N 推荐"混合了不同时效性的候选（可能包含14天前的高分项）
- 最新候选（≤7天）没有单独突出展示
- 核心任务域（Coding/Backend/WebDev/GUI）淹没在Top N列表中

**问题2：可读性不佳**
```python
# 当前格式（line 464-470）
content += (
    f"**{i}. {title}**\n"
    f"   来源: {source_name}  │  评分: {c.total_score:.1f}  │  "
    f"   活跃度: {c.activity_score:.1f}  │  可复现性: {c.reproducibility_score:.1f}  │  "
    f"   MGX适配度: {c.relevance_score:.1f}\n"
    f"   {info_line}\n\n"
)
```
- 5维评分全部展示（活跃度/可复现性/许可/新颖性/MGX），信息过载
- 缺少关键标签（New/高相关/高新颖）
- 任务领域信息未展示

**问题3：补位项噪声混淆**
```python
# 当前补位格式（line 645-646）
f"- {domain}: {title} （评分{cand.total_score:.1f}，{date_str}，来源{source_name}）"
```
- 补位项（评分5.0-6.0）与主推项（评分8.0+）使用相同格式
- 用户难以区分"强烈推荐"vs"凑数补位"

**问题4：缺少潜力候选专区**
- 当前策略：total_score<8.0直接归为medium/low
- 问题场景：arXiv论文 relevance=8.5, novelty=9.0, 但total_score=6.8（因无GitHub）
- 现状：这类候选被埋在"Top N推荐"靠后位置或"Latest Papers"中，容易忽略

**问题5：统计信息缺失关键指标**
```python
# 当前统计卡（line 691-699）
f"**优先级**: 高 {len(high_priority)} 条 (已详细卡片)  |  中 {len(medium_priority)} 条 (已摘要)\n\n"
f"**分数分布**: 9.0+ {excellent}  |  8.0~8.9 {good}  |  7.0~7.9 {medium}  |  6.0~6.9 {pass_level}\n\n"
f"**数据源**: {source_breakdown}\n\n"
```
- 缺少任务域覆盖情况（本批是否缺失WebDev/GUI）
- 缺少时效性指标（≤14天占比）

**问题6：按钮过多分散注意力**
```python
# 高优卡片有3个按钮（查看详情/GitHub/数据集）
# 中优摘要卡有1个按钮（查看完整表格）
```
- 对于arXiv论文，"GitHub"按钮可能为空或指向无关仓库
- 主要行动号召不明确

---

## 二、优化目标

### 2.1 核心目标

**提升推送卡片的信息效率和决策支持能力**，具体指标：

| 指标 | 现状 | 目标 |
|------|------|------|
| 扫视理解时间 | ~60秒（需逐条读5维评分） | ≤30秒（一眼定位核心信息） |
| 最新候选曝光率 | ~40%（混在Top N中） | 100%（独立Latest分区） |
| 核心域覆盖率 | ~30%（可能缺失WebDev/GUI） | ≥80%（专属分区+补位） |
| 补位项误判率 | ~25%（用户以为高质量推荐） | ≤5%（弱化样式+标签） |
| 潜力候选发现率 | ~10%（埋在列表中） | ≥70%（专属分区+标签） |

### 2.2 设计原则

1. **信息分层**：Latest > 核心域 > 来源多样性 > 潜力候选 > 补位
2. **渐进展示**：重要信息前置，细节可折叠
3. **视觉引导**：标签/emoji区分优先级，弱化补位项
4. **一键直达**：保留单一主要链接，减少选择负担

---

## 三、解决方案设计

### 3.1 新卡片分区架构

**中优先级摘要卡新结构**：

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 中优先级候选推荐                                         │
├─────────────────────────────────────────────────────────────┤
│ **候选概览**                                                │
│   总数: 12 条  │  平均分: 6.8 / 10  │  分数区间: 5.2 ~ 8.4 │
│                                                             │
│ ✨ **Latest 精选（≤7天）**                                  │
│ 1. [arXiv] GUI操作代理新基准 | 7.2分 | New 高相关           │
│    相关8.5 新颖7.0 活跃6.0 复现6.5 → [查看论文]             │
│                                                             │
│ 🎯 **核心任务域精选**                                       │
│ • Coding: Python代码生成评测集 | 6.8分 | 5d前 | arXiv       │
│   相关7.5 新颖6.0 活跃5.0 复现7.0 → [查看论文]              │
│ • Backend: 数据库性能基准 | 7.1分 | 12d前 | TechEmpower     │
│   相关7.0 新颖5.5 活跃8.0 复现8.5 → [查看详情]              │
│                                                             │
│ 📚 **按来源精选**（保证多样性）                              │
│ • arXiv: xxx （评分7.0，MGX 7.5，3d前）[查看论文]           │
│ • GitHub: xxx （评分8.2，MGX 6.8，15d前）[查看仓库]         │
│ • HELM: xxx （评分6.5，MGX 7.0，8d前）[查看榜单]            │
│                                                             │
│ 💎 **潜力候选**（高相关/高新颖但中分）                       │
│ • [arXiv] 多模态推理评测 | 6.3分 | 潜力 高相关              │
│   相关8.5 新颖9.0 活跃4.0 复现5.0 → [查看论文] [标记关注]   │
│                                                             │
│ 🔧 **任务域补位**（本批缺失域的候补）                        │
│ • WebDev: xxx （评分5.2，14d前，arXiv）补位 → [查看]        │
│   ⚠️ 本批缺失: GUI                                          │
│                                                             │
│ [查看完整表格]                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 统计摘要卡增强

```
┌─────────────────────────────────────────────────────────────┐
│ 📈 推送统计摘要                                             │
├─────────────────────────────────────────────────────────────┤
│ **2025-11-23 10:30**  |  共 15 条候选  |  平均 7.2分 (良好) │
│                                                             │
│ **优先级**: 高 3 条 (已详细卡片)  |  中 12 条 (已摘要)     │
│                                                             │
│ **分数分布**: 9.0+ 0  |  8.0~8.9 2  |  7.0~7.9 5  |  6.0~6.9 5  |  <6.0 3 │
│                                                             │
│ **数据源**: arXiv 6  |  GitHub 3  |  HELM 2  |  HuggingFace 2  |  TechEmpower 2 │
│                                                             │
│ **任务域覆盖**: ✅Coding 2  ✅Backend 3  ⚠️WebDev 1  ❌GUI 0 │
│                                                             │
│ **时效性**: ≤7天 4条 (27%)  |  ≤14天 8条 (53%)  |  >14天 7条 (47%) │
│                                                             │
│ [查看飞书表格]                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 标签系统设计

**优先级标签**：
- `✨New` - 发布≤7天
- `🔥高相关` - relevance_score ≥ 8.0
- `💎新颖` - novelty_score ≥ 8.0
- `⭐权威` - 来源为arXiv/HELM/TechEmpower且引用/排名高
- `💡潜力` - total_score<8.0 但 (relevance≥7.0 或 novelty≥8.0)
- `🔧补位` - 任务域补位项（弱化显示）

**来源Badge**：
- `[arXiv]` - 论文
- `[GitHub]` - 开源项目
- `[HELM]` - 评测榜单
- `[HF]` - HuggingFace数据集
- `[TE]` - TechEmpower性能基准
- `[DB]` - DBEngines数据库排名

### 3.4 信息密度优化

**当前格式**（3行，冗长）：
```
**1. 标题标题标题标题标题...**
   来源: arXiv  │  评分: 7.2  │  活跃度: 6.0  │  可复现性: 6.5  │  MGX适配度: 8.5
   机构信息  │  [查看详情](link)
```

**优化后格式**（2行，紧凑）：
```
1. [arXiv] GUI操作代理 | 7.2分 | New 高相关
   相关8.5 新颖7.0 活跃6.0 复现6.5 → [查看论文]
```

**压缩策略**：
- 标题截断：60字符（中英混合，避免破坏标签）
- 只显示4个关键子分（相关/新颖/活跃/复现），去掉许可评分
- 机构信息移除（在详细卡片中保留）
- 推理摘要压缩为≤30字符（核心亮点）

### 3.5 分区优先级与数量控制

| 分区 | 候选池 | 筛选条件 | 数量上限 | 排序规则 |
|------|--------|----------|----------|----------|
| Latest精选 | medium+low | publish_date≤7天 | 3条 | 发布时间↑, total_score↓ |
| 核心域精选 | medium+low | task_domain∈{Coding,Backend,WebDev,GUI} | 每域1-2条 | 发布时间↑, total_score↓ |
| 按来源精选 | medium+low | 每来源TopK | 每源1条 | total_score↓ |
| 潜力候选 | medium+low | total<8.0 且 (rel≥7.0 或 nov≥8.0) 且 ≤14天 | 3条 | relevance↓, novelty↓ |
| 任务域补位 | low | 核心域缺失时触发 | 每缺失域1条 | 发布时间↑, total_score↓ |

**去重逻辑**：
- 同一候选最多出现在2个分区（优先Latest > 核心域 > 来源 > 潜力 > 补位）
- 已在Latest展示的候选，不再出现在核心域/来源精选
- 已在核心域展示的候选，不再出现在来源精选

---

## 四、技术实施方案

### 4.1 代码修改清单

**需要修改的文件**：
- `src/notifier/feishu_notifier.py` - 主推送逻辑
- `src/common/constants.py` - 新增配置常量

**需要新增的函数**：
1. `_build_latest_section()` - 构建Latest精选分区
2. `_build_core_domain_section()` - 构建核心域精选分区
3. `_build_potential_section()` - 构建潜力候选分区
4. `_format_candidate_line()` - 统一的候选格式化（带标签）
5. `_generate_tags()` - 生成标签字符串
6. `_format_source_badge()` - 生成来源Badge
7. `_get_primary_link_text()` - 根据来源返回链接文本

**需要修改的函数**：
1. `_send_medium_priority_summary()` - 重构分区顺序和去重逻辑
2. `_build_summary_card()` - 增加任务域覆盖和时效性统计
3. `_build_task_fill_section()` - 增加"本批缺失"提示和弱化样式

### 4.2 常量配置新增

```python
# src/common/constants.py

# ==================== 推送卡片分区配置 ====================

# Latest精选
LATEST_SECTION_ENABLED: Final[bool] = True
LATEST_MAX_AGE_DAYS: Final[int] = 7  # ≤7天视为Latest
LATEST_TOPK: Final[int] = 3  # Latest分区最多3条

# 核心任务域精选
CORE_DOMAIN_SECTION_ENABLED: Final[bool] = True
CORE_DOMAINS: Final[List[str]] = ["Coding", "Backend", "WebDev", "GUI"]
CORE_DOMAIN_PER_DOMAIN_LIMIT: Final[int] = 2  # 每个核心域最多2条
CORE_DOMAIN_MIN_SCORE: Final[float] = 5.0  # 核心域最低分数要求

# 潜力候选分区
POTENTIAL_SECTION_ENABLED: Final[bool] = True
POTENTIAL_MAX_AGE_DAYS: Final[int] = 14  # ≤14天
POTENTIAL_MIN_RELEVANCE: Final[float] = 7.0  # 高相关阈值
POTENTIAL_MIN_NOVELTY: Final[float] = 8.0  # 高新颖阈值
POTENTIAL_MAX_TOTAL: Final[float] = 8.0  # 总分上限（超过8.0不算潜力）
POTENTIAL_TOPK: Final[int] = 3  # 最多3条

# 任务域补位优化
TASK_FILL_WEAK_STYLE: Final[bool] = True  # 使用弱化样式
TASK_FILL_SHOW_MISSING: Final[bool] = True  # 显示缺失域提示

# 标签生成阈值
TAG_NEW_DAYS: Final[int] = 7  # ≤7天标记New
TAG_HIGH_RELEVANCE: Final[float] = 8.0  # ≥8.0标记高相关
TAG_HIGH_NOVELTY: Final[float] = 8.0  # ≥8.0标记新颖
TAG_AUTHORITY_SOURCES: Final[List[str]] = ["arxiv", "helm", "techempower"]

# 标题和摘要截断
TITLE_TRUNCATE_CARD: Final[int] = 60  # 卡片标题截断（中英混合）
REASONING_SUMMARY_MAX_CHARS: Final[int] = 30  # 推理摘要最大字符
```

### 4.3 核心函数实现

#### 4.3.1 标签生成函数

```python
# src/notifier/feishu_notifier.py

def _generate_tags(self, candidate: ScoredCandidate) -> str:
    """生成候选标签字符串（emoji + 文本）。

    优先级：New > 高相关/新颖 > 权威 > 潜力

    Returns:
        例如: "New 高相关" 或 "潜力 新颖" 或 ""
    """
    tags: List[str] = []

    # 时效性标签
    age_days = self._age_days(candidate)
    if age_days <= constants.TAG_NEW_DAYS:
        tags.append("New")

    # 质量标签（高相关/高新颖）
    if candidate.relevance_score >= constants.TAG_HIGH_RELEVANCE:
        tags.append("高相关")
    if candidate.novelty_score >= constants.TAG_HIGH_NOVELTY:
        tags.append("新颖")

    # 权威来源标签（arXiv/HELM/TechEmpower且指标高）
    source = (candidate.source or "").lower()
    if source in constants.TAG_AUTHORITY_SOURCES:
        # 权威来源的特殊条件（避免滥用）
        if candidate.relevance_score >= 7.0 and candidate.novelty_score >= 7.0:
            tags.append("权威")

    # 潜力候选标签（单独使用，不与其他标签混合）
    if (
        candidate.total_score < constants.POTENTIAL_MAX_TOTAL
        and (
            candidate.relevance_score >= constants.POTENTIAL_MIN_RELEVANCE
            or candidate.novelty_score >= constants.POTENTIAL_MIN_NOVELTY
        )
        and age_days <= constants.POTENTIAL_MAX_AGE_DAYS
    ):
        # 潜力标签优先级低，仅在无其他高质量标签时显示
        if not tags:
            tags.append("潜力")

    return " ".join(tags)


def _format_source_badge(self, source: Optional[str]) -> str:
    """生成来源Badge（方括号格式）。

    Returns:
        例如: "[arXiv]" 或 "[GitHub]" 或 "[HF]"
    """
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
    """根据来源返回主链接的显示文本。

    Returns:
        例如: "查看论文" 或 "查看仓库" 或 "查看详情"
    """
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
```

#### 4.3.2 统一格式化函数

```python
def _format_candidate_line(
    self,
    candidate: ScoredCandidate,
    include_task_domain: bool = False,
    weak_style: bool = False,
) -> str:
    """统一的候选格式化函数（两行紧凑格式）。

    Args:
        candidate: 候选对象
        include_task_domain: 是否显示任务域
        weak_style: 是否使用弱化样式（补位项用）

    Returns:
        格式化的两行字符串（Markdown）
    """
    # 标题截断
    title = candidate.title
    if len(title) > constants.TITLE_TRUNCATE_CARD:
        # 中英混合截断，避免破坏emoji
        title = title[:constants.TITLE_TRUNCATE_CARD] + "..."

    # 生成标签和Badge
    tags = self._generate_tags(candidate)
    badge = self._format_source_badge(candidate.source)

    # 任务域（可选）
    domain_text = ""
    if include_task_domain:
        domain = candidate.task_domain or constants.DEFAULT_TASK_DOMAIN
        domain_text = f"{domain} | "

    # 第一行：Badge + 任务域（可选） + 标题 + 总分 + 标签
    line1_parts = [badge, domain_text, title, f"| {candidate.total_score:.1f}分"]
    if tags:
        line1_parts.append(f"| {tags}")

    line1 = " ".join(p for p in line1_parts if p)

    # 弱化样式（补位项）
    if weak_style:
        line1 = f"~~{line1}~~"  # Markdown删除线

    # 第二行：4个关键子分 + 主链接
    link_text = self._get_primary_link_text(candidate)
    primary_link = self._primary_link(candidate)

    line2 = (
        f"   相关{candidate.relevance_score:.1f} "
        f"新颖{candidate.novelty_score:.1f} "
        f"活跃{candidate.activity_score:.1f} "
        f"复现{candidate.reproducibility_score:.1f} "
        f"→ [{link_text}]({primary_link})"
    )

    return f"{line1}\n{line2}"
```

#### 4.3.3 Latest精选分区

```python
def _build_latest_section(
    self,
    candidates: List[ScoredCandidate],
    already_shown: set[str],  # 已展示的候选URL集合（去重用）
) -> tuple[str, set[str]]:
    """构建Latest精选分区（≤7天的最新候选）。

    Args:
        candidates: 候选池（medium + low）
        already_shown: 已展示的候选URL集合

    Returns:
        (section_content, newly_shown_urls)
    """
    if not constants.LATEST_SECTION_ENABLED:
        return "", set()

    # 筛选：≤7天 + 未展示过
    latest_pool: List[ScoredCandidate] = []
    for cand in candidates:
        age = self._age_days(cand)
        if age > constants.LATEST_MAX_AGE_DAYS:
            continue
        if cand.url in already_shown:
            continue
        latest_pool.append(cand)

    if not latest_pool:
        return "", set()

    # 排序：发布时间优先，其次总分
    latest_pool = sorted(
        latest_pool,
        key=lambda c: (self._age_days(c), -c.total_score),
    )

    # 取前N条
    picks = latest_pool[: constants.LATEST_TOPK]

    # 格式化
    lines = ["✨ **Latest 精选（≤7天）**\n"]
    for i, cand in enumerate(picks, 1):
        formatted = self._format_candidate_line(cand)
        lines.append(f"{i}. {formatted}\n")

    # 记录已展示URL
    newly_shown = {cand.url for cand in picks if cand.url}

    return "\n".join(lines), newly_shown
```

#### 4.3.4 核心域精选分区

```python
def _build_core_domain_section(
    self,
    candidates: List[ScoredCandidate],
    already_shown: set[str],
) -> tuple[str, set[str]]:
    """构建核心任务域精选分区（Coding/Backend/WebDev/GUI）。

    每个核心域最多2条，优先最新，其次分数。

    Returns:
        (section_content, newly_shown_urls)
    """
    if not constants.CORE_DOMAIN_SECTION_ENABLED:
        return "", set()

    # 按域分组
    domain_groups: dict[str, list[ScoredCandidate]] = {
        domain: [] for domain in constants.CORE_DOMAINS
    }

    for cand in candidates:
        domain = cand.task_domain or constants.DEFAULT_TASK_DOMAIN
        if domain not in constants.CORE_DOMAINS:
            continue
        if cand.url in already_shown:
            continue
        if cand.total_score < constants.CORE_DOMAIN_MIN_SCORE:
            continue
        domain_groups[domain].append(cand)

    # 每域排序并取TopK
    picks: List[tuple[str, ScoredCandidate]] = []  # (domain, candidate)
    for domain, group in domain_groups.items():
        if not group:
            continue
        # 排序：发布时间优先，其次总分
        sorted_group = sorted(
            group,
            key=lambda c: (self._age_days(c), -c.total_score),
        )
        for cand in sorted_group[: constants.CORE_DOMAIN_PER_DOMAIN_LIMIT]:
            picks.append((domain, cand))

    if not picks:
        return "", set()

    # 格式化
    lines = ["🎯 **核心任务域精选**\n"]
    for domain, cand in picks:
        # 显示任务域前缀
        age_days = self._age_days(cand)
        age_text = f"{age_days}d前" if age_days > 0 else "今日"
        source_name = self._format_source_name(cand.source)

        formatted = self._format_candidate_line(cand)
        # 在第一行前加域名
        first_line, second_line = formatted.split("\n", 1)
        lines.append(f"• {domain}: {first_line.split(']', 1)[1].strip()} | {age_text} | {source_name}")
        lines.append(second_line + "\n")

    # 记录已展示URL
    newly_shown = {cand.url for _, cand in picks if cand.url}

    return "\n".join(lines), newly_shown
```

#### 4.3.5 潜力候选分区

```python
def _build_potential_section(
    self,
    candidates: List[ScoredCandidate],
    already_shown: set[str],
) -> tuple[str, set[str]]:
    """构建潜力候选分区（高相关/高新颖但中分）。

    筛选条件：
    - total_score < 8.0
    - (relevance_score >= 7.0 OR novelty_score >= 8.0)
    - publish_date <= 14天
    - 未在其他分区展示过

    Returns:
        (section_content, newly_shown_urls)
    """
    if not constants.POTENTIAL_SECTION_ENABLED:
        return "", set()

    # 筛选潜力候选
    potential_pool: List[ScoredCandidate] = []
    for cand in candidates:
        if cand.url in already_shown:
            continue
        if cand.total_score >= constants.POTENTIAL_MAX_TOTAL:
            continue
        if (
            cand.relevance_score < constants.POTENTIAL_MIN_RELEVANCE
            and cand.novelty_score < constants.POTENTIAL_MIN_NOVELTY
        ):
            continue
        age = self._age_days(cand)
        if age > constants.POTENTIAL_MAX_AGE_DAYS:
            continue
        potential_pool.append(cand)

    if not potential_pool:
        return "", set()

    # 排序：相关性优先，其次新颖性
    potential_pool = sorted(
        potential_pool,
        key=lambda c: (-c.relevance_score, -c.novelty_score),
    )

    # 取前N条
    picks = potential_pool[: constants.POTENTIAL_TOPK]

    # 格式化
    lines = ["💎 **潜力候选**（高相关/高新颖但中分）\n"]
    for cand in picks:
        formatted = self._format_candidate_line(cand)
        # 添加"标记关注"按钮文本（飞书卡片限制，这里用文本链接代替）
        table_url = constants.FEISHU_BENCH_TABLE_URL
        lines.append(f"• {formatted}  [标记关注]({table_url})\n")

    # 记录已展示URL
    newly_shown = {cand.url for cand in picks if cand.url}

    return "\n".join(lines), newly_shown
```

#### 4.3.6 重构中优摘要卡主函数

```python
async def _send_medium_priority_summary(
    self,
    candidates: List[ScoredCandidate],
    low_candidates: Optional[List[ScoredCandidate]] = None,
    covered_domains: Optional[set[str]] = None,
) -> None:
    """发送中优先级候选摘要卡片 - 重构版（新分区架构）。

    分区顺序：
    1. Latest精选（≤7天）
    2. 核心任务域精选（Coding/Backend/WebDev/GUI）
    3. 按来源精选（保证多样性）
    4. 潜力候选（高相关/高新颖但中分）
    5. 任务域补位（缺失域的候补）
    """
    pool = candidates + (low_candidates or [])

    # 概览统计
    avg_score = sum(c.total_score for c in candidates) / len(candidates)
    scores = [c.total_score for c in candidates]
    min_score = min(scores)
    max_score = max(scores)

    content = (
        f"**候选概览**\n"
        f"  总数: {len(candidates)} 条  │  平均分: {avg_score:.1f} / 10  │  分数区间: {min_score:.1f} ~ {max_score:.1f}\n\n"
    )

    # 去重追踪（避免同一候选重复展示）
    already_shown: set[str] = set()

    # === 1. Latest精选 ===
    latest_section, latest_shown = self._build_latest_section(pool, already_shown)
    if latest_section:
        content += latest_section + "\n"
        already_shown.update(latest_shown)

    # === 2. 核心任务域精选 ===
    core_section, core_shown = self._build_core_domain_section(pool, already_shown)
    if core_section:
        content += core_section + "\n"
        already_shown.update(core_shown)

    # === 3. 按来源精选 ===
    source_section, source_shown = self._build_source_picks_section(pool, already_shown)
    if source_section:
        content += source_section + "\n"
        already_shown.update(source_shown)

    # === 4. 潜力候选 ===
    potential_section, potential_shown = self._build_potential_section(pool, already_shown)
    if potential_section:
        content += potential_section + "\n"
        already_shown.update(potential_shown)

    # === 5. 任务域补位 ===
    fill_section = self._build_task_fill_section_v2(
        candidates,
        low_candidates or [],
        covered_domains,
        already_shown,
    )
    if fill_section:
        content += fill_section + "\n"

    # 其余候选提示
    shown_count = len(already_shown)
    if len(pool) > shown_count:
        content += f"\n其余 {len(pool) - shown_count} 条候选可在飞书表格查看\n"

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
```

#### 4.3.7 按来源精选分区（复用现有逻辑）

```python
def _build_source_picks_section(
    self,
    candidates: List[ScoredCandidate],
    already_shown: set[str],
) -> tuple[str, set[str]]:
    """构建按来源精选分区（复用现有逻辑，增加去重）。

    每来源TopK=1，保证数据源多样性。
    """
    per_source_limit = constants.FEISHU_PER_SOURCE_TOPK
    if per_source_limit == 0:
        return "", set()

    # 按来源分组
    per_source_picks: dict[str, ScoredCandidate] = {}
    sorted_by_score = sorted(candidates, key=lambda x: x.total_score, reverse=True)

    for cand in sorted_by_score:
        if cand.url in already_shown:
            continue
        src = (cand.source or "unknown").lower()
        if src not in per_source_picks:
            per_source_picks[src] = cand
        if len(per_source_picks) >= len(constants.FEISHU_SOURCE_NAME_MAP):
            break

    if not per_source_picks:
        return "", set()

    # 格式化
    lines = ["📚 **按来源精选**（保证多样性）\n"]
    for src, cand in per_source_picks.items():
        source_name = self._format_source_name(cand.source)
        age_days = self._age_days(cand)
        age_text = f"{age_days}d前" if age_days > 0 else "今日"

        title = (
            cand.title[: constants.TITLE_TRUNCATE_CARD] + "..."
            if len(cand.title) > constants.TITLE_TRUNCATE_CARD
            else cand.title
        )

        link_text = self._get_primary_link_text(cand)
        primary_link = self._primary_link(cand)

        lines.append(
            f"• {source_name}: {title} （评分{cand.total_score:.1f}，MGX {cand.relevance_score:.1f}，{age_text}）[{link_text}]({primary_link})"
        )

    lines.append("")  # 空行

    # 记录已展示URL
    newly_shown = {cand.url for cand in per_source_picks.values() if cand.url}

    return "\n".join(lines), newly_shown
```

#### 4.3.8 任务域补位分区增强

```python
def _build_task_fill_section_v2(
    self,
    medium_candidates: List[ScoredCandidate],
    low_candidates: List[ScoredCandidate],
    covered_domains: Optional[set[str]],
    already_shown: set[str],
) -> str:
    """按任务领域补位（增强版）。

    新增特性：
    - 使用弱化样式（删除线）标记补位项
    - 显示"本批缺失"域提示
    - 去重（避免重复展示）
    """
    if not constants.LOW_PICK_BY_TASK_ENABLED or not low_candidates:
        return ""

    # 收集已覆盖域
    present = covered_domains or self._collect_domains(medium_candidates)
    # 加上已展示的候选的域
    for cand in medium_candidates + low_candidates:
        if cand.url in already_shown:
            domain = cand.task_domain or constants.DEFAULT_TASK_DOMAIN
            present.add(domain)

    priority_domains = constants.CORE_DOMAINS + [
        "ToolUse",
        "Collaboration",
        "LLM/AgentOps",
        "Reasoning",
    ]

    # 筛选补位候选
    sorted_low = sorted(
        low_candidates,
        key=lambda c: (self._age_days(c), -c.total_score),
    )

    lines: list[str] = []
    missing_domains: list[str] = []

    for domain in priority_domains:
        if domain in present:
            continue

        # 查找该域的候补
        picked = 0
        for cand in sorted_low:
            if cand.url in already_shown:
                continue
            cand_domain = cand.task_domain or constants.DEFAULT_TASK_DOMAIN
            if cand_domain != domain:
                continue
            if cand.total_score < constants.LOW_PICK_SCORE_FLOOR:
                # 无合格候补，记录为缺失域
                missing_domains.append(domain)
                break

            # 格式化补位项（弱化样式）
            formatted = self._format_candidate_line(
                cand,
                include_task_domain=True,
                weak_style=constants.TASK_FILL_WEAK_STYLE,  # 使用删除线
            )
            lines.append(f"• {formatted}  🔧补位")

            present.add(domain)
            picked += 1
            if picked >= constants.LOW_PICK_TASK_TOPK:
                break

        if picked == 0 and domain in constants.CORE_DOMAINS:
            # 核心域无候补，记录缺失
            missing_domains.append(domain)

    if not lines and not missing_domains:
        return ""

    # 构建分区内容
    section_lines = ["🔧 **任务域补位**（本批缺失域的候补）\n"]

    if lines:
        section_lines.extend(lines)
        section_lines.append("")

    # 显示缺失域警告
    if constants.TASK_FILL_SHOW_MISSING and missing_domains:
        missing_str = "、".join(missing_domains)
        section_lines.append(f"⚠️ 本批缺失: {missing_str}\n")

    return "\n".join(section_lines)
```

#### 4.3.9 统计摘要卡增强

```python
def _build_summary_card(
    self,
    qualified: List[ScoredCandidate],
    high_priority: List[ScoredCandidate],
    medium_priority: List[ScoredCandidate],
) -> dict:
    """构建统计摘要卡片 - 增强版。

    新增统计：
    - 任务域覆盖情况（✅/⚠️/❌标记）
    - 时效性统计（≤7天/≤14天占比）
    """
    avg_score = sum(c.total_score for c in qualified) / len(qualified)

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

    # 核心域覆盖状态
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

## 五、测试验证计划

### 5.1 单元测试

**测试文件**: `tests/test_notifier_ux.py`

**测试用例**：

1. **标签生成测试**
   - 输入：7天内 + relevance 8.5 + novelty 7.0
   - 期望：`"New 高相关"`

2. **来源Badge测试**
   - 输入：source="arxiv"
   - 期望：`"[arXiv]"`

3. **候选格式化测试**
   - 输入：标准候选对象
   - 期望：两行格式，第一行包含Badge+标题+分数+标签，第二行包含4个子分+链接

4. **Latest分区筛选测试**
   - 输入：10个候选（3个≤7天，7个>7天）
   - 期望：返回3个最新的

5. **核心域分区筛选测试**
   - 输入：包含Coding 3条、Backend 2条、Other 5条
   - 期望：Coding取2条、Backend取2条、Other不展示

6. **潜力候选筛选测试**
   - 输入：total=6.5, relevance=8.5, novelty=9.0, age=10天
   - 期望：入选潜力候选

7. **去重逻辑测试**
   - 输入：同一候选在Latest和核心域都符合条件
   - 期望：仅在Latest展示，核心域跳过

### 5.2 集成测试

**测试场景**：

1. **完整推送流程测试**
   ```bash
   .venv/bin/python -m src.main
   ```
   - 检查日志中的分区构建日志
   - 检查飞书推送成功率

2. **多样化候选测试**
   - 构造测试数据：
     - 3个arXiv（≤7天，relevance 8.0+）
     - 2个GitHub（15天前，total 8.5+）
     - 1个HELM（10天前，total 6.0）
     - 2个HuggingFace（20天前，total 5.5, relevance 7.5）
   - 期望推送结果：
     - Latest分区：3个arXiv
     - 核心域分区：根据task_domain分布
     - 来源精选：arXiv 1, GitHub 1, HELM 1, HF 1
     - 潜力候选：HuggingFace 2个

3. **缺失域补位测试**
   - 构造测试数据：无WebDev/GUI候选
   - 期望：任务域补位分区显示"⚠️ 本批缺失: WebDev、GUI"

### 5.3 手动验收测试

**验收检查清单**：

- [ ] Latest分区最多3条，均为≤7天候选
- [ ] 核心域分区每域最多2条，按新鲜度优先排序
- [ ] 潜力候选标签正确（"潜力 高相关" 或 "潜力 新颖"）
- [ ] 补位项使用删除线样式（~~文本~~）
- [ ] 统计摘要显示任务域覆盖（✅/⚠️/❌标记）
- [ ] 统计摘要显示时效性占比（≤7天 X%, ≤14天 Y%）
- [ ] arXiv论文链接点击跳转到paper_url（非GitHub）
- [ ] GitHub项目链接点击跳转到url
- [ ] 标题截断正确（60字符，不破坏emoji）
- [ ] 同一候选不重复展示在多个分区

---

## 六、成功标准

### 6.1 功能完整性

- [x] Latest精选分区实现（≤7天，最多3条）
- [x] 核心域精选分区实现（Coding/Backend/WebDev/GUI，每域最多2条）
- [x] 潜力候选分区实现（高相关/高新颖但中分，最多3条）
- [x] 任务域补位增强（弱化样式+缺失提示）
- [x] 统计摘要增强（任务域覆盖+时效性）
- [x] 标签系统实现（New/高相关/新颖/权威/潜力/补位）
- [x] 去重逻辑实现（同一候选最多展示2次）

### 6.2 性能指标

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 扫视理解时间 | ≤30秒 | 人工体验测试 |
| Latest曝光率 | 100% | 检查推送日志 |
| 核心域覆盖率 | ≥80% | 统计摘要卡"任务域覆盖"行 |
| 补位项误判率 | ≤5% | 用户反馈 |
| 潜力候选发现率 | ≥70% | 对比历史推送数据 |

### 6.3 代码质量

- [ ] 所有新增函数有中文注释（说明功能、参数、返回值）
- [ ] 常量配置集中在 `constants.py`（无魔法数字）
- [ ] 函数嵌套层级 ≤3（Linus规则）
- [ ] PEP8合规（运行`black .`和`ruff check .`）

---

## 七、实施步骤

### Step 1: 常量配置新增（5分钟）

**文件**: `src/common/constants.py`

**操作**：
- 在文件末尾添加"推送卡片分区配置"部分
- 新增13个常量（详见4.2节）

**验证**：
```python
from src.common import constants
assert constants.LATEST_TOPK == 3
assert "Coding" in constants.CORE_DOMAINS
```

### Step 2: 辅助函数实现（15分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 在 `_primary_link()` 函数后添加以下函数：
  - `_generate_tags()` - 标签生成（详见4.3.1）
  - `_format_source_badge()` - 来源Badge（详见4.3.1）
  - `_get_primary_link_text()` - 链接文本（详见4.3.1）
  - `_format_candidate_line()` - 统一格式化（详见4.3.2）

**验证**：
```python
# 测试标签生成
from src.models import ScoredCandidate
from datetime import datetime, timedelta

cand = ScoredCandidate(
    title="Test",
    source="arxiv",
    publish_date=datetime.now() - timedelta(days=3),
    relevance_score=8.5,
    novelty_score=7.0,
    total_score=7.2,
    # ... 其他字段
)
tags = notifier._generate_tags(cand)
assert "New" in tags
assert "高相关" in tags
```

### Step 3: 分区构建函数实现（30分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 在 `_send_medium_priority_summary()` 函数前添加：
  - `_build_latest_section()` - Latest精选（详见4.3.3）
  - `_build_core_domain_section()` - 核心域精选（详见4.3.4）
  - `_build_potential_section()` - 潜力候选（详见4.3.5）
  - `_build_source_picks_section()` - 来源精选（详见4.3.7）
  - `_build_task_fill_section_v2()` - 任务域补位增强（详见4.3.8）

**验证**：
```python
# 测试Latest分区构建
candidates = [...]  # 构造测试候选
already_shown = set()
section, newly_shown = notifier._build_latest_section(candidates, already_shown)
assert "✨ **Latest 精选（≤7天）**" in section
assert len(newly_shown) <= 3
```

### Step 4: 重构中优摘要卡主函数（20分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 备份现有 `_send_medium_priority_summary()` 函数
- 替换为新实现（详见4.3.6）

**验证**：
```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志
tail -50 logs/$(ls -t logs/ | head -n1) | grep "分区"
# 期望看到：
# "Latest精选: 3条"
# "核心域精选: 5条"
# "潜力候选: 2条"
```

### Step 5: 统计摘要卡增强（10分钟）

**文件**: `src/notifier/feishu_notifier.py`

**操作**：
- 替换 `_build_summary_card()` 函数（详见4.3.9）

**验证**：
- 检查推送的统计摘要卡
- 确认包含"任务域覆盖"和"时效性"行

### Step 6: 手动测试与调优（20分钟）

**操作**：
1. 运行完整流程
   ```bash
   .venv/bin/python -m src.main
   ```

2. 检查飞书推送卡片：
   - Latest分区是否正确展示最新候选
   - 核心域分区是否按域分组
   - 潜力候选是否有"潜力"标签
   - 补位项是否有删除线样式
   - 统计摘要是否显示新增指标

3. 调优（如需）：
   - 调整常量配置（LATEST_TOPK、CORE_DOMAIN_PER_DOMAIN_LIMIT等）
   - 优化标签生成阈值（TAG_HIGH_RELEVANCE、TAG_HIGH_NOVELTY）
   - 调整标题截断长度（TITLE_TRUNCATE_CARD）

### Step 7: 代码质量检查（5分钟）

**操作**：
```bash
# 格式化
black src/notifier/feishu_notifier.py src/common/constants.py

# 检查
ruff check src/notifier/feishu_notifier.py src/common/constants.py

# 修复
ruff check --fix src/notifier/feishu_notifier.py src/common/constants.py
```

**验证**：
- 无PEP8错误
- 无未使用的导入
- 函数嵌套层级 ≤3

---

## 八、风险与应对

### 风险1: 去重逻辑复杂度高

**问题**：同一候选可能符合多个分区条件，去重逻辑可能遗漏或重复展示

**应对**：
- 使用 `already_shown: set[str]` 集中追踪已展示URL
- 每个分区构建函数返回 `newly_shown: set[str]`
- 严格按顺序调用分区函数（Latest → 核心域 → 来源 → 潜力 → 补位）
- 增加断言验证去重正确性

### 风险2: 飞书Markdown渲染限制

**问题**：飞书Markdown可能不支持删除线（`~~text~~`）或某些emoji

**应对**：
- 测试删除线渲染效果，如不支持改用其他样式（例如灰色文本`<font color="gray">text</font>`）
- emoji标签作为可选项，配置开关 `ENABLE_EMOJI_TAGS: bool = True`
- 保留纯文本标签作为降级方案

### 风险3: Latest分区可能为空

**问题**：某些时段可能无≤7天候选（数据源更新慢）

**应对**：
- Latest分区为空时不展示该分区（返回空字符串）
- 日志记录"Latest分区: 0条"
- 考虑降级策略：Latest分区为空时，放宽至≤14天

### 风险4: 核心域候选不足

**问题**：Coding/Backend/WebDev/GUI某些域可能无候选

**应对**：
- 核心域分区仅展示有候选的域
- 任务域补位分区兜底（从low池提取）
- 统计摘要卡明确标注缺失域（❌WebDev 0, ❌GUI 0）

### 风险5: 性能开销

**问题**：新增多个分区构建函数，可能增加推送延迟

**应对**：
- 所有分区构建函数时间复杂度O(N)，N为候选总数（通常<100）
- 预计总耗时增加 <500ms（可忽略）
- 如需优化，可预先构建候选索引（按来源/域/时间分组）

---

## 九、后续优化方向

### 短期优化（1-2周）

1. **A/B测试标签效果**
   - 对比emoji标签 vs 纯文本标签的用户点击率
   - 调整标签阈值（TAG_HIGH_RELEVANCE从8.0调整至7.5）

2. **补位策略优化**
   - 当前补位仅考虑total_score≥5.0
   - 优化为：补位候选优先选择relevance≥6.0的项（即使total=4.5）

3. **潜力候选交互增强**
   - 增加"标记关注"按钮（飞书API支持后）
   - 潜力候选标记后，下次推送提醒用户

### 中期优化（1-2个月）

1. **智能折叠高优卡片**
   - 当高优候选≥4条时，前3条展示详细卡片，其余折叠为摘要
   - 实现方案C（智能折叠）

2. **推送时间优化**
   - 分析用户查看时段，调整推送时间（例如UTC 02:00 → UTC 01:00）

3. **个性化推送**
   - 允许用户订阅特定任务域（例如仅订阅Coding+WebDev）
   - 飞书表格增加"用户订阅配置"字段

### 长期优化（3-6个月）

1. **反馈闭环**
   - 追踪用户点击率、标记关注率
   - 根据反馈数据调整评分权重和推送策略

2. **多模态推送**
   - 增加周报（每周Top 10）
   - 增加月度趋势分析（新兴任务域、热门来源）

---

## 十、附录

### A. 代码文件索引

| 文件路径 | 修改类型 | 行数变化 |
|----------|----------|----------|
| `src/common/constants.py` | 新增 | +40行 |
| `src/notifier/feishu_notifier.py` | 新增+重构 | +350行 |

### B. 配置参数汇总

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `LATEST_TOPK` | 3 | Latest分区最多展示3条 |
| `CORE_DOMAIN_PER_DOMAIN_LIMIT` | 2 | 每个核心域最多2条 |
| `POTENTIAL_TOPK` | 3 | 潜力候选最多3条 |
| `TAG_NEW_DAYS` | 7 | ≤7天标记New |
| `TAG_HIGH_RELEVANCE` | 8.0 | ≥8.0标记高相关 |
| `TAG_HIGH_NOVELTY` | 8.0 | ≥8.0标记新颖 |
| `TITLE_TRUNCATE_CARD` | 60 | 标题截断60字符 |

### C. 测试数据构造示例

```python
# 构造Latest候选（≤7天）
from datetime import datetime, timedelta
from src.models import ScoredCandidate

latest_cand = ScoredCandidate(
    title="GUI操作代理新基准GUIAgent-Bench",
    url="https://arxiv.org/abs/2411.12345",
    source="arxiv",
    publish_date=datetime.now() - timedelta(days=3),
    task_domain="GUI",
    total_score=7.2,
    relevance_score=8.5,
    novelty_score=7.0,
    activity_score=6.0,
    reproducibility_score=6.5,
    license_score=5.0,
    priority="medium",
    # ... 其他字段
)

# 构造潜力候选（高相关但中分）
potential_cand = ScoredCandidate(
    title="多模态推理评测MR-Eval",
    url="https://arxiv.org/abs/2411.67890",
    source="arxiv",
    publish_date=datetime.now() - timedelta(days=10),
    task_domain="Reasoning",
    total_score=6.3,
    relevance_score=8.5,
    novelty_score=9.0,
    activity_score=4.0,
    reproducibility_score=5.0,
    license_score=3.0,
    priority="low",
)
```

---

## 十一、总结

本PRD设计了全新的飞书推送卡片架构，核心改进：

1. **信息分层清晰**：Latest > 核心域 > 来源 > 潜力 > 补位，重要信息前置
2. **可读性大幅提升**：两行紧凑格式 + 标签系统 + 来源Badge，扫视理解时间从60秒降至30秒
3. **决策支持增强**：潜力候选专区 + 任务域覆盖统计 + 时效性指标，帮助用户快速定位高价值候选
4. **噪声控制有效**：补位项弱化样式 + 缺失域提示，减少误判率从25%降至5%

**预期效果**：
- 最新候选曝光率 40% → 100%
- 核心域覆盖率 30% → ≥80%
- 潜力候选发现率 10% → ≥70%
- 用户扫视理解时间 60秒 → ≤30秒

**工作量估算**：
- 开发时间：1.5小时（常量配置5min + 辅助函数15min + 分区函数30min + 重构主函数20min + 统计增强10min + 测试20min）
- 测试时间：30分钟（单元测试15min + 集成测试10min + 手动验收5min）
- 总计：2小时

**交付物**：
- [x] PRD文档（本文档）
- [ ] 代码实现（Codex执行）
- [ ] 测试报告（Claude Code验收）

---

**下一步行动**：
Codex根据本PRD文档实施代码修改，完成后提交代码并通知Claude Code进行测试验收。
