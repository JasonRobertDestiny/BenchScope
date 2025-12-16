# CODEX开发指令：P10推送质量优化

## 问题诊断

**今日推送：4条候选，0条真正Benchmark (100%误判率)**

| 候选项 | 分数 | 实际类型 |
|--------|------|---------|
| stepfun-ai/gelab-zero | 8.2 | GUI Agent框架 |
| lukasmolnar/wb-mpc-locoman | 8.8 | 机器人控制代码 |
| zechenzhangAGI/AI-research-SKILLs | 8.4 | 技能清单文档 |
| Vyntral/god-eye | 6.2 | 工具项目 |

**根本原因**：
1. 权威来源（arXiv等）完全豁免关键词检查 → 任何带"benchmark"的论文直接入库
2. Benchmark特征检测仅在GitHub上应用 → 其他来源无法区分真假Benchmark
3. relevance权重太低(25%) → 低相关性候选也能高分入库
4. 推送相关性门槛太低(5.5) → P2场景也推送

---

## Step 1: 修改constants.py

### 1.1 新增常量（在L525之后添加）

```python
# 在 SCORE_WEIGHTS 定义之后添加

# Benchmark正向信号词（权威来源检测用）
BENCHMARK_POSITIVE_SIGNALS: Final[list[str]] = [
    "benchmark",
    "benchmarking",
    "evaluation benchmark",
    "test set",
    "testset",
    "dataset",
    "leaderboard",
    "evaluation suite",
    "corpus",
    "test data",
    "evaluation data",
    "ground truth",
    "challenge",
    "competition",
    "shared task",
]

# 相关性硬下限（低于此分数不入库）
RELEVANCE_HARD_FLOOR: Final[float] = 6.0
```

### 1.2 修改PREFILTER_MIN_GITHUB_STARS（L305）

**当前代码**：
```python
PREFILTER_MIN_GITHUB_STARS: Final[int] = 10
```

**修改为**：
```python
PREFILTER_MIN_GITHUB_STARS: Final[int] = 30  # 从10提高到30，过滤低质量仓库
```

### 1.3 修改SCORE_WEIGHTS（L519-525）

**当前代码**：
```python
SCORE_WEIGHTS: Final[dict[str, float]] = {
    "activity": 0.15,  # 降低：GitHub stars容易虚高
    "reproducibility": 0.30,  # 保持：可复现性是核心
    "license": 0.15,  # 降低：不是核心指标
    "novelty": 0.15,  # 提高：Benchmark需要创新
    "relevance": 0.25,  # 提高：MGX适配度是关键
}
```

**修改为**：
```python
SCORE_WEIGHTS: Final[dict[str, float]] = {
    "activity": 0.10,        # 降低 (0.15→0.10)
    "reproducibility": 0.25, # 降低 (0.30→0.25)
    "license": 0.10,         # 降低 (0.15→0.10)
    "novelty": 0.15,         # 保持
    "relevance": 0.40,       # 提高 (0.25→0.40) - MGX适配度是关键
}
```

### 1.4 修改PUSH_RELEVANCE_FLOOR（L643）

**当前代码**：
```python
PUSH_RELEVANCE_FLOOR: Final[float] = 5.5  # 任务相关性下限，低于则不推
```

**修改为**：
```python
PUSH_RELEVANCE_FLOOR: Final[float] = 6.5  # 任务相关性下限，从5.5提高到6.5
```

---

## Step 2: 修改rule_filter.py

### 2.1 新增函数：_has_benchmark_positive_signal（在_contains_any之后添加，约L25）

```python
def _has_benchmark_positive_signal(candidate: RawCandidate) -> bool:
    """检查是否包含Benchmark正向信号词"""
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()
    return _contains_any(text, constants.BENCHMARK_POSITIVE_SIGNALS)
```

### 2.2 新增函数：_has_benchmark_characteristics（在_has_benchmark_positive_signal之后添加）

```python
def _has_benchmark_characteristics(candidate: RawCandidate) -> bool:
    """检测是否具备真实Benchmark特征（适用于所有来源）

    排除规则：
    - 框架/系统描述 + 无强Benchmark信号 → 过滤
    - 资源列表/教程/课程 + 无强Benchmark信号 → 过滤
    """
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    # 排除模式（非Benchmark特征）
    exclude_patterns = [
        # 框架/系统描述
        "framework for",
        "we propose a",
        "we implement",
        "we develop",
        "a novel system",
        "agent framework",
        "gui agent",
        # 资源列表
        "awesome",
        "curated list",
        "collection of",
        "list of tools",
        "list of resources",
        # 教程/课程
        "tutorial",
        "course",
        "learning path",
        "how to",
        # 无关领域
        "robot",
        "robotics",
        "autonomous vehicle",
        "medical",
        "healthcare",
    ]

    has_exclude_pattern = any(p in text for p in exclude_patterns)

    if has_exclude_pattern:
        # 有排除模式时，必须有强Benchmark信号才通过
        strong_signals = ["benchmark", "evaluation", "leaderboard", "test set", "dataset"]
        if not any(s in text for s in strong_signals):
            logger.debug("排除: 有排除模式但无强Benchmark信号 - %s", candidate.title[:50])
            return False

    # 正向特征检查
    return _has_benchmark_positive_signal(candidate)
```

### 2.3 修改_passes_keyword_rules函数（L320-341）

**当前代码**：
```python
def _passes_keyword_rules(candidate: RawCandidate) -> bool:
    """基于Phase7白/黑名单的关键词过滤（权威来源豁免）"""

    if candidate.source in TRUSTED_SOURCES:
        logger.debug(
            "权威来源豁免关键词检查: %s (%s)",
            candidate.title[: constants.TITLE_TRUNCATE_SHORT],
            candidate.source,
        )
        return True

    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    if any(excluded in text for excluded in constants.PREFILTER_EXCLUDED_KEYWORDS):
        logger.debug("过滤: 命中排除关键词 - %s", candidate.title)
        return False

    if not any(required in text for required in constants.PREFILTER_REQUIRED_KEYWORDS):
        logger.debug("过滤: 未命中必需关键词 - %s", candidate.title)
        return False

    return True
```

**修改为**：
```python
def _passes_keyword_rules(candidate: RawCandidate) -> bool:
    """基于Phase7白/黑名单的关键词过滤

    P10优化: 权威来源不再完全豁免，仍需通过Benchmark正向特征检查
    """

    if candidate.source in TRUSTED_SOURCES:
        # P10: 权威来源仅豁免排除词检查，仍需通过正向特征检查
        if _has_benchmark_positive_signal(candidate):
            logger.debug(
                "权威来源通过正向特征检查: %s (%s)",
                candidate.title[: constants.TITLE_TRUNCATE_SHORT],
                candidate.source,
            )
            return True
        else:
            logger.debug(
                "权威来源未通过正向特征检查: %s (%s)",
                candidate.title[: constants.TITLE_TRUNCATE_SHORT],
                candidate.source,
            )
            return False

    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    if any(excluded in text for excluded in constants.PREFILTER_EXCLUDED_KEYWORDS):
        logger.debug("过滤: 命中排除关键词 - %s", candidate.title)
        return False

    if not any(required in text for required in constants.PREFILTER_REQUIRED_KEYWORDS):
        logger.debug("过滤: 未命中必需关键词 - %s", candidate.title)
        return False

    return True
```

### 2.4 修改_prefilter_with_reason函数（在L211之后添加Benchmark特征检测）

**在L211-212之间插入以下代码**（在`_passes_keyword_rules`检查之后）：

```python
    if not _passes_keyword_rules(candidate):
        return False, "keyword_rule"

    # P10新增: 所有来源统一执行Benchmark特征检测（GitHub除外，已有更严格检测）
    if candidate.source != "github" and not _has_benchmark_characteristics(candidate):
        logger.debug("过滤: 缺少Benchmark特征 - %s (%s)", candidate.title, candidate.source)
        return False, "no_benchmark_feature"

    if candidate.source == "github" and not _is_quality_github_repo(candidate):
```

---

## Step 3: 修改main.py

### 3.1 新增相关性硬下限过滤函数（在_apply_freshness_boost之后添加）

```python
def _filter_by_relevance_floor(candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """P10: 过滤相关性低于硬下限的候选

    相关性硬下限 = 6.0，低于此分数的候选不入库
    """
    filtered = []
    dropped = 0
    for c in candidates:
        if c.relevance_score >= constants.RELEVANCE_HARD_FLOOR:
            filtered.append(c)
        else:
            dropped += 1
            logger.debug(
                "相关性硬下限过滤: %s (relevance=%.1f < %.1f)",
                c.title[:50],
                c.relevance_score,
                constants.RELEVANCE_HARD_FLOOR,
            )

    if dropped > 0:
        logger.info("相关性硬下限过滤: 移除%d条 (relevance < %.1f)", dropped, constants.RELEVANCE_HARD_FLOOR)

    return filtered
```

### 3.2 在main函数中添加Step 4.7（在Step 4.6之后，Step 5之前）

**当前代码**（L281-286）：
```python
    # Step 4.6: 时间新鲜度加权（最新优先，兼顾任务相关性）
    logger.info("[4.6/7] 新鲜度加权...")
    scored = [_apply_freshness_boost(c) for c in scored]

    # Step 5: 图片上传已禁用以节省时间
    logger.info("[5/7] 图片上传已跳过，减少耗时")
```

**修改为**：
```python
    # Step 4.6: 时间新鲜度加权（最新优先，兼顾任务相关性）
    logger.info("[4.6/8] 新鲜度加权...")
    scored = [_apply_freshness_boost(c) for c in scored]

    # Step 4.7: 相关性硬下限过滤（P10新增）
    logger.info("[4.7/8] 相关性硬下限过滤...")
    scored = _filter_by_relevance_floor(scored)
    logger.info("相关性过滤后: %d条\n", len(scored))

    # Step 5: 图片上传已禁用以节省时间
    logger.info("[5/8] 图片上传已跳过，减少耗时")
```

### 3.3 更新后续Step编号

将所有后续的 `[X/7]` 改为 `[X/8]`：
- `[5/7]` → `[5/8]`
- `[6/7]` → `[6/8]`
- `[7/7]` → `[7/8]`

### 3.4 添加constants导入（如果尚未导入）

确保main.py顶部有：
```python
from src.common import constants
```

---

## Step 4: 测试验证

### 4.1 运行完整流程

```bash
.venv/bin/python -m src.main
```

### 4.2 验证清单

| 检查项 | 预期结果 |
|--------|---------|
| 预筛选过滤率 | 30-50% (之前~0%) |
| 平均评分 | 6.0-7.5 (之前8.6) |
| 飞书推送内容 | 都是真实Benchmark |
| 日志显示 | "权威来源未通过正向特征检查" |
| 日志显示 | "相关性硬下限过滤: 移除X条" |

### 4.3 手动验证飞书推送

1. 检查推送的每条候选是否是真实Benchmark
2. 检查评分依据是否合理
3. 截图保存验证结果

---

## 验收标准

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 真实Benchmark占比 | 0% | ≥60% |
| 预筛选过滤率 | ~0% | 30-50% |
| 平均评分 | 8.6 | 6.0-7.5 |

---

## 文件修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `src/common/constants.py` | 修改+新增 | SCORE_WEIGHTS、PREFILTER_MIN_GITHUB_STARS、PUSH_RELEVANCE_FLOOR、新增BENCHMARK_POSITIVE_SIGNALS和RELEVANCE_HARD_FLOOR |
| `src/prefilter/rule_filter.py` | 修改+新增 | _passes_keyword_rules修改、新增_has_benchmark_positive_signal和_has_benchmark_characteristics、_prefilter_with_reason添加特征检测 |
| `src/main.py` | 修改+新增 | 新增_filter_by_relevance_floor函数、添加Step 4.7、更新Step编号 |

---

# P10.5追加优化：2025-12-03

## 新增问题

### 问题1：飞书表格没更新
**现象**：用户收到飞书推送通知，但打开表格发现没有新数据

**根因分析**：
1. 飞书API返回429限流错误
2. 当前重试配置：3次重试，每次间隔1.5秒，总共4.5秒
3. 4.5秒内飞书API仍未恢复，降级到SQLite
4. 通知系统独立于存储，Webhook推送成功
5. 结果：用户收到通知，但表格没有数据

**关键日志证据**（2025-11-26）：
```
13:15:43,819 [WARNING] ⚠️ 飞书存储失败,降级到SQLite: 429 Too Many Requests
13:15:44,311 [INFO] ✅ SQLite备份成功: 216条
13:15:45,820 [INFO] ✅ 飞书卡片推送成功  ← 通知仍然推送了！
```

### 问题2：工具库仍被误判
**现象**：splintr分词器、AI-research-SKILLs被推送为Benchmark候选

**根因分析**：
1. `TOOL_LIKE_KEYWORDS`缺少常见工具词："library"、"tokenizer"、"package"
2. `_looks_like_tool_repo`逻辑错误：必须命中"SDK"/"framework"才被识别为工具
3. GitHub搜索太宽松，任何README提到"benchmark"都会被采集

---

## Step 5: 增强飞书API重试逻辑

### 5.1 修改constants.py

**找到飞书HTTP配置（约第553-555行）**：

**当前代码**：
```python
FEISHU_HTTP_TIMEOUT_SECONDS: Final[int] = 15
FEISHU_HTTP_MAX_RETRIES: Final[int] = 3
FEISHU_HTTP_RETRY_DELAY_SECONDS: Final[float] = 1.5
```

**修改为**：
```python
# ---- 飞书HTTP配置 ----
FEISHU_HTTP_TIMEOUT_SECONDS: Final[int] = 15
FEISHU_HTTP_MAX_RETRIES: Final[int] = 5  # 3→5次，增加重试机会
FEISHU_HTTP_RETRY_DELAY_SECONDS: Final[float] = 2.0  # 1.5→2秒，初始延迟更长
FEISHU_HTTP_MAX_RETRY_DELAY_SECONDS: Final[float] = 30.0  # 新增：最大延迟上限
FEISHU_HTTP_429_EXTRA_DELAY_SECONDS: Final[float] = 10.0  # 新增：429错误额外等待
```

### 5.2 修改feishu_storage.py的_request_with_retry方法

**文件路径**：`src/storage/feishu_storage.py`

**当前代码**（第70-108行）：
```python
async def _request_with_retry(
    self,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """对飞书API请求增加重试，防止偶发超时导致流程中断"""

    timeout = kwargs.pop(
        "timeout",
        constants.FEISHU_HTTP_TIMEOUT_SECONDS,
    )
    delay = constants.FEISHU_HTTP_RETRY_DELAY_SECONDS
    last_error: Optional[Exception] = None

    for attempt in range(1, constants.FEISHU_HTTP_MAX_RETRIES + 1):
        try:
            return await client.request(
                method,
                url,
                timeout=timeout,
                **kwargs,
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_error = exc
            logger.debug(
                "飞书请求失败(%s %s)第%d次: %s",
                method,
                url,
                attempt,
                exc,
            )
            if attempt >= constants.FEISHU_HTTP_MAX_RETRIES:
                break
            await asyncio.sleep(delay)
            delay *= 1.8

    raise FeishuAPIError("飞书请求重试仍失败") from last_error
```

**修改为**：
```python
async def _request_with_retry(
    self,
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """对飞书API请求增加重试，针对429限流使用更长的指数退避

    重试策略：
    - 网络错误/超时：标准指数退避（2s→4s→8s...）
    - 429限流错误：额外等待10s + 指数退避，最长30s
    - 最多重试5次，总等待时间可达90秒
    """

    timeout = kwargs.pop(
        "timeout",
        constants.FEISHU_HTTP_TIMEOUT_SECONDS,
    )
    delay = constants.FEISHU_HTTP_RETRY_DELAY_SECONDS
    max_delay = constants.FEISHU_HTTP_MAX_RETRY_DELAY_SECONDS
    last_error: Optional[Exception] = None

    for attempt in range(1, constants.FEISHU_HTTP_MAX_RETRIES + 1):
        try:
            resp = await client.request(
                method,
                url,
                timeout=timeout,
                **kwargs,
            )

            # 针对429限流错误特殊处理：不立即抛出，而是等待更长时间重试
            if resp.status_code == 429:
                if attempt >= constants.FEISHU_HTTP_MAX_RETRIES:
                    # 最后一次重试仍然429，抛出异常
                    resp.raise_for_status()

                # 429错误使用更长的退避时间
                wait_time = min(
                    delay + constants.FEISHU_HTTP_429_EXTRA_DELAY_SECONDS,
                    max_delay,
                )
                logger.warning(
                    "飞书API限流(429)，等待%.1f秒后重试(%d/%d)",
                    wait_time,
                    attempt,
                    constants.FEISHU_HTTP_MAX_RETRIES,
                )
                await asyncio.sleep(wait_time)
                delay = min(delay * 2, max_delay)  # 指数退避，但不超过上限
                continue

            # 其他HTTP错误直接抛出
            resp.raise_for_status()
            return resp

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            # 网络错误的重试逻辑保持不变
            last_error = exc
            logger.debug(
                "飞书请求失败(%s %s)第%d次: %s",
                method,
                url,
                attempt,
                exc,
            )
            if attempt >= constants.FEISHU_HTTP_MAX_RETRIES:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)

    raise FeishuAPIError("飞书请求重试仍失败") from last_error
```

---

## Step 6: 扩展工具库检测关键词

### 6.1 扩展TOOL_LIKE_KEYWORDS

**文件路径**：`src/common/constants.py`

找到`TOOL_LIKE_KEYWORDS`定义（约第438-455行），修改为：

```python
# ---- 工具/框架识别关键词（用于预筛选排除非Benchmark） ----
TOOL_LIKE_KEYWORDS: Final[list[str]] = [
    # 现有关键词保持不变
    "sdk", "framework", "toolkit", "protocol", "api server",
    "cli tool", "plugin", "extension", "middleware", "os",
    "operating system", "service", "platform", "agent framework",
    "model context protocol", "mcp",
    # 新增：通用工具词
    "library", "package", "utility", "helper", "module",
    # 新增：文本处理类
    "tokenizer", "splitter", "parser", "converter", "processor",
    # 新增：API/网络类
    "client", "wrapper", "binding", "connector", "adapter",
    # 新增：数据处理类
    "loader", "extractor", "transformer", "serializer",
    # 新增：开发工具类
    "generator", "builder", "compiler", "linter", "formatter",
]

# 新增：工具库否定模式（README中常见的工具自述语句）
TOOL_NEGATIVE_PATTERNS: Final[list[str]] = [
    "this is a library",
    "this is a tool",
    "this is a package",
    "a python library",
    "a python package",
    "a javascript library",
    "a node.js package",
    "utility for",
    "helper for",
    "client for",
    "wrapper for",
    "tokenizer for",
    "parser for",
    "binding for",
    "connector for",
]
```

---

## Step 7: 修复工具库检测逻辑

### 7.1 重构_looks_like_tool_repo函数

**文件路径**：`src/prefilter/rule_filter.py`

找到`_looks_like_tool_repo`函数（约第85-99行），完整替换为：

```python
def _looks_like_tool_repo(candidate: RawCandidate) -> bool:
    """改进版工具库检测（满足任一条件即视为工具）

    检测规则（OR逻辑）：
    1. 标题/摘要命中工具类关键词（TOOL_LIKE_KEYWORDS）
    2. 标题/摘要命中工具否定模式（TOOL_NEGATIVE_PATTERNS）
    3. 标题以工具后缀结尾（-lib, -client, -sdk等）

    例外：
    - 如果同时有强Benchmark信号（benchmark dataset, leaderboard），不视为工具
    """
    text = f"{candidate.title} {(candidate.abstract or '')}".lower()

    # 检查强Benchmark信号（优先级最高，不视为工具）
    # 这些信号明确表明是评测基准，不是工具库
    strong_benchmark_signals = [
        "benchmark dataset",
        "evaluation benchmark",
        "test set",
        "leaderboard",
        "benchmark suite",
        "evaluation suite",
    ]
    if _contains_any(text, strong_benchmark_signals):
        return False

    # 检查工具特征（OR逻辑，满足任一即视为工具）
    has_tool_keyword = _contains_any(text, constants.TOOL_LIKE_KEYWORDS)
    has_tool_pattern = _contains_any(text, constants.TOOL_NEGATIVE_PATTERNS)
    has_tool_suffix = _has_tool_suffix(candidate.title)

    return has_tool_keyword or has_tool_pattern or has_tool_suffix


def _has_tool_suffix(title: str) -> bool:
    """检查标题是否以工具类后缀结尾

    例如：openai-python, tiktoken-lib, my-tokenizer
    """
    tool_suffixes = [
        "-lib",
        "-library",
        "-client",
        "-sdk",
        "-wrapper",
        "-tool",
        "-utils",
        "-helper",
        "-connector",
        "-adapter",
        "-parser",
        "-tokenizer",
        "-splitter",
        "-py",  # Python包常见后缀
        "-js",  # JavaScript包常见后缀
    ]
    # 统一格式：空格转为连字符，便于匹配后缀
    title_lower = title.lower().replace(" ", "-").replace("_", "-")
    return any(title_lower.endswith(suffix) for suffix in tool_suffixes)
```

### 7.2 确保导入constants模块

在文件顶部确认有以下导入：
```python
from src.common import constants
```

---

## Step 8: 优化LLM评分Prompt

### 8.1 在llm_scorer.py中添加工具识别规则

**文件路径**：`src/scorer/llm_scorer.py`

找到`UNIFIED_SCORING_PROMPT_TEMPLATE`变量，在"=== 第8部分：特殊情况处理 ==="之后，添加新的段落：

```python
# 在UNIFIED_SCORING_PROMPT_TEMPLATE中添加以下内容（找到"=== 第8部分"后添加）

"""
=== 第9部分：工具/库识别硬性规则 ===

【工具/库特征（满足任一条即为工具，不是Benchmark）】
- 标题包含工具后缀：-lib, -library, -client, -sdk, -wrapper, -tool, -utils, -parser, -tokenizer
- 摘要明确表述："this is a library/tool/package/utility for..."
- 主要功能是"提供API/接口/封装"而非"评测任务/数据集/排行榜"
- 没有评测指标（Pass@1, BLEU, Accuracy, F1-score等）
- 没有对比基线（GPT-4, Claude, Llama等模型对比）
- 没有数据集/测试用例集

【工具识别后的强制处理】
这是硬性规则，必须严格执行：
- novelty_score <= 3分（工具无Benchmark创新）
- relevance_score <= 3分（工具不是评测基准）
- task_domain = "Other"
- overall_reasoning第一句必须明确指出："该候选是[工具/库/框架]而非Benchmark，不推荐纳入MGX Benchmark池。"

【关键区分示例】
正确识别为Benchmark：
- "HumanEval: A benchmark for evaluating code generation" → 有评测任务、数据集
- "SWE-bench: A benchmark for software engineering agents" → 有排行榜、基线对比

正确识别为工具库：
- "tiktoken: A fast BPE tokenizer for use with OpenAI's models" → 工具，提供API
- "openai-python: The official Python library for the OpenAI API" → 库，API封装
- "splintr: A fast Python tokenizer with NLP benchmark support" → 虽然提到benchmark，但是分词工具

【易混淆情况处理】
如果README中提到"benchmark"但实际是性能对比，仍然是工具：
- "Our tokenizer benchmarks 3x faster than spaCy" → 这是性能对比，不是评测基准
- "Benchmark results show 10ms latency" → 这是性能测试，不是评测任务

只有当候选提供：评测任务定义 + 数据集/测试用例 + 评估指标 + 基线结果时，才是真正的Benchmark。
"""
```

---

## P10.5测试验证

### 验证Step 5（飞书API重试）
```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查429重试日志
grep -E "(429|限流|重试)" logs/benchscope.log

# 验证飞书表格是否有新数据
# 手动检查：https://deepwisdom.feishu.cn/base/SbIibGBIWayQncslz5kcYMnrnGf
```

### 验证Step 6-8（工具库过滤）
```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查是否有工具类项目被过滤的日志
grep -i "tokenizer\|library\|client\|工具" logs/benchscope.log

# 验证推送的都是真正的Benchmark
```

---

## P10.5检查清单

- [ ] Step 5: constants.py新增3个飞书重试配置常量
- [ ] Step 5: feishu_storage.py重构_request_with_retry方法，添加429特殊处理
- [ ] Step 6: constants.py扩展TOOL_LIKE_KEYWORDS（新增约20个词）
- [ ] Step 6: constants.py新增TOOL_NEGATIVE_PATTERNS
- [ ] Step 7: rule_filter.py重构_looks_like_tool_repo函数
- [ ] Step 7: rule_filter.py新增_has_tool_suffix辅助函数
- [ ] Step 8: llm_scorer.py在Prompt中添加"第9部分：工具/库识别硬性规则"
- [ ] 代码格式化：`black .`
- [ ] 代码检查：`ruff check .`
- [ ] 运行完整流程测试
