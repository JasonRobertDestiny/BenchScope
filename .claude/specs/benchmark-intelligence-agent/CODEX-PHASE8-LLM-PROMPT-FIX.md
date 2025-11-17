# Codex Phase 8: LLM评分Prompt修复指令

**创建时间**: 2025-11-16
**优先级**: P1 (中优先级 - 不阻塞Phase 8验收，但影响评分质量)
**预计工期**: 2小时
**背景**: Phase 8飞书字段映射已修复，但LLM评分Prompt存在问题导致Pydantic验证失败

---

## 1. 问题描述

### 1.1 错误现象

**执行命令**: `PYTHONPATH=. .venv/bin/python src/main.py`

**错误日志**:
```
[ERROR] src.scorer.llm_scorer: LLM响应字段校验失败: 4 validation errors for BenchmarkExtraction
activity_score
  Field required [type=missing, input_value={'is_benchmark': True, 't...ded for consideration."}, input_type=dict]
reproducibility_score
  Field required [type=missing, input_value={'is_benchmark': True, 't...ded for consideration."}, input_type=dict]
license_score
  Field required [type=missing, input_value={'is_benchmark': True, 't...ded for consideration."}, input_type=dict]
novelty_score
  Field required [type=missing, input_value={'is_benchmark': True, 't...ded for consideration."}, input_type=dict]
```

### 1.2 根本原因

**问题文件**: `src/scorer/llm_scorer.py`

**原因分析**:
1. LLM返回的JSON包含 `"is_benchmark": True` 字段（不在Pydantic模型中）
2. LLM未返回必需的 `activity_score`, `reproducibility_score`, `license_score`, `novelty_score` 字段
3. Prompt没有明确要求LLM **必须**返回所有5维评分字段
4. JSON schema约束不够严格

**当前影响**:
- 系统正确回退到规则评分（兜底机制正常）
- Phase 8新增的5个字段仍能正常采集和存储
- 但评分质量受影响，无法体现LLM智能评分的优势

---

## 2. 修复目标

### 2.1 功能目标

1. **LLM必须返回5维评分**: activity_score, reproducibility_score, license_score, novelty_score, relevance_score
2. **Pydantic验证100%通过**: 所有返回字段符合 `BenchmarkExtraction` 模型
3. **Phase 8新字段提取率≥60%**: task_domain, metrics, baselines, institution, authors, dataset_size至少60%的候选项能提取到

### 2.2 质量目标

- **平均分提升**: 从4.36/10提升至6.5+/10
- **高优先级命中率**: 从0%提升至20%+
- **MGX适配度评分**: 平均从4.08提升至7.0+

---

## 3. 修复方案

### 3.1 核心修改点

**文件**: `src/scorer/llm_scorer.py`

需要修改的内容:
1. `BenchmarkExtraction` Pydantic模型（如果有字段定义问题）
2. `SCORING_PROMPT_TEMPLATE` Prompt模板（重点）
3. `_call_llm_with_structure()` 方法的JSON schema约束

---

### 3.2 Pydantic模型检查

**位置**: `src/scorer/llm_scorer.py` 中的 `BenchmarkExtraction` 类

**检查清单**:
```python
class BenchmarkExtraction(BaseModel):
    """Benchmark信息提取结果（Phase 8扩展）"""

    # ✅ 5维评分（必需字段，ge=0, le=10）
    activity_score: float = Field(..., ge=0, le=10, description="活跃度评分 0-10")
    reproducibility_score: float = Field(..., ge=0, le=10, description="可复现性评分 0-10")
    license_score: float = Field(..., ge=0, le=10, description="许可合规评分 0-10")
    novelty_score: float = Field(..., ge=0, le=10, description="新颖性评分 0-10")
    relevance_score: float = Field(..., ge=0, le=10, description="MGX适配度评分 0-10")

    score_reasoning: str = Field(..., description="评分依据（100-200字）")

    # ✅ Phase 8新增字段（可选，但要有明确默认值）
    task_domain: Optional[str] = Field(
        None,
        description="任务领域分类（必须从以下选项中选择一个或多个，用逗号分隔）：Coding, DeepResearch, Reasoning, ToolUse, Collaboration, WebDev, GUI, Other"
    )
    metrics: Optional[List[str]] = Field(
        None,
        description="评估指标列表（如Pass@1, BLEU, F1-Score），从摘要/README中提取，最多5个"
    )
    baselines: Optional[List[str]] = Field(
        None,
        description="基准模型或框架列表（如GPT-4, Claude-3.5-Sonnet），从摘要/README中提取，最多5个"
    )
    institution: Optional[str] = Field(
        None,
        description="主要研究机构（如Stanford University, OpenAI），优先选择第一作者单位"
    )
    authors: Optional[List[str]] = Field(
        None,
        description="作者列表（最多前5位），格式：['FirstName LastName', ...]"
    )
    dataset_size: Optional[int] = Field(
        None,
        description="数据集样本数量（统一为整数，如1000），从描述中提取数字"
    )
    dataset_size_description: Optional[str] = Field(
        None,
        description="数据集规模原始描述（如'1000 coding problems'），保留原文"
    )
```

**关键检查**:
- ❌ **禁止**在模型中包含 `is_benchmark` 字段（LLM不应该判断是否为benchmark）
- ✅ 5维评分字段必须是 `Field(..., ge=0, le=10)` 格式（必需字段）
- ✅ Phase 8字段可以是 `Optional`，但必须有清晰的description

---

### 3.3 Prompt模板优化 (核心修复)

**位置**: `src/scorer/llm_scorer.py` 中的 `SCORING_PROMPT_TEMPLATE`

#### 3.3.1 Prompt结构要求

Prompt必须包含以下部分：

```python
SCORING_PROMPT_TEMPLATE = """你是BenchScope系统的Benchmark评估专家。请根据以下信息对候选Benchmark进行5维评分并提取关键字段。

【重要】你必须严格按照JSON schema返回结果，所有评分字段都是必需的，不能缺失。

【MGX框架背景】
MGX是一个多智能体协作框架，专注于Vibe Coding（AI原生编程）。核心应用场景包括：
- P0（最高优先级）：Coding（代码生成/理解）、WebDev（Web开发/自动化）、GUI（图形界面操作）
- P1（高优先级）：ToolUse（工具调用/API使用）、Collaboration（多智能体协作）
- P2（中优先级）：Reasoning（推理/数学）、DeepResearch（深度研究）

【候选Benchmark信息】
标题: {title}
来源: {source}
摘要/README: {abstract}
GitHub Stars: {github_stars}
许可证: {license_type}
任务类型（初步识别）: {task_type}

【采集器初步提取的信息】
原始指标列表: {raw_metrics}
原始Baseline列表: {raw_baselines}
原始作者: {raw_authors}
原始机构: {raw_institutions}
原始数据集规模: {raw_dataset_size}

---

【评分维度说明】

⚠️ **重要**: 每个评分维度都必须给出0-10的分数，不能省略任何评分字段。

1. **活跃度** (activity_score, 0-10分，权重15%)
   评分依据：
   - GitHub Stars数量：
     * 10分: >1000 stars
     * 8分: 500-1000 stars
     * 6分: 100-500 stars
     * 4分: 50-100 stars
     * 2分: 10-50 stars
     * 0分: <10 stars或无GitHub数据
   - 最近更新时间：
     * +2分: 近3个月有更新
     * +1分: 近6个月有更新
     * -2分: 超过1年未更新
   - 社区活跃度：
     * +1分: 有PR/Issue讨论

2. **可复现性** (reproducibility_score, 0-10分，权重30%)
   评分依据：
   - 数据集开源状态：
     * 10分: 完全开源+公开下载链接
     * 7分: 开源但需申请
     * 4分: 仅示例数据
     * 0分: 闭源或未提及
   - 代码开源状态：
     * +3分: 完整评估脚本
     * +2分: 部分代码
     * +1分: 仅示例
   - 评估指标明确度：
     * +2分: 提供详细Metrics定义和计算方法
   - Baseline可验证性：
     * +2分: 提供主流模型评测结果
   - 文档完整性：
     * +1分: 有详细README/论文

3. **许可合规** (license_score, 0-10分，权重20%)
   评分依据：
   - 10分: MIT/Apache-2.0/BSD（完全开放）
   - 7分: GPL系列（传染性开源）
   - 4分: CC-BY（学术使用）
   - 0分: 专有许可或无许可证

4. **新颖性** (novelty_score, 0-10分，权重15%)
   评分依据：
   - 任务创新性：
     * 10分: 全新任务
     * 7分: 现有任务新角度
     * 4分: 改进现有Benchmark
     * 2分: 数据扩充
   - 评估方法创新：
     * +2分: 新颖的评估指标
   - 时间性：
     * +2分: 2024-2025年
     * +1分: 2023年
     * 0分: 2022年及更早

5. **MGX适配度** (relevance_score, 0-10分，权重25% - **Phase 8重点提升**)
   评分依据：
   - 任务领域匹配度（按优先级）：
     * 10分: P0领域（Coding/WebDev/GUI）直接适用
     * 8分: P1领域（ToolUse/Collaboration）高度相关
     * 6分: P2领域（Reasoning/DeepResearch）中度相关
     * 3分: 其他领域（NLP/CV/语音）但有可迁移性
     * 0分: 完全不相关（纯NLP分类/图像识别等）

   - 任务类型细化（额外加分）：
     * Coding细分: +2分代码生成, +1分代码理解/补全
     * WebDev细分: +2分浏览器自动化, +1分Web爬虫/测试
     * GUI细分: +2分跨平台GUI操作, +1分特定平台
     * ToolUse细分: +2分复杂API调用链, +1分单一API调用
     * Collaboration细分: +2分多智能体协作, +1分单智能体规划

   - 评估维度匹配：
     * +1分: 评估代码正确性（Pass@k, 功能测试）
     * +1分: 评估执行效率（时间/步数/成本）
     * +1分: 评估真实场景表现（非synthetic数据）

---

【字段提取指令】

⚠️ **重要**: 以下字段为可选字段，如果摘要/README中没有明确信息，可以填写null，但不能省略字段。

1. **task_domain**（任务领域）
   - 必须从以下选项中选择一个或多个（多个用逗号分隔）：
     * Coding: 代码生成、代码理解、程序合成、代码补全
     * WebDev: 浏览器自动化、Web爬虫、Web应用测试
     * GUI: 图形界面操作、UI自动化、跨平台GUI
     * ToolUse: API调用、工具使用、函数调用
     * Collaboration: 多智能体协作、任务分解、团队协作
     * Reasoning: 数学推理、逻辑推理、问题求解
     * DeepResearch: 深度研究、文献综述、知识图谱
     * Other: 以上都不符合时选择
   - 优先级: Coding > WebDev > GUI > ToolUse > Collaboration > Reasoning > DeepResearch > Other
   - 如果无法判断，填写"Other"

2. **metrics**（评估指标）
   - 从摘要/README中提取评估指标，格式统一为：
     * Pass@1, Pass@5, Pass@10（代码通过率）
     * BLEU, ROUGE-L（文本相似度）
     * Exact Match, F1-Score（匹配度）
     * Success Rate, Completion Rate（成功率）
     * Accuracy, Precision, Recall（分类指标）
   - 最多提取5个主要指标
   - 如果摘要中未明确提及，可根据任务类型推断常用指标（标注"推断"）
   - 如果无法提取，返回null

3. **baselines**（基准模型）
   - 从摘要/README中提取已验证的基准模型，统一命名：
     * GPT-4, GPT-4-Turbo, GPT-3.5-Turbo（OpenAI系列）
     * Claude-3.5-Sonnet, Claude-3-Opus（Anthropic系列）
     * Llama-3.1-70B, Llama-2-13B（Meta系列）
     * Mistral-7B, DeepSeek-Coder（开源系列）
     * Codex, StarCoder, CodeLlama（代码专用）
   - 最多提取5个主流模型
   - 优先提取论文中明确提及的模型
   - 如果无法提取，返回null

4. **institution**（机构）
   - 优先提取第一作者或通讯作者的单位
   - 统一命名：Stanford University, MIT, OpenAI, Google DeepMind, Meta AI
   - 如果有多个机构，选择最知名的一个
   - 如果无法提取，返回null

5. **authors**（作者）
   - 提取前5位作者，格式：["FirstName LastName", ...]
   - 如果摘要中无作者信息，可从GitHub仓库owner或论文作者推断
   - 如果无法提取，返回null

6. **dataset_size**（数据集规模）
   - 从描述中提取数字并统一为整数（如"1k samples" → 1000）
   - 如果是范围（如"500-1000 problems"），取平均值（750）
   - 常见单位换算：k=1000, M=1000000
   - 如果无法提取，返回null

7. **dataset_size_description**（数据集规模描述）
   - 保留原始描述，如"1000 coding problems", "500 test cases", "10k web tasks"
   - 如果无法提取，返回null

---

【评分输出要求】

1. ⚠️ **强制要求**: 每个评分维度（activity_score, reproducibility_score, license_score, novelty_score, relevance_score）都必须给出0-10的分数，允许小数点后1位
2. score_reasoning字段必须说明：
   - 总分如何计算（各维度得分*权重）
   - 为何给出该MGX适配度评分（匹配哪个优先级领域）
   - 为何给出该可复现性评分（是否开源数据/代码/Metrics）
   - 是否推荐纳入MGX Benchmark池（总分≥6.5 + 适配度≥7推荐）
3. 字数控制在100-200字

---

【输出格式】

请严格按照以下JSON schema返回结果，不要添加额外字段（如is_benchmark等）：

{{
  "activity_score": <float>,  // 必需，0-10
  "reproducibility_score": <float>,  // 必需，0-10
  "license_score": <float>,  // 必需，0-10
  "novelty_score": <float>,  // 必需，0-10
  "relevance_score": <float>,  // 必需，0-10
  "score_reasoning": "<string>",  // 必需，100-200字
  "task_domain": "<string or null>",  // 可选
  "metrics": [<string>, ...] or null,  // 可选
  "baselines": [<string>, ...] or null,  // 可选
  "institution": "<string or null>",  // 可选
  "authors": [<string>, ...] or null,  // 可选
  "dataset_size": <int or null>,  // 可选
  "dataset_size_description": "<string or null>"  // 可选
}}

⚠️ **再次强调**:
- 所有评分字段都是必需的，不能缺失
- 不要添加is_benchmark等额外字段
- Phase 8字段如果无法提取，填写null而非省略
"""
```

---

### 3.4 JSON Schema强化

**位置**: `src/scorer/llm_scorer.py` 中的 `_call_llm_with_structure()` 方法

**当前代码**:
```python
async def _call_llm_with_structure(
    self,
    prompt: str,
    response_model: type[BaseModel],
) -> BaseModel:
    """调用LLM并返回结构化输出（使用Pydantic schema）"""

    messages = [
        {"role": "system", "content": "你是BenchScope系统的Benchmark评估专家。请严格按照schema返回JSON格式结果。"},
        {"role": "user", "content": prompt},
    ]

    completion = await self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=0.1,  # 低温度确保稳定性
        max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
        response_format={"type": "json_object"},  # 强制JSON输出
    )

    # 解析JSON并验证schema
    response_text = completion.choices[0].message.content
    response_data = json.loads(response_text)

    # Pydantic自动验证
    return response_model(**response_data)
```

**优化建议**:

```python
async def _call_llm_with_structure(
    self,
    prompt: str,
    response_model: type[BaseModel],
) -> BaseModel:
    """调用LLM并返回结构化输出（使用Pydantic schema）"""

    # 生成JSON schema并注入到prompt中
    schema = response_model.model_json_schema()
    required_fields = schema.get("required", [])

    system_prompt = f"""你是BenchScope系统的Benchmark评估专家。

【严格要求】
1. 必须按照JSON schema返回结果
2. 以下字段是必需的，不能缺失: {', '.join(required_fields)}
3. 不要添加schema中未定义的额外字段
4. 所有评分字段必须是0-10的浮点数
5. 可选字段如果无法提取，填写null而非省略字段

【JSON Schema】
{json.dumps(schema, indent=2, ensure_ascii=False)}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,  # 低温度确保稳定性
            max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
            response_format={"type": "json_object"},  # 强制JSON输出
        )

        # 解析JSON并验证schema
        response_text = completion.choices[0].message.content
        response_data = json.loads(response_text)

        # 验证必需字段
        missing_fields = [f for f in required_fields if f not in response_data]
        if missing_fields:
            raise ValueError(f"LLM响应缺少必需字段: {missing_fields}")

        # 移除额外字段（如is_benchmark）
        allowed_fields = set(schema["properties"].keys())
        extra_fields = set(response_data.keys()) - allowed_fields
        if extra_fields:
            logger.warning(f"LLM返回了额外字段（已移除）: {extra_fields}")
            for field in extra_fields:
                response_data.pop(field)

        # Pydantic自动验证
        return response_model(**response_data)

    except (json.JSONDecodeError, ValueError, ValidationError) as e:
        logger.error(f"LLM响应解析失败: {e}")
        logger.error(f"原始响应: {response_text[:500]}")
        raise
```

---

## 4. 实施步骤

### Step 1: 检查Pydantic模型 (10分钟)

```bash
# 查看当前模型定义
PYTHONPATH=. .venv/bin/python -c "
from src.scorer.llm_scorer import BenchmarkExtraction
import json
print(json.dumps(BenchmarkExtraction.model_json_schema(), indent=2, ensure_ascii=False))
"
```

**检查清单**:
- [ ] 5维评分字段都是必需字段（`Field(..., ge=0, le=10)`）
- [ ] 不存在 `is_benchmark` 字段
- [ ] Phase 8字段都是 `Optional` 类型

### Step 2: 更新Prompt模板 (30分钟)

**文件**: `src/scorer/llm_scorer.py`

**修改内容**:
1. 替换 `SCORING_PROMPT_TEMPLATE` 为上面提供的优化版本
2. 确保Prompt中明确说明：
   - 必须返回所有5维评分
   - 不要添加 `is_benchmark` 等额外字段
   - Phase 8字段无法提取时填null

### Step 3: 强化JSON Schema验证 (20分钟)

**文件**: `src/scorer/llm_scorer.py`

**修改内容**:
1. 更新 `_call_llm_with_structure()` 方法
2. 在system prompt中注入JSON schema
3. 添加必需字段检查
4. 自动移除额外字段

### Step 4: 单元测试 (20分钟)

**创建测试脚本**: `scripts/test_phase8_llm_scoring.py`

```python
"""测试Phase 8 LLM评分功能"""
import asyncio
from src.collectors import ArxivCollector
from src.scorer import LLMScorer

async def test_llm_scoring():
    # 1. 采集1条arXiv样本
    collector = ArxivCollector()
    candidates = await collector.collect()
    test_candidate = candidates[0]

    print(f"测试候选: {test_candidate.title}")

    # 2. LLM评分
    async with LLMScorer() as scorer:
        scored = await scorer.score_batch([test_candidate])

    result = scored[0]

    # 3. 验证必需字段
    print(f"\n【5维评分】")
    print(f"活跃度: {result.activity_score}/10")
    print(f"可复现性: {result.reproducibility_score}/10")
    print(f"许可合规: {result.license_score}/10")
    print(f"新颖性: {result.novelty_score}/10")
    print(f"MGX适配度: {result.relevance_score}/10")
    print(f"总分: {result.total_score}/10")
    print(f"优先级: {result.priority}")

    # 4. 验证Phase 8字段
    print(f"\n【Phase 8字段】")
    print(f"任务领域: {result.task_domain}")
    print(f"评估指标: {result.metrics}")
    print(f"基准模型: {result.baselines}")
    print(f"机构: {result.institution}")
    print(f"作者: {result.authors}")
    print(f"数据集规模: {result.dataset_size} ({result.dataset_size_description})")

    # 5. 断言验证
    assert result.activity_score >= 0 and result.activity_score <= 10, "活跃度评分超出范围"
    assert result.reproducibility_score >= 0 and result.reproducibility_score <= 10, "可复现性评分超出范围"
    assert result.license_score >= 0 and result.license_score <= 10, "许可合规评分超出范围"
    assert result.novelty_score >= 0 and result.novelty_score <= 10, "新颖性评分超出范围"
    assert result.relevance_score >= 0 and result.relevance_score <= 10, "MGX适配度评分超出范围"
    assert result.total_score >= 0 and result.total_score <= 10, "总分超出范围"
    assert result.reasoning, "评分依据不能为空"

    print(f"\n✅ LLM评分测试通过")

if __name__ == "__main__":
    asyncio.run(test_llm_scoring())
```

**运行测试**:
```bash
PYTHONPATH=. .venv/bin/python scripts/test_phase8_llm_scoring.py
```

### Step 5: 集成测试 (40分钟)

**运行完整流程3次**:
```bash
# Run 1
PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_fix_run1.log

# Run 2
PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_fix_run2.log

# Run 3
PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_fix_run3.log
```

**验证指标**:
```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_phase7_scores.py
```

**预期结果**:
- ✅ LLM评分成功率≥80% (不再大量回退到规则评分)
- ✅ 平均分≥6.5/10 (从4.36提升)
- ✅ 高优先级命中率≥20% (从0%提升)
- ✅ MGX适配度平均分≥7.0/10 (从4.08提升)
- ✅ Phase 8字段提取率≥60%

---

## 5. 验收标准

### 5.1 功能验收

| 验收项 | 标准 | 验收方法 |
|--------|------|---------|
| **LLM评分成功率** | ≥80% | 运行3次main.py，统计Pydantic验证失败次数 |
| **5维评分完整性** | 100%非空 | 检查所有评分字段是否都有值 |
| **Phase 8字段提取率** | ≥60% | 统计task_domain等字段的非空率 |
| **Pydantic验证通过率** | 100% | 无ValidationError日志 |

### 5.2 质量验收

| 指标 | Phase 7实测 | Phase 8目标 | 验收方法 |
|------|-------------|------------|---------|
| **平均分** | 4.36/10 | ≥6.5/10 | scripts/analyze_phase7_scores.py |
| **高优先级命中率** | 0% | ≥20% | 统计priority="high"的比例 |
| **MGX适配度评分** | 4.08/10 | ≥7.0/10 | 统计relevance_score平均值 |
| **LLM规则兜底率** | 95%+ | ≤20% | grep "规则兜底评分" logs/*.log |

---

## 6. 注意事项

### 6.1 不要修改的部分

- ❌ **不要修改数据模型** (`src/models.py`) - 已经由Phase 8完成
- ❌ **不要修改飞书存储** (`src/storage/feishu_storage.py`) - 已修复完成
- ❌ **不要修改采集器** - 采集器的raw_*字段提取功能正常
- ❌ **不要修改规则评分逻辑** - 规则评分作为兜底机制保持不变

### 6.2 重点关注的部分

- ✅ **Prompt清晰度**: 确保LLM理解每个字段的含义和格式
- ✅ **JSON schema约束**: 必需字段检查、额外字段移除
- ✅ **错误处理**: LLM失败时正确回退到规则评分
- ✅ **日志记录**: 记录LLM原始响应以便调试

### 6.3 调试建议

如果修复后仍有Pydantic验证失败：

1. **查看LLM原始响应**:
```python
logger.error(f"LLM原始响应: {response_text}")
```

2. **检查JSON格式**:
```python
logger.error(f"解析后的JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
```

3. **降低temperature**:
```python
temperature=0.05  # 从0.1降低到0.05
```

4. **增强system prompt**:
```python
"你必须严格按照JSON schema返回结果。任何缺失必需字段或添加额外字段都会导致系统报错。"
```

---

## 7. 交付物

### 7.1 代码修改

- [ ] `src/scorer/llm_scorer.py` - Prompt模板优化 + JSON schema强化
- [ ] `scripts/test_phase8_llm_scoring.py` - 单元测试脚本（新增）

### 7.2 测试报告

- [ ] 单元测试结果（1条样本测试通过）
- [ ] 集成测试结果（3次完整流程日志）
- [ ] 评分改善效果分析（平均分、高优先级命中率、MGX适配度）

### 7.3 文档更新

- [ ] 更新 `CODEX-PHASE8-FIELD-EXPANSION.md` 的LLM评分章节
- [ ] 创建 `PHASE8-LLM-FIX-REPORT.md` 记录修复过程和结果

---

## 8. 预期完成时间

- Step 1 (Pydantic检查): 10分钟
- Step 2 (Prompt优化): 30分钟
- Step 3 (JSON schema强化): 20分钟
- Step 4 (单元测试): 20分钟
- Step 5 (集成测试): 40分钟
- **总计**: 2小时

---

## 9. 成功标志

修复完成后，你应该看到：

```bash
# 日志中不再出现大量LLM评分失败
[INFO] src.scorer.llm_scorer: 批量评分完成: 74条

# 而非之前的
[ERROR] src.scorer.llm_scorer: LLM评分失败,使用兜底: RetryError[<Future raised ValidationError>]
[ERROR] src.scorer.llm_scorer: LLM评分失败,使用兜底: RetryError[<Future raised ValidationError>]
...（重复多次）
```

```bash
# 飞书表格中看到丰富的Phase 8字段
任务领域: Coding, WebDev  # 不再是空
评估指标: Pass@1, BLEU, F1-Score  # 不再是空
基准模型: GPT-4, Claude-3.5-Sonnet  # 不再是空
```

```bash
# 评分改善明显
平均分: 6.8/10  # 从4.36提升
高优先级: 18条 (24%)  # 从0%提升
MGX适配度: 7.2/10  # 从4.08提升
```

**Good luck, Codex!** 🚀
