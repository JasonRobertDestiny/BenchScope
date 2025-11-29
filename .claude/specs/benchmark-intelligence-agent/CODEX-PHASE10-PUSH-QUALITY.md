# CODEX-PHASE10: 推送质量优化

**文档版本**: v1.0
**创建时间**: 2025-11-29
**目标**: 减少Other领域噪音，提升核心领域Benchmark占比

---

## 一、问题诊断

### 1.1 今日推送数据分析（2025-11-29）

| 指标 | 实际值 | 期望值 | 问题严重度 |
|------|--------|--------|-----------|
| Other领域占比 | 46% (7/15) | ≤20% | 严重 |
| 核心领域占比 | 20% (3/15) | ≥60% | 严重 |
| 相关性=6.0占比 | 60% (9/15) | ≤20% | 严重 |
| 新颖度≥8.0占比 | 100% (15/15) | ≤50% | 中等 |
| 真Benchmark占比 | ~20% | ≥60% | 严重 |

### 1.2 问题候选样例

**典型噪音候选（应被过滤）**：

| 标题 | 领域 | 相关性 | 问题 |
|------|------|--------|------|
| Qwen3-VL Technical Report | Other | 6.0 | 技术报告，非Benchmark |
| Digital Twin-Driven Secure Access Strategy... | Other | 7.0 | IoT论文，与MGX无关 |
| Context-Aware Pragmatic Metacognitive... | Other | 6.0 | Sarcasm Detection，NLP任务 |
| Model-Based Policy Adaptation... | Other | 7.0 | 自动驾驶论文 |
| TAGFN: Fake News Detection | Other | 7.0 | 假新闻检测，与MGX无关 |

**高价值候选（应被保留）**：

| 标题 | 领域 | 相关性 | 价值 |
|------|------|--------|------|
| Large Language Models for Unit Test Generation | Coding | 9.0 | 代码测试生成 |
| Lightweight Model Editing for LLMs to Correct Deprecated API | Coding | 9.0 | API修复 |
| Tool-RoCo: Multi-robot Cooperation | Collaboration | 8.0 | 多Agent协作 |

### 1.3 根因分析

#### 根因1: 预筛选规则对arXiv过于宽松

**当前代码** (`src/prefilter/rule_filter.py:16-17`):
```python
TRUSTED_SOURCES: set[str] = {"arxiv", "techempower", "dbengines", "helm"}
```

**问题**: arXiv被列为信任来源，豁免关键词检查，导致大量无关论文通过预筛选。

#### 根因2: 算法论文检测不够精确

**当前代码** (`src/prefilter/rule_filter.py:43-54`):
```python
def _looks_like_algo_paper(candidate: RawCandidate) -> bool:
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()
    has_algo_phrase = _contains_any(text, constants.ALGO_METHOD_PHRASES)
    has_benchmark_signal = _contains_any(text, constants.BENCHMARK_DATASET_KEYWORDS)
    return has_algo_phrase and not has_benchmark_signal
```

**问题**:
- 只检测`ALGO_METHOD_PHRASES`，不覆盖"Technical Report"类型
- 如果摘要包含"benchmark"（如"我们在XXX benchmark上测试"），就不会被过滤
- 无法区分"方法论论文"和"Benchmark论文"

#### 根因3: LLM评分对Other领域评分过高

**当前Prompt** (`src/scorer/llm_scorer.py:92-96`):
```
【Other - 低相关】（relevance_score建议 ≤3分）
10. 纯NLP/视觉/语音任务（无Agent或代码关联）
11. 理论研究（无实际工程应用）
12. 与MGX场景完全无关的领域
```

**问题**: Prompt说"建议≤3分"，但LLM实际给了6.0。需要强制约束而非建议。

#### 根因4: 新颖度评分标准执行不严格

**当前评分标准**:
- 10分: 2024+发布, 全新任务/指标, 补位MGX空白场景
- 8-9分: 2023-2024发布, 创新任务或指标, 与MGX高度相关

**问题**: 所有候选新颖度都是8.0+，说明LLM对"创新任务"判断过于宽松。

#### 根因5: 推送过滤对Other领域门槛过低

**当前代码** (`src/common/constants.py:642`):
```python
PUSH_RELEVANCE_FLOOR: Final[float] = 5.5  # 任务相关性下限
```

**问题**: Other领域候选相关性6.0就能通过推送过滤，应该提高门槛。

---

## 二、解决方案设计

### 2.1 方案概览

采用**四层防御机制**：

| 层级 | 位置 | 防御目标 | 预期过滤率 |
|------|------|----------|-----------|
| L1 | 预筛选 | 标题级快速过滤（Technical Report等） | +10% |
| L2 | 预筛选 | 非Benchmark论文精确检测 | +15% |
| L3 | LLM评分 | Other领域相关性强制约束 | +20% |
| L4 | 推送过滤 | Other领域占比限制 | +5% |

### 2.2 详细设计

#### Layer 1: 标题级快速过滤

**新增规则**: 标题包含以下模式但不包含Benchmark信号的论文，直接过滤

```python
TECHNICAL_REPORT_PATTERNS = [
    "technical report",
    "progress report",
    "status report",
    "white paper",
    "position paper",
    "survey of",
    "review of",
    "overview of",
]

BENCHMARK_TITLE_SIGNALS = [
    "benchmark",
    "dataset",
    "leaderboard",
    "evaluation suite",
    "test set",
    "challenge",
]
```

**逻辑**:
```
IF title contains TECHNICAL_REPORT_PATTERNS
   AND title NOT contains BENCHMARK_TITLE_SIGNALS
THEN filter_out
```

#### Layer 2: 非Benchmark论文精确检测

**增强`_looks_like_algo_paper`函数**:

1. 新增"模型发布论文"检测：
   - 标题包含模型名（如"Qwen", "Llama", "GPT"）+ "Technical Report"
   - 摘要侧重模型能力描述而非评测

2. 新增"应用论文"检测：
   - 标题包含特定应用领域（如"autonomous driving", "fake news", "sarcasm"）
   - 与MGX核心场景无关

3. 增强"方法论论文"检测短语：
```python
ALGO_METHOD_PHRASES_EXTENDED = [
    # 现有短语...
    "a new model",
    "a novel model",
    "our model",
    "a new architecture",
    "a novel architecture",
    "a new technique",
    "a novel technique",
    "a new algorithm",
    "a novel algorithm",
    "we developed",
    "we built",
    "we trained",
]
```

#### Layer 3: LLM评分Prompt优化

**修改位置**: `src/scorer/llm_scorer.py` UNIFIED_SCORING_PROMPT_TEMPLATE

**修改内容**:

1. **强化Other领域评分规则**（将"建议"改为"必须"）:

```
【Other - 低相关】（relevance_score **必须** ≤4分，违反将视为评分失败）
10. 纯NLP/视觉/语音任务（无Agent或代码关联）→ 必须≤3分
11. 理论研究（无实际工程应用）→ 必须≤3分
12. 与MGX场景完全无关的领域 → 必须≤2分
13. 技术报告/模型发布论文（如"XX Technical Report"）→ 必须≤4分
14. 应用领域论文（自动驾驶、医疗、金融等）→ 必须≤4分

**重要约束**：
- 如果任务领域判定为Other，则relevance_score必须≤4分
- 如果论文标题包含"Technical Report"，则relevance_score必须≤4分
- 违反此规则的评分将被系统拒绝并重新评分
```

2. **收紧新颖度评分标准**:

```
【维度4: 新颖性 novelty_score】
评分标准（**严格执行**）：
- 10分: 2024+发布, 全新任务类型（MGX从未评测过）, 填补空白
- 8-9分: 2024+发布, 在现有任务上有显著创新（新指标/新数据/新场景）
- 6-7分: 2023-2024发布, 对现有任务有小幅改进
- 4-5分: 2022-2023发布, 成熟任务的变种
- 2-3分: 常规任务/常规数据集/常规指标
- 0-1分: 完全过时或无创新

**重要约束**：
- 单纯的"更大规模"不算创新，novelty_score≤6
- 单纯的"更多领域"不算创新，novelty_score≤6
- 技术报告/模型发布论文（非Benchmark）novelty_score≤5
- 只有真正引入新评测范式/新任务类型才能给8分以上
```

3. **新增任务领域识别规则**:

```
【task_domain识别硬性规则】

以下情况必须标记为Other：
- 标题包含"Technical Report"且无Benchmark相关词
- 标题包含应用领域词（autonomous driving, fake news, sarcasm detection等）
- 摘要侧重模型能力/性能描述而非评测方法
- 任务与代码生成/Agent协作/工具调用无关

以下情况优先标记为核心领域：
- Coding: 明确涉及代码生成/补全/调试/测试
- Backend: 明确涉及API/数据库/分布式系统性能
- GUI: 明确涉及UI自动化/桌面/移动端交互
- WebDev: 明确涉及Web开发/前后端
- ToolUse: 明确涉及工具调用/API集成
- Collaboration: 明确涉及多Agent协作
```

#### Layer 4: 推送过滤优化

**修改位置**: `src/notifier/feishu_notifier.py` 和 `src/common/constants.py`

**新增常量**:
```python
# Other领域推送限制
OTHER_DOMAIN_RELEVANCE_FLOOR: Final[float] = 7.0  # Other领域相关性门槛提高到7.0
OTHER_DOMAIN_MAX_RATIO: Final[float] = 0.20  # Other领域最多占20%
OTHER_DOMAIN_MAX_COUNT: Final[int] = 3  # Other领域最多3条
```

**修改推送过滤逻辑**:
```python
def _prefilter_for_push(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    # 现有逻辑...

    # 新增: Other领域特殊处理
    other_candidates = [c for c in filtered if (c.task_domain or "Other") == "Other"]
    non_other_candidates = [c for c in filtered if (c.task_domain or "Other") != "Other"]

    # Other领域相关性门槛更高
    other_qualified = [c for c in other_candidates if c.relevance_score >= OTHER_DOMAIN_RELEVANCE_FLOOR]

    # Other领域数量限制
    other_qualified = other_qualified[:OTHER_DOMAIN_MAX_COUNT]

    filtered = non_other_candidates + other_qualified

    # Other领域占比限制
    total_count = len(filtered)
    max_other = int(total_count * OTHER_DOMAIN_MAX_RATIO)
    other_count = len([c for c in filtered if (c.task_domain or "Other") == "Other"])
    if other_count > max_other:
        # 按相关性排序，保留top max_other
        other_in_filtered = [c for c in filtered if (c.task_domain or "Other") == "Other"]
        other_sorted = sorted(other_in_filtered, key=lambda c: -c.relevance_score)
        other_to_keep = set(id(c) for c in other_sorted[:max_other])
        filtered = [c for c in filtered if (c.task_domain or "Other") != "Other" or id(c) in other_to_keep]

    return filtered
```

---

## 三、实施步骤

### Step 1: 修改 `src/common/constants.py`

**新增常量**（在文件末尾添加）:

```python
# ============================================================
# Phase 10: 推送质量优化常量
# ============================================================

# 技术报告/方法论论文检测模式
TECHNICAL_REPORT_PATTERNS: Final[list[str]] = [
    "technical report",
    "progress report",
    "status report",
    "white paper",
    "position paper",
    "survey of",
    "review of",
    "overview of",
    "an introduction to",
]

# 应用领域关键词（非MGX相关）
NON_MGX_APPLICATION_KEYWORDS: Final[list[str]] = [
    "autonomous driving",
    "self-driving",
    "fake news",
    "sarcasm detection",
    "sentiment analysis",
    "emotion recognition",
    "medical imaging",
    "drug discovery",
    "climate prediction",
    "financial forecasting",
    "stock prediction",
    "recommendation system",
    "speech recognition",
    "speaker identification",
    "face recognition",
    "object detection",
    "image segmentation",
    "video understanding",
    "digital twin",
    "iot network",
    "smart city",
    "smart home",
]

# 模型发布论文关键词（非Benchmark）
MODEL_RELEASE_KEYWORDS: Final[list[str]] = [
    "qwen",
    "llama",
    "gpt-",
    "claude",
    "gemini",
    "palm",
    "falcon",
    "mistral",
    "mixtral",
    "phi-",
    "deepseek",
    "yi-",
    "baichuan",
    "chatglm",
    "internlm",
]

# 扩展的算法方法短语
ALGO_METHOD_PHRASES_EXTENDED: Final[list[str]] = [
    # 现有短语保留
    "we propose a",
    "we propose an",
    "we introduce a",
    "we present a",
    "we design a",
    "a novel approach",
    "a new approach",
    "a novel framework",
    "a new framework",
    "a novel method",
    "a new method",
    "our method",
    "our framework",
    "our approach",
    # 新增短语
    "a new model",
    "a novel model",
    "our model",
    "a new architecture",
    "a novel architecture",
    "a new technique",
    "a novel technique",
    "a new algorithm",
    "a novel algorithm",
    "we developed",
    "we built",
    "we trained",
    "we fine-tuned",
    "we adapted",
    "we extended",
    "a new strategy",
    "a novel strategy",
    "our strategy",
]

# Benchmark标题信号词（用于区分Benchmark论文 vs 方法论论文）
BENCHMARK_TITLE_SIGNALS: Final[list[str]] = [
    "benchmark",
    "benchmarking",
    "dataset",
    "leaderboard",
    "evaluation suite",
    "test set",
    "testset",
    "challenge",
    "competition",
    "evaluation framework",
    "assessment",
]

# Other领域推送限制
OTHER_DOMAIN_RELEVANCE_FLOOR: Final[float] = 7.0  # Other领域相关性门槛
OTHER_DOMAIN_MAX_RATIO: Final[float] = 0.20  # Other领域最多占20%
OTHER_DOMAIN_MAX_COUNT: Final[int] = 3  # Other领域最多3条
```

### Step 2: 修改 `src/prefilter/rule_filter.py`

#### 2.1 新增技术报告检测函数

在 `_looks_like_algo_paper` 函数后新增：

```python
def _looks_like_technical_report(candidate: RawCandidate) -> bool:
    """检测技术报告/模型发布论文（非Benchmark）

    规则：
    1. 标题包含"Technical Report"等模式
    2. 标题包含模型名（如Qwen/Llama）
    3. 且不包含Benchmark信号词
    """
    title_lower = (candidate.title or "").lower()

    # 检测技术报告模式
    has_tech_report_pattern = _contains_any(title_lower, constants.TECHNICAL_REPORT_PATTERNS)

    # 检测模型发布论文
    has_model_name = _contains_any(title_lower, constants.MODEL_RELEASE_KEYWORDS)

    # 检测Benchmark信号
    has_benchmark_signal = _contains_any(title_lower, constants.BENCHMARK_TITLE_SIGNALS)

    # 技术报告 + 无Benchmark信号 → 过滤
    if has_tech_report_pattern and not has_benchmark_signal:
        return True

    # 模型名 + Technical Report + 无Benchmark信号 → 过滤
    if has_model_name and "technical report" in title_lower and not has_benchmark_signal:
        return True

    return False


def _looks_like_non_mgx_application(candidate: RawCandidate) -> bool:
    """检测非MGX相关的应用领域论文

    规则：标题或摘要包含非MGX应用关键词，且不包含MGX核心场景关键词
    """
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    # 检测非MGX应用关键词
    has_non_mgx_app = _contains_any(text, constants.NON_MGX_APPLICATION_KEYWORDS)

    if not has_non_mgx_app:
        return False

    # 检测MGX核心场景关键词
    mgx_core_keywords = [
        "code generation", "code completion", "code review",
        "multi-agent", "agent collaboration", "tool use",
        "api call", "function call", "web automation",
        "gui automation", "browser automation",
        "software engineering", "programming",
    ]
    has_mgx_signal = _contains_any(text, mgx_core_keywords)

    # 非MGX应用 + 无MGX信号 → 过滤
    return not has_mgx_signal
```

#### 2.2 修改 `_prefilter_with_reason` 函数

在现有过滤规则后（约第173行后）新增：

```python
    # 技术报告/模型发布论文过滤（arXiv等论文源）
    if candidate.source == "arxiv" and _looks_like_technical_report(candidate):
        logger.debug("过滤: 技术报告/模型发布论文 - %s", candidate.title)
        return False, "tech_report"

    # 非MGX应用领域论文过滤（arXiv等论文源）
    if candidate.source == "arxiv" and _looks_like_non_mgx_application(candidate):
        logger.debug("过滤: 非MGX应用领域论文 - %s", candidate.title)
        return False, "non_mgx_app"
```

#### 2.3 更新 `_looks_like_algo_paper` 函数

使用扩展的短语列表：

```python
def _looks_like_algo_paper(candidate: RawCandidate) -> bool:
    """针对arXiv等论文源，识别算法/系统方法论（非Benchmark）。

    规则：文本命中算法方法短语，且不包含Benchmark/数据集正向关键词。
    保留"Benchmark方法论"——因为它会包含benchmark/dataset等正向信号。
    """
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    # 使用扩展的短语列表
    has_algo_phrase = _contains_any(text, constants.ALGO_METHOD_PHRASES_EXTENDED)
    has_benchmark_signal = _contains_any(text, constants.BENCHMARK_DATASET_KEYWORDS)
    return has_algo_phrase and not has_benchmark_signal
```

### Step 3: 修改 `src/scorer/llm_scorer.py`

#### 3.1 修改 `UNIFIED_SCORING_PROMPT_TEMPLATE`

**修改位置**: 第92-96行附近

**当前代码**:
```
【Other - 低相关】（relevance_score建议 ≤3分）
10. 纯NLP/视觉/语音任务（无Agent或代码关联）
11. 理论研究（无实际工程应用）
12. 与MGX场景完全无关的领域
```

**修改后**:
```
【Other - 低相关】（relevance_score **必须** ≤4分，这是硬性规则）
10. 纯NLP/视觉/语音任务（无Agent或代码关联）→ relevance_score必须≤3分
11. 理论研究（无实际工程应用）→ relevance_score必须≤3分
12. 与MGX场景完全无关的领域（自动驾驶/医疗/金融等）→ relevance_score必须≤2分
13. 技术报告/模型发布论文（如"XX Technical Report"）→ relevance_score必须≤4分
14. 假新闻检测/情感分析/推荐系统等应用论文 → relevance_score必须≤3分

**硬性约束（违反将被系统拒绝）**：
- 任务领域=Other时，relevance_score最高4分，超过4分将被系统自动降级
- 标题包含"Technical Report"的论文，relevance_score最高4分
- 与代码/Agent/工具/Web无关的应用论文，relevance_score最高3分
```

#### 3.2 修改新颖度评分标准

**修改位置**: 第148-162行附近

**当前代码**:
```
【维度4: 新颖性 novelty_score】
评分标准：
- 10分: 2024+发布, 全新任务/指标, 补位MGX空白场景
- 8-9分: 2023-2024发布, 创新任务或指标, 与MGX高度相关
...
```

**修改后**:
```
【维度4: 新颖性 novelty_score】
评分标准（**严格执行，不得随意打高分**）：
- 10分: 2024+发布 + 全新任务类型（MGX从未评测过的场景）+ 填补行业空白
- 8-9分: 2024+发布 + 在现有任务上有显著创新（新指标体系/新评测范式/新场景定义）
- 6-7分: 2023-2024发布 + 对现有任务有小幅改进（数据规模扩大/领域扩展）
- 4-5分: 2022-2023发布 + 成熟任务的标准变种
- 2-3分: 常规任务 + 常规数据集 + 常规指标
- 0-1分: 完全过时或无任何创新

**硬性约束**：
- "更大规模"不等于创新，novelty_score≤6
- "更多领域"不等于创新，novelty_score≤6
- 技术报告/模型发布论文（非Benchmark）novelty_score必须≤5
- 应用领域论文（非MGX相关）novelty_score必须≤5
- 只有真正引入新评测范式/新任务类型的Benchmark才能给8分以上
- **如果这个论文的主要贡献是"模型"而非"Benchmark"，novelty_score最高5分**
```

#### 3.3 新增任务领域识别硬性规则

**修改位置**: 第216-223行附近（task_domain说明后）

**新增内容**:
```
【task_domain识别硬性规则】

以下情况**必须**标记为Other（无例外）：
- 标题包含"Technical Report"且不包含"Benchmark/Dataset/Leaderboard"
- 标题包含应用领域词（autonomous driving, fake news, sarcasm, medical, financial）
- 论文主要贡献是"模型"而非"评测方法/数据集"
- 任务与代码生成/Agent协作/工具调用/Web开发完全无关

以下情况**必须**标记为核心领域（按优先级）：
- Coding: 明确涉及代码生成/补全/调试/测试/重构
- Backend: 明确涉及API设计/数据库/分布式系统/微服务
- WebDev: 明确涉及Web开发/前端/后端/全栈
- GUI: 明确涉及UI自动化/桌面应用/移动端交互
- ToolUse: 明确涉及工具调用/API集成/函数调用
- Collaboration: 明确涉及多Agent协作/任务分工

**验证规则**：
- 如果task_domain=Other但relevance_score>4，这是错误的，请修正
- 如果task_domain∈{Coding,Backend,WebDev,GUI}但relevance_score<6，请检查分类是否正确
```

### Step 4: 修改 `src/notifier/feishu_notifier.py`

#### 4.1 修改 `_prefilter_for_push` 函数

**修改位置**: 约第215-289行

**在函数末尾、排序和总量限制之前，新增Other领域过滤逻辑**:

```python
    def _prefilter_for_push(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
        """推送前过滤..."""

        # ... 现有过滤逻辑保持不变 ...

        # === Phase 10新增: Other领域特殊处理 ===
        other_candidates = [c for c in filtered if (c.task_domain or "Other") == "Other"]
        non_other_candidates = [c for c in filtered if (c.task_domain or "Other") != "Other"]

        # Other领域相关性门槛更高
        other_qualified = [
            c for c in other_candidates
            if c.relevance_score >= constants.OTHER_DOMAIN_RELEVANCE_FLOOR
        ]

        # Other领域数量限制
        other_qualified = sorted(other_qualified, key=lambda c: -c.relevance_score)
        other_qualified = other_qualified[:constants.OTHER_DOMAIN_MAX_COUNT]

        # 合并结果
        filtered = non_other_candidates + other_qualified

        logger.info(
            "Other领域过滤: 原%d条 → 保留%d条 (门槛%.1f, 上限%d)",
            len(other_candidates),
            len(other_qualified),
            constants.OTHER_DOMAIN_RELEVANCE_FLOOR,
            constants.OTHER_DOMAIN_MAX_COUNT,
        )
        # === Phase 10新增结束 ===

        # 按新鲜度优先，其次分数
        def sort_key(c: ScoredCandidate) -> tuple[int, float]:
            age = self._age_days(c)
            return (age, -c.total_score)

        filtered = sorted(filtered, key=sort_key)

        # Other领域占比限制（二次检查）
        total_count = len(filtered)
        if total_count > 0:
            max_other = max(1, int(total_count * constants.OTHER_DOMAIN_MAX_RATIO))
            current_other = [c for c in filtered if (c.task_domain or "Other") == "Other"]
            if len(current_other) > max_other:
                other_to_remove = len(current_other) - max_other
                # 移除相关性最低的Other候选
                other_sorted = sorted(current_other, key=lambda c: c.relevance_score)
                remove_set = set(id(c) for c in other_sorted[:other_to_remove])
                filtered = [c for c in filtered if id(c) not in remove_set]
                logger.info("Other领域占比限制: 移除%d条低相关性Other候选", other_to_remove)

        # 总量上限
        if len(filtered) > constants.PUSH_TOTAL_CAP:
            filtered = filtered[: constants.PUSH_TOTAL_CAP]

        return filtered
```

---

## 四、测试验证计划

### 4.1 单元测试

**测试文件**: `tests/test_phase10_quality.py`

```python
"""Phase 10 推送质量优化测试"""

import pytest
from src.prefilter.rule_filter import (
    _looks_like_technical_report,
    _looks_like_non_mgx_application,
    _looks_like_algo_paper,
)
from src.models import RawCandidate


class TestTechnicalReportDetection:
    """技术报告检测测试"""

    def test_qwen3_vl_technical_report(self):
        """Qwen3-VL Technical Report应被过滤"""
        candidate = RawCandidate(
            title="Qwen3-VL Technical Report",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We present Qwen3-VL, a multimodal language model...",
        )
        assert _looks_like_technical_report(candidate) is True

    def test_benchmark_paper_not_filtered(self):
        """Benchmark论文不应被过滤"""
        candidate = RawCandidate(
            title="SWE-bench: A Benchmark for Software Engineering",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We introduce SWE-bench, a benchmark dataset for...",
        )
        assert _looks_like_technical_report(candidate) is False


class TestNonMgxApplicationDetection:
    """非MGX应用检测测试"""

    def test_autonomous_driving_filtered(self):
        """自动驾驶论文应被过滤"""
        candidate = RawCandidate(
            title="Model-Based Policy Adaptation for Autonomous Driving",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We propose a new approach for autonomous driving...",
        )
        assert _looks_like_non_mgx_application(candidate) is True

    def test_code_generation_not_filtered(self):
        """代码生成论文不应被过滤"""
        candidate = RawCandidate(
            title="CodeGen: An Open Large Language Model for Code",
            url="https://arxiv.org/abs/xxx",
            source="arxiv",
            abstract="We present CodeGen, a code generation model...",
        )
        assert _looks_like_non_mgx_application(candidate) is False


class TestOtherDomainFiltering:
    """Other领域过滤测试"""

    def test_other_domain_high_threshold(self):
        """Other领域相关性门槛应为7.0"""
        from src.common import constants
        assert constants.OTHER_DOMAIN_RELEVANCE_FLOOR == 7.0

    def test_other_domain_max_ratio(self):
        """Other领域占比上限应为20%"""
        from src.common import constants
        assert constants.OTHER_DOMAIN_MAX_RATIO == 0.20
```

### 4.2 集成测试

```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志中的过滤统计
grep "过滤:" logs/$(ls -t logs/ | head -n1)

# 检查Other领域过滤
grep "Other领域" logs/$(ls -t logs/ | head -n1)
```

### 4.3 验收标准

| 指标 | 优化前 | 期望值 | 验收通过 |
|------|--------|--------|---------|
| Other领域占比 | 46% | ≤20% | Other条数/总条数 ≤ 0.20 |
| 核心领域占比 | 20% | ≥50% | (Coding+Backend+WebDev+GUI)/总条数 ≥ 0.50 |
| 相关性=6.0占比 | 60% | ≤30% | 相关性6.0条数/总条数 ≤ 0.30 |
| Technical Report过滤 | 0条 | 全部过滤 | 标题含"Technical Report"的候选数=0 |

---

## 五、成功标准检查清单

### 5.1 代码修改检查

- [ ] `src/common/constants.py` 新增所有常量
- [ ] `src/prefilter/rule_filter.py` 新增 `_looks_like_technical_report` 函数
- [ ] `src/prefilter/rule_filter.py` 新增 `_looks_like_non_mgx_application` 函数
- [ ] `src/prefilter/rule_filter.py` 修改 `_looks_like_algo_paper` 使用扩展短语
- [ ] `src/prefilter/rule_filter.py` 修改 `_prefilter_with_reason` 新增过滤规则
- [ ] `src/scorer/llm_scorer.py` 修改 Other领域评分规则（必须≤4分）
- [ ] `src/scorer/llm_scorer.py` 修改 新颖度评分规则（收紧标准）
- [ ] `src/scorer/llm_scorer.py` 新增 任务领域识别硬性规则
- [ ] `src/notifier/feishu_notifier.py` 修改 `_prefilter_for_push` 新增Other领域过滤

### 5.2 测试通过检查

- [ ] 单元测试全部通过: `pytest tests/test_phase10_quality.py`
- [ ] 集成测试通过: `.venv/bin/python -m src.main`
- [ ] 日志显示Technical Report被过滤
- [ ] 日志显示非MGX应用论文被过滤
- [ ] 推送中Other领域≤20%

### 5.3 推送质量检查

- [ ] Qwen3-VL Technical Report 类似候选被过滤
- [ ] 自动驾驶/假新闻/情感分析类候选被过滤
- [ ] 核心领域（Coding/Backend/WebDev/GUI）候选保留
- [ ] 平均相关性提升（目标≥7.0）
- [ ] Other领域候选相关性≥7.0

---

## 六、风险与回滚

### 6.1 潜在风险

1. **过度过滤风险**: 可能误过滤少量边缘Benchmark
   - 缓解: 保留日志记录，监控过滤率变化

2. **LLM不遵守Prompt约束风险**: LLM可能仍给Other高分
   - 缓解: 推送层二次过滤，强制Other≤4条

3. **核心领域召回下降风险**: 收紧规则可能影响核心领域召回
   - 缓解: 核心领域保持原有规则，仅收紧Other

### 6.2 回滚方案

如果优化后出现问题，可以通过以下步骤回滚：

```bash
# 恢复constants.py
git checkout HEAD~1 -- src/common/constants.py

# 恢复rule_filter.py
git checkout HEAD~1 -- src/prefilter/rule_filter.py

# 恢复llm_scorer.py
git checkout HEAD~1 -- src/scorer/llm_scorer.py

# 恢复feishu_notifier.py
git checkout HEAD~1 -- src/notifier/feishu_notifier.py
```

---

## 七、附录：今日推送样例对比

### 7.1 应过滤候选（优化后不应出现）

```
# 这些候选在优化后应被过滤

1. Qwen3-VL Technical Report
   - 过滤原因: _looks_like_technical_report → True
   - 规则: 标题含模型名+Technical Report

2. Digital Twin-Driven Secure Access Strategy for SAGIN-Enabled IoT Networks
   - 过滤原因: _looks_like_non_mgx_application → True
   - 规则: 标题含"digital twin"、"iot network"

3. Context-Aware Pragmatic Metacognitive Prompting for Sarcasm Detection
   - 过滤原因: _looks_like_non_mgx_application → True
   - 规则: 标题含"sarcasm detection"

4. Model-Based Policy Adaptation for Closed-Loop End-to-End Autonomous Driving
   - 过滤原因: _looks_like_non_mgx_application → True
   - 规则: 标题含"autonomous driving"

5. TAGFN: A Text-Attributed Graph Dataset for Fake News Detection
   - 过滤原因: _looks_like_non_mgx_application → True
   - 规则: 标题含"fake news"
```

### 7.2 应保留候选（优化后继续推送）

```
# 这些候选在优化后应保留

1. Large Language Models for Unit Test Generation
   - task_domain: Coding
   - relevance_score: 9.0
   - 保留原因: 核心领域+高相关性

2. Lightweight Model Editing for LLMs to Correct Deprecated API Recommendations
   - task_domain: Coding
   - relevance_score: 9.0
   - 保留原因: 核心领域+高相关性

3. Tool-RoCo: Multi-robot Cooperation
   - task_domain: Collaboration
   - relevance_score: 8.0
   - 保留原因: P1高价值场景
```

---

**文档结束**

Codex请严格按照上述步骤实施，实施完成后运行完整流程验证效果。
