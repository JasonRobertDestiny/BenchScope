# CODEX紧急修复指令 - Phase 9 LLM推理长度不足问题

## 问题诊断

### 现象
运行`python -m src.main`时，LLM评分阶段全部失败，报Pydantic ValidationError：
```
activity_reasoning: String should have at least 150 characters [type=string_too_short, input_value='候选项目未提供Git...少的技术债务。', input_type=str]
```

### 根本原因分析

**数据统计（从日志提取）**：
- activity_reasoning: 平均120-140字符（要求150+）
- reproducibility_reasoning: 平均100-130字符（要求150+）
- license_reasoning: 平均80-120字符（要求150+）
- novelty_reasoning: 平均90-130字符（要求150+）
- relevance_reasoning: 平均100-140字符（要求150+）
- overall_reasoning: 平均30-45字符（要求50+）

**问题根源**：
1. Prompt说明"≥150字符"，但LLM（gpt-4o）经常忽略这个要求
2. JSON Schema中没有明确的字符计数示例
3. System message没有强调违反字符要求的后果
4. 缺少Self-Healing机制检测短文本并自动补充

**示例失败案例**：
```json
{
  "activity_reasoning": "该项目在GitHub上没有提供stars信息，也没有明确的GitHub URL，这表明项目可能是新项目或私有仓库，导致无法评估其社区活跃度。此外，缺乏更新和讨论的迹象，可能影响其在MGX中的应用。因此，活动评分较低，反映出其社区支持和开发活跃度的不足。"
}
```
上述文本只有140字符，差10个字符导致验证失败。

## 解决方案

### 方案设计原则
1. **质量第一**：用户明确要求"token不用管，可以大，质量第一位"
2. **自动修复**：LLM自我检测并扩写不足字段
3. **强制完成**：不允许返回短文本，必须达到最低要求

### 三层防御机制

#### 第1层：增强Prompt - 添加显式字符计数要求

在`UNIFIED_SCORING_PROMPT_TEMPLATE`中每个推理字段说明后添加**字符计数强调**：

**修改位置**：`src/scorer/llm_scorer.py:108-173`

**当前问题代码**：
```python
推理要求（activity_reasoning, ≥150字符）：
- 明确说明GitHub stars数量和最近更新时间
- 分析社区活跃度（PR/Issue数量、讨论质量）
- 说明为什么这个活跃度水平适合/不适合MGX采纳
- 如果是论文来源无代码，说明这对可复现性的影响
```

**修复后代码**：
```python
推理要求（activity_reasoning, **必须≥150字符，当前平均需要180字符才能满足要求**）：
- 明确说明GitHub stars数量和最近更新时间（提供具体数字）
- 分析社区活跃度（PR/Issue数量、讨论质量、Contributor数量）
- 说明为什么这个活跃度水平适合/不适合MGX采纳（展开论述，不少于2-3句话）
- 如果是论文来源无代码，说明这对可复现性的影响（详细分析风险）
- **字符计数示例**：像这样的段落"该候选项来自GitHub，拥有1200+ stars，说明有一定的社区关注度。最近30天内有5次提交，表明项目仍在活跃维护中。PR讨论较活跃，有15个open issues正在被处理，社区参与度良好。这种活跃度适合MGX采纳，因为持续的维护意味着更少的技术债务和更好的兼容性。"（约150字符）
```

**所有5个维度推理字段都需要同样的增强**（activity/reproducibility/license/novelty/relevance）

**后端推理字段**（backend_mgx_reasoning, backend_engineering_reasoning）也需要增强：
```python
推理要求（backend_mgx_reasoning, **必须≥200字符，当前平均需要250字符才能满足要求**）：
- 说明该后端Benchmark具体评测什么（性能/可扩展性/安全性/API设计）
- 分析MGX可以如何使用（例如：用TechEmpower基准测试MGX生成的API性能）
- 如果是数据库Benchmark，说明对MGX存储层设计的启发
- 评估工程实践价值（是否有真实生产环境的参考意义）
- **字符计数示例**：像这样的段落"该后端Benchmark专注于评测Web框架的吞吐量和延迟性能。MGX可以使用该基准测试其自动生成的FastAPI代码的性能表现，对比人工编写代码的性能差异。该基准使用真实生产环境的负载模型，包括高并发场景和复杂查询，对MGX后端开发有很高的参考价值。测试环境配置详细，结果可信度高，适合作为MGX性能优化的标准参照。"（约200字符）
```

#### 第2层：增强System Message - 强调验证失败后果

**修改位置**：`src/scorer/llm_scorer.py:580`

**当前问题代码**：
```python
messages = [
    {
        "role": "system",
        "content": "你是MGX BenchScope的Benchmark评估专家。你必须严格按照JSON Schema输出，不能返回null（除非明确说明可选），推理字段必须详细且达到最低字符要求。",
    },
    {"role": "user", "content": prompt},
]
```

**修复后代码**：
```python
messages = [
    {
        "role": "system",
        "content": (
            "你是MGX BenchScope的Benchmark评估专家。\n\n"
            "**关键要求（违反将导致验证失败）**：\n"
            "1. 所有5维推理字段（activity/reproducibility/license/novelty/relevance_reasoning）必须≥150字符\n"
            "2. 后端推理字段（backend_mgx/engineering_reasoning）如果评分>0，必须≥200字符\n"
            "3. overall_reasoning必须≥50字符\n"
            "4. 总推理字数必须≥1200字符（非后端至少800字符）\n\n"
            "**如何确保字符要求**：\n"
            "- 提供具体数据（GitHub stars数量、更新时间、PR/Issue数量）\n"
            "- 展开论述（2-3句话解释每个判断依据）\n"
            "- ���析影响（对MGX的实际价值、潜在风险、适配成本）\n"
            "- 避免简略回答，每个推理段落应包含证据+分析+结论\n\n"
            "**验证机制**：输出前请自检每个reasoning字段的字符数，不足则扩写。"
        ),
    },
    {"role": "user", "content": prompt},
]
```

#### 第3层：Self-Healing机制 - 检测短文本并自动修复

**核心思路**：
1. 首次LLM调用后，解析JSON并检测字段长度
2. 如果发现字段不足，构造补充prompt要求LLM扩写
3. 保留原始JSON，只要求LLM扩写特定字段
4. 最多重试3次，如果仍不足则降级处理

**修改位置**：`src/scorer/llm_scorer.py:586-625`

**当前问题代码**：
```python
response = await asyncio.wait_for(
    self.client.chat.completions.create(
        model=self.settings.openai.model or constants.LLM_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,  # 增加max_tokens以容纳详细推理
    ),
    timeout=constants.LLM_TIMEOUT_SECONDS * 2,  # 增加超时时间
)

content = response.choices[0].message.content or ""
logger.debug("LLM原始响应长度: %d 字符", len(content))
payload = self._load_payload(content)
try:
    extraction = UnifiedBenchmarkExtraction.parse_obj(payload)
except ValidationError as exc:
    logger.error("LLM响应字段校验失败: %s", exc)
    logger.error(
        "解析的payload: %s",
        json.dumps(payload, indent=2, ensure_ascii=False)[:1000],
    )
    raise
```

**修复后代码**：
```python
repair_attempt = 0
while True:
    response = await asyncio.wait_for(
        self.client.chat.completions.create(
            model=self.settings.openai.model or constants.LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,  # 增加max_tokens以容纳详细推理
        ),
        timeout=constants.LLM_TIMEOUT_SECONDS * 2,  # 增加超时时间
    )

    content = response.choices[0].message.content or ""
    logger.debug("LLM原始响应长度: %d 字符", len(content))
    payload = self._load_payload(content)
    try:
        extraction = UnifiedBenchmarkExtraction.parse_obj(payload)
    except ValidationError as exc:  # noqa: PERF203
        # 提取可自动修复的字符长度问题
        violations = self._extract_length_violations(exc, payload)
        if (
            violations
            and repair_attempt < constants.LLM_SELF_HEAL_MAX_ATTEMPTS
        ):
            repair_attempt += 1
            # 构造补充prompt要求LLM扩写
            fix_prompt = self._build_length_fix_prompt(violations)
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": fix_prompt})
            logger.warning(
                "LLM推理长度不足，触发第%d次纠偏: %s",
                repair_attempt,
                candidate.title[:50],
            )
            continue  # 重新调用LLM

        # 无法修复或超过重试次数
        logger.error("LLM响应字段校验失败: %s", exc)
        logger.error(
            "解析的payload: %s",
            json.dumps(payload, indent=2, ensure_ascii=False)[:1000],
        )
        raise

    # 验证总推理字数
    total_reasoning_length = (
        len(extraction.activity_reasoning)
        + len(extraction.reproducibility_reasoning)
        + len(extraction.license_reasoning)
        + len(extraction.novelty_reasoning)
        + len(extraction.relevance_reasoning)
        + len(extraction.backend_mgx_reasoning)
        + len(extraction.backend_engineering_reasoning)
        + len(extraction.overall_reasoning)
    )
    if total_reasoning_length < 1200:
        logger.warning(
            "推理总字数不足: %d < 1200，候选：%s",
            total_reasoning_length,
            candidate.title[:50],
        )

    return extraction  # 成功解析，退出循环
```

**新增辅助方法1：_extract_length_violations**

**添加位置**：`src/scorer/llm_scorer.py`（在类中新增方法）

```python
def _extract_length_violations(
    self, error: ValidationError, payload: dict[str, Any]
) -> Dict[str, Tuple[int, int]]:
    """从Pydantic错误中提取可自动修复的字符长度问题

    Returns:
        Dict[field_name, (required_length, current_length)]
        如果无法自动修复，返回空字典
    """
    violations: Dict[str, Tuple[int, int]] = {}
    for err in error.errors():
        # 只处理string_too_short错误
        if err.get("type") != "string_too_short":
            return {}  # 有其他类型错误，不能自动修复

        # 提取字段名
        loc = err.get("loc") or ()
        field = loc[0] if loc else None
        if not field:
            return {}

        # 提取最小长度要求
        min_length = err.get("ctx", {}).get("min_length")
        if not isinstance(min_length, int):
            return {}

        # 提取当前长度
        current_value = payload.get(field, "") or ""
        current_length = len(str(current_value))

        violations[field] = (min_length, current_length)

    return violations
```

**新增辅助方法2：_build_length_fix_prompt**

**添加位置**：`src/scorer/llm_scorer.py`（在类中新增方法）

```python
# 定义推理字段的有序列表（在类外部，方便_build_length_fix_prompt使用）
REASONING_FIELD_ORDER = [
    "activity_reasoning",
    "reproducibility_reasoning",
    "license_reasoning",
    "novelty_reasoning",
    "relevance_reasoning",
    "backend_mgx_reasoning",
    "backend_engineering_reasoning",
    "overall_reasoning",
]

REASONING_FIELD_LABELS = {
    "activity_reasoning": "activity_reasoning（活跃度推理）",
    "reproducibility_reasoning": "reproducibility_reasoning（可复现性推理）",
    "license_reasoning": "license_reasoning（许可推理）",
    "novelty_reasoning": "novelty_reasoning（新颖性推理）",
    "relevance_reasoning": "relevance_reasoning（MGX相关性推理）",
    "backend_mgx_reasoning": "backend_mgx_reasoning（后端MGX相关性推理）",
    "backend_engineering_reasoning": "backend_engineering_reasoning（后端工程价值推理）",
    "overall_reasoning": "overall_reasoning（综合推理）",
}

def _build_length_fix_prompt(
    self, violations: Dict[str, Tuple[int, int]]
) -> str:
    """构造提示语，让LLM扩写字符不足的推理字段

    Args:
        violations: {field_name: (required_length, current_length)}

    Returns:
        补充prompt字符串
    """
    # 按照REASONING_FIELD_ORDER排序（保持5维+后端+综合的逻辑顺序）
    ordered_fields: List[str] = []
    for field in REASONING_FIELD_ORDER:
        if field in violations:
            ordered_fields.append(field)
    # 添加其他字段（如果有）
    for field in violations:
        if field not in ordered_fields:
            ordered_fields.append(field)

    tips = [
        "上一次的JSON输出未通过校验：以下推理字段字符数不足。",
        "请保留所有字段并重新输出完整JSON，通过补充证据、数据来源、MGX场景影响、潜在风险等方式扩写对应推理段落。",
    ]
    for field in ordered_fields:
        required, current = violations[field]
        label = REASONING_FIELD_LABELS.get(field, field)
        tips.append(
            f"- {label}: 当前{current}字符，至少{required}字符。"
        )
    tips.append("只输出符合Schema的纯JSON，不要添加额外解释或省略字段。")
    return "\n".join(tips)
```

#### 第4层：配置常量补充

**修改位置**：`src/common/constants.py`

**新增常量**：
```python
# LLM Self-Healing配置
LLM_SELF_HEAL_MAX_ATTEMPTS: Final[int] = 3  # 最多重试3次扩写
```

### 实施步骤

#### Step 1: 更新constants.py（添加Self-Healing配置）
```python
# 文件: src/common/constants.py
# 在LLM配置部分新增：

# LLM Self-Healing配置
LLM_SELF_HEAL_MAX_ATTEMPTS: Final[int] = 3  # 最多重试3次扩写
```

#### Step 2: 更新llm_scorer.py（三层防御机制）

**2.1 在文件开头添加常量定义**
```python
# 文件: src/scorer/llm_scorer.py
# 在导入语句后，UNIFIED_SCORING_PROMPT_TEMPLATE之前添加：

REASONING_FIELD_ORDER = [
    "activity_reasoning",
    "reproducibility_reasoning",
    "license_reasoning",
    "novelty_reasoning",
    "relevance_reasoning",
    "backend_mgx_reasoning",
    "backend_engineering_reasoning",
    "overall_reasoning",
]

REASONING_FIELD_LABELS = {
    "activity_reasoning": "activity_reasoning（活跃度推理）",
    "reproducibility_reasoning": "reproducibility_reasoning（可复现性推理）",
    "license_reasoning": "license_reasoning（许可推理）",
    "novelty_reasoning": "novelty_reasoning（新颖性推理）",
    "relevance_reasoning": "relevance_reasoning（MGX相关性推理）",
    "backend_mgx_reasoning": "backend_mgx_reasoning（后端MGX相关性推理）",
    "backend_engineering_reasoning": "backend_engineering_reasoning（后端工程价值推理）",
    "overall_reasoning": "overall_reasoning（综合推理）",
}
```

**2.2 增强Prompt模板**

修改`UNIFIED_SCORING_PROMPT_TEMPLATE`中的5个维度推理要求（第3部分第99-173行）：

```python
推理要求（activity_reasoning, **必须≥150字符，当前平均需要180字符才能满足要求**）：
- 明确说明GitHub stars数量和最近更新时间（提供具体数字）
- 分析社区活跃度（PR/Issue数量、讨论质量、Contributor数量）
- 说明为什么这个活跃度水平适合/不适合MGX采纳（展开论述，不少于2-3句话）
- 如果是论文来源无代码，说明这对可复现性的影响（详细分析风险）
- **字符计数示例**：像这样的段落"该候选项来自GitHub，拥有1200+ stars，说明有一定的社区关注度。最近30天内有5次提交，表明项目仍在活跃维护中。PR讨论较活跃，有15个open issues正���被处理，社区参与度良好。这种活跃度适合MGX采纳，因为持续的维护意味着更少的技术债务和更好的兼容性。"（约150字符）
```

（对reproducibility/license/novelty/relevance也做同样修改，后端推理字段改为200字符示例）

**2.3 增强System Message**

修改`_call_llm`方法中的messages构造（约第577-583行）：

```python
messages = [
    {
        "role": "system",
        "content": (
            "你是MGX BenchScope的Benchmark评估专家。\n\n"
            "**关键要求（违反将导致验证失败）**：\n"
            "1. 所有5维推理字段（activity/reproducibility/license/novelty/relevance_reasoning）必须≥150字符\n"
            "2. 后端推理字段（backend_mgx/engineering_reasoning）如果评分>0，必须≥200字符\n"
            "3. overall_reasoning必须≥50字符\n"
            "4. 总推理字数必须≥1200字符（非后端至少800字符）\n\n"
            "**如何确保字符要求**：\n"
            "- 提供具体数据（GitHub stars数量、更新时间、PR/Issue数量）\n"
            "- 展开论述（2-3句话解释每个判断依据）\n"
            "- 分析影响（对MGX的实际价值、潜在风险、适配成本）\n"
            "- 避免简略回答，每个推理段落应包含证据+分析+结论\n\n"
            "**验证机制**：输出前请自检每个reasoning字段的字符数，不足则扩写。"
        ),
    },
    {"role": "user", "content": prompt},
]
```

**2.4 实现Self-Healing循环**

替换`_call_llm`方法中的LLM调用和验证逻辑（约第586-625行）：

```python
repair_attempt = 0
while True:
    response = await asyncio.wait_for(
        self.client.chat.completions.create(
            model=self.settings.openai.model or constants.LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,  # 增加max_tokens以容纳详细推理
        ),
        timeout=constants.LLM_TIMEOUT_SECONDS * 2,  # 增加超时时间
    )

    content = response.choices[0].message.content or ""
    logger.debug("LLM原始响应长度: %d 字符", len(content))
    payload = self._load_payload(content)
    try:
        extraction = UnifiedBenchmarkExtraction.parse_obj(payload)
    except ValidationError as exc:  # noqa: PERF203
        # 提取可自动修复的字符长度问题
        violations = self._extract_length_violations(exc, payload)
        if (
            violations
            and repair_attempt < constants.LLM_SELF_HEAL_MAX_ATTEMPTS
        ):
            repair_attempt += 1
            # 构造补充prompt要求LLM扩写
            fix_prompt = self._build_length_fix_prompt(violations)
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": fix_prompt})
            logger.warning(
                "LLM推理长度不足，触发第%d次纠偏: %s",
                repair_attempt,
                candidate.title[:50],
            )
            continue  # 重新调用LLM

        # 无法修复或超过重试次数
        logger.error("LLM响应字段校验失败: %s", exc)
        logger.error(
            "解析的payload: %s",
            json.dumps(payload, indent=2, ensure_ascii=False)[:1000],
        )
        raise

    # 验证总推理字数
    total_reasoning_length = (
        len(extraction.activity_reasoning)
        + len(extraction.reproducibility_reasoning)
        + len(extraction.license_reasoning)
        + len(extraction.novelty_reasoning)
        + len(extraction.relevance_reasoning)
        + len(extraction.backend_mgx_reasoning)
        + len(extraction.backend_engineering_reasoning)
        + len(extraction.overall_reasoning)
    )
    if total_reasoning_length < 1200:
        logger.warning(
            "推理总字数不足: %d < 1200，候选：%s",
            total_reasoning_length,
            candidate.title[:50],
        )

    return extraction  # 成功解析，退出循环
```

**2.5 添加辅助方法**

在`LLMScorer`类中添加两个新方法（在类的末尾，`score_batch`方法之前）：

```python
def _extract_length_violations(
    self, error: ValidationError, payload: dict[str, Any]
) -> Dict[str, Tuple[int, int]]:
    """从Pydantic错误中提取可自动修复的字符长度问题

    Returns:
        Dict[field_name, (required_length, current_length)]
        如果无法自动修复，返回空字典
    """
    violations: Dict[str, Tuple[int, int]] = {}
    for err in error.errors():
        # 只处理string_too_short错误
        if err.get("type") != "string_too_short":
            return {}  # 有其他类型错误，不能自动修复

        # 提取字段名
        loc = err.get("loc") or ()
        field = loc[0] if loc else None
        if not field:
            return {}

        # 提取最小长度要求
        min_length = err.get("ctx", {}).get("min_length")
        if not isinstance(min_length, int):
            return {}

        # ��取当前长度
        current_value = payload.get(field, "") or ""
        current_length = len(str(current_value))

        violations[field] = (min_length, current_length)

    return violations

def _build_length_fix_prompt(
    self, violations: Dict[str, Tuple[int, int]]
) -> str:
    """构造提示语，让LLM扩写字符不足的推理字段

    Args:
        violations: {field_name: (required_length, current_length)}

    Returns:
        补充prompt字符串
    """
    # 按照REASONING_FIELD_ORDER排序（保持5维+后端+综合的逻辑顺序）
    ordered_fields: List[str] = []
    for field in REASONING_FIELD_ORDER:
        if field in violations:
            ordered_fields.append(field)
    # 添加其他字段（如果有）
    for field in violations:
        if field not in ordered_fields:
            ordered_fields.append(field)

    tips = [
        "上一次的JSON输出未通过校验：以下推理字段字符数不足。",
        "请保留所有字段并重新输出完整JSON，通过补充证据、数据来源、MGX场景影响、潜在风险等方式扩写对应推理段落。",
    ]
    for field in ordered_fields:
        required, current = violations[field]
        label = REASONING_FIELD_LABELS.get(field, field)
        tips.append(
            f"- {label}: 当前{current}字符，至少{required}字符。"
        )
    tips.append("只输出符合Schema的纯JSON，不要添加额外解释或省略字段。")
    return "\n".join(tips)
```

#### Step 3: 测试验证（由Claude Code执行）

测试计划（修复后由Claude Code执行）：
1. 运行完整流程：`.venv/bin/python -m src.main`
2. 检查日志中是否有"触发第X次纠偏"警告
3. 验证评分是否全部成功（无ValidationError）
4. 检查飞书表格字段是否完整填充
5. 抽样检查推理字段字符数（应≥150或200）

预期结果：
- 第1次LLM调用可能仍返回短文本
- Self-Healing机制自动触发，要求LLM扩写
- 第2次或第3次LLM调用成功通过验证
- 最终评分成功率≥95%（容许极少数边缘case失败）

## 实施检查清单

Codex执行前请自检：
- [ ] 所有代码修改遵循Python PEP8规范
- [ ] 新增常量定义在`constants.py`
- [ ] 新增方法有完整docstring（中文）
- [ ] Self-Healing循环逻辑正确（最多3次重试）
- [ ] 日志记录完整（warning级别记录重试，error级别记录最终失败）
- [ ] 不破坏现有功能（保留原有评分逻辑）

## 成功标准

修复成功的标志：
1. ✅ 运行`.venv/bin/python -m src.main`无ValidationError
2. ✅ 日志中出现"LLM推理长度不足，触发第X次纠偏"警告（说明Self-Healing工作）
3. ✅ 最终评分成功率≥95%
4. ✅ 飞书表格中推理字段完整填充（≥150/200字符）
5. ✅ 总推理字数≥1200字符（通过日志验证）

## 备注

- 本修复方案基于用户明确要求"token不用管，可以大，质量第一位"
- Self-Healing机制会增加LLM调用次数（最多4次：1次初始+3次修复）
- 预计成本增加20-30%，但数据质量提升显著
- 如需进一步优化成本，可考虑降低并发度（从50降至30）
