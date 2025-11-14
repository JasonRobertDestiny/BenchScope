# Phase 7: 评测体系增强 - Codex开发指令

**文档版本**: v1.0
**创建时间**: 2025-11-14
**目标**: 基于最新Agent评测研究，重构BenchScope评分体系，引入多维度能力评估、安全风险检测和持续演进机制

---

## 一、背景与问题诊断

### 当前系统痛点（基于arXiv 2503.16416等最新研究）

**1. 评价维度单一**
- 现状: 仅评估活跃度、可复现性、许可、新颖性、MGX适配度等静态特征
- 问题: 缺乏对Agent核心能力（规划Planning、工具使用Tool Use、记忆Memory、协作Collaboration）的判定
- 影响: 无法区分GUI/Web/Coding/DeepResearch场景的真实差异，推送的Benchmark可能不适合实际应用

**2. 风险感知缺失**
- 现状: 无安全、鲁棒、合规相关指标
- 问题: 金融与高价值领域研究表明，传统性能分数无法暴露幻觉、越权调用、时间错配等系统性风险
- 影响: 推送到候选池的Benchmark可能在实战中不可用或存在安全隐患
- 参考: arXiv 2502.15865 - 金融Agent风险评估研究

**3. 安全攻防盲点**
- 现状: 无攻击面分析或安全暴露评分
- 问题: RAS-Eval实验显示，高级攻击可将LLM Agent任务完成率降低36.78%
- 影响: 无法保证推荐的Benchmark在对抗环境下的鲁棒性
- 参考: arXiv 2506.15253 - RAS-Eval安全评测

**4. 信息抽取准确性问题**
- 现状: 完全依赖LLM单次抽取，无校验机制
- 问题: GPT-4在科学信息抽取中存在幻觉问题，尤其是图表、单位、数值
- 影响: 论文链接、开源时间、评估指标等关键字段可能不准确
- 参考: scisimple.com - GPT-4科学信息抽取评估

**5. 静态评分，无演进机制**
- 现状: 候选入库后评分固定，不随时间更新
- 问题: Benchmark质量会随版本演进、社区活跃度变化而变化
- 影响: 无法发现已过时或质量下降的Benchmark
- 参考: arXiv 2505.11942 - LifelongAgentBench持续评测

---

## 二、改进方案概述

### 核心目标

**从单一静态评分 → 多维动态评估**

```
旧模式: 5维静态评分(0-10) → 加权总分 → 一次性入库
新模式: 3域动态评估(能力+风险+运营) → 多轮验证 → 持续更新
```

### 改进策略（5大方向）

1. **重构评分表** - 能力域 + 风险域 + 运营域三大块
2. **自进化样本池** - 高置信重述 + 扰动生成新评测情境
3. **安全/可控回路** - 攻防测试 + LLM自我评估
4. **持续学习校验** - 跨周期复测 + 分数漂移监控
5. **信息抽取双轨制** - LLM + 传统解析器并行，一致性检查

---

## 三、详细实现方案

### Task 1: 重构评分模型 (能力域 + 风险域 + 运营域)

#### 1.1 新增数据模型字段

**文件**: `src/models.py`

在 `ScoredCandidate` 模型中新增：

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict

class AgentCapabilityScores(BaseModel):
    """Agent能力域评分"""
    planning_score: float = Field(ge=0, le=10, description="规划能力：任务分解、策略制定")
    tool_use_score: float = Field(ge=0, le=10, description="工具使用：API调用、脚本执行")
    memory_score: float = Field(ge=0, le=10, description="记忆能力：上下文保持、信息检索")
    collaboration_score: float = Field(ge=0, le=10, description="协作能力：多Agent交互、任务协同")
    reasoning_score: float = Field(ge=0, le=10, description="推理能力：逻辑推理、问题求解")

class RiskDomainScores(BaseModel):
    """风险域评分"""
    security_score: float = Field(ge=0, le=10, description="安全性：无恶意代码、权限控制")
    robustness_score: float = Field(ge=0, le=10, description="鲁棒性：抗攻击、错误恢复")
    hallucination_risk: float = Field(ge=0, le=10, description="幻觉风险：0=高风险, 10=无风险")
    compliance_score: float = Field(ge=0, le=10, description="合规性：隐私保护、伦理规范")

class OperationalScores(BaseModel):
    """运营域评分（现有指标）"""
    activity_score: float = Field(ge=0, le=10)
    reproducibility_score: float = Field(ge=0, le=10)
    license_score: float = Field(ge=0, le=10)
    novelty_score: float = Field(ge=0, le=10)
    relevance_score: float = Field(ge=0, le=10)

class ScoredCandidate(RawCandidate):
    """评分后的候选项 - 重构版"""
    # 三域评分
    capability_scores: Optional[AgentCapabilityScores] = None
    risk_scores: Optional[RiskDomainScores] = None
    operational_scores: OperationalScores

    # 综合指标
    total_score: float  # 三域加权总分
    capability_total: float = 0.0  # 能力域总分
    risk_total: float = 0.0  # 风险域总分
    operational_total: float = 0.0  # 运营域总分

    # 优先级与状态
    priority: str = "medium"  # high/medium/low
    risk_level: str = "unknown"  # safe/moderate/high/critical

    # 元数据
    reasoning: str = ""  # LLM评分依据
    last_evaluated_at: Optional[datetime] = None  # 最后评分时间
    evaluation_version: str = "v2.0"  # 评分模型版本
```

#### 1.2 更新常量配置

**文件**: `src/common/constants.py`

```python
# 评分权重 - 三域模型
SCORE_WEIGHTS_V2: Final[dict[str, float]] = {
    "capability_domain": 0.40,  # 能力域权重40%
    "risk_domain": 0.30,        # 风险域权重30%
    "operational_domain": 0.30, # 运营域权重30%
}

# 能力域子权重
CAPABILITY_WEIGHTS: Final[dict[str, float]] = {
    "planning": 0.25,
    "tool_use": 0.25,
    "memory": 0.20,
    "collaboration": 0.15,
    "reasoning": 0.15,
}

# 风险域子权重
RISK_WEIGHTS: Final[dict[str, float]] = {
    "security": 0.35,
    "robustness": 0.25,
    "hallucination_risk": 0.25,
    "compliance": 0.15,
}

# 风险等级阈值
RISK_CRITICAL_THRESHOLD: Final[float] = 3.0  # 风险总分<3.0为严重
RISK_HIGH_THRESHOLD: Final[float] = 5.0
RISK_MODERATE_THRESHOLD: Final[float] = 7.0

# 优先级判定阈值（基于三域综合）
PRIORITY_HIGH_THRESHOLD_V2: Final[float] = 8.0  # 能力+风险双高
PRIORITY_MEDIUM_THRESHOLD_V2: Final[float] = 6.5
```

#### 1.3 增强LLM评分Prompt

**文件**: `src/scorer/llm_scorer.py`

在 `_build_prompt` 方法中，替换为三域评分prompt：

```python
def _build_prompt(self, candidate: RawCandidate) -> str:
    """构建三域评分prompt"""

    # 构建上下文（保留现有逻辑）
    github_info = ""
    if candidate.github_url:
        github_info = f"\nGitHub链接: {candidate.github_url}"
        if candidate.github_stars is not None:
            github_info += f"\nGitHub Stars: {candidate.github_stars:,}"

    task_info = f"\n任务类型: {candidate.task_type}" if candidate.task_type else ""
    license_info = f"\nLicense: {candidate.license_type}" if candidate.license_type else ""

    return f"""请对以下AI Benchmark候选进行**三域评分**（0-10分，保留一位小数）。

候选信息:
- 标题: {candidate.title}
- 来源: {candidate.source}
- URL: {candidate.url}
- 摘要: {(candidate.abstract or 'N/A')[:800]}
{github_info}{task_info}{license_info}

---

## 一、能力域评分 (Capability Domain)

评估该Benchmark对Agent核心能力的覆盖程度：

1. **规划能力 (planning_score)**
   - 是否评测任务分解、策略制定、目标设定能力？
   - 示例：WebArena评测Web任务规划 → 9分；MMLU无规划评测 → 2分

2. **工具使用 (tool_use_score)**
   - 是否涉及API调用、代码执行、外部工具集成？
   - 示例：ToolBench评测API使用 → 10分；纯文本QA → 1分

3. **记忆能力 (memory_score)**
   - 是否考察长期记忆、上下文保持、信息检索？
   - 示例：LifelongBench评测跨会话记忆 → 9分；单轮对话 → 3分

4. **协作能力 (collaboration_score)**
   - 是否评估多Agent交互、任务协同、角色分工？
   - 示例：AgentVerse评测多Agent协作 → 10分；单Agent任务 → 0分

5. **推理能力 (reasoning_score)**
   - 是否测试逻辑推理、问题求解、知识运用？
   - 示例：MATH评测数学推理 → 9分；信息检索任务 → 4分

---

## 二、风险域评分 (Risk Domain)

评估该Benchmark的安全性、鲁棒性和合规性：

1. **安全性 (security_score)**
   - 数据集/代码是否包含恶意内容、隐私泄露？
   - 是否有安全防护措施（输入验证、权限控制）？
   - 示例：官方学术数据集 → 9分；未验证的爬虫数据 → 4分

2. **鲁棒性 (robustness_score)**
   - 是否测试对抗样本、异常输入的处理？
   - 是否有错误恢复机制？
   - 示例：RAS-Eval包含攻击测试 → 10分；无鲁棒性测试 → 3分

3. **幻觉风险 (hallucination_risk)**
   - 评估指标是否容易被"虚假高分"误导？
   - 数据集是否有验证机制？
   - 示例：可验证答案的数据集 → 9分；主观评价 → 4分

4. **合规性 (compliance_score)**
   - 是否符合隐私保护（GDPR/HIPAA）、伦理规范？
   - License是否允许商业使用？
   - 示例：MIT License + 公开数据 → 10分；未知License → 5分

---

## 三、运营域评分 (Operational Domain)

评估该Benchmark的可维护性和实用性（保留现有5维）：

1. **活跃度 (activity_score)**: GitHub stars、最近更新频率
2. **可复现性 (reproducibility_score)**: 代码、数据、文档完整性
3. **许可合规 (license_score)**: MIT/Apache优先
4. **任务新颖性 (novelty_score)**: 与已有Benchmark差异
5. **MGX适配度 (relevance_score)**: 与多智能体/代码生成相关性

---

## 输出格式

请输出JSON，包含三域详细评分 + 综合分析：

```json
{{
  "capability_scores": {{
    "planning_score": 7.5,
    "tool_use_score": 9.0,
    "memory_score": 6.0,
    "collaboration_score": 8.5,
    "reasoning_score": 7.0
  }},
  "risk_scores": {{
    "security_score": 9.0,
    "robustness_score": 7.0,
    "hallucination_risk": 8.5,
    "compliance_score": 10.0
  }},
  "operational_scores": {{
    "activity_score": 8.5,
    "reproducibility_score": 9.0,
    "license_score": 10.0,
    "novelty_score": 7.0,
    "relevance_score": 8.0
  }},
  "reasoning": "【能力域分析】该Benchmark主要评测...(200字)\n【风险域分析】安全性方面...(150字)\n【运营域分析】项目活跃度...(150字)\n【综合建议】适合用于...(100字)"
}}
```

**评分原则**:
- 能力域：从Agent评测角度判断，非传统NLP任务标准
- 风险域：严格评估，宁可保守，发现任何安全隐患立即扣分
- 运营域：沿用现有标准，关注长期可维护性

**reasoning要求**:
- 最少500字，分4个部分
- 必须引用具体数据（stars数量、更新时间、文档质量）
- 禁止模糊描述（"较高"→"1,500 stars"）
"""
```

#### 1.4 更新评分计算逻辑

**文件**: `src/scorer/llm_scorer.py`

在 `score` 方法中，替换总分计算：

```python
async def score(self, candidate: RawCandidate) -> ScoredCandidate:
    """三域评分实现"""
    cached = await self._get_cached_score(candidate)
    if cached:
        scores = cached
    else:
        if not self.client:
            logger.warning("OpenAI未配置,使用规则兜底评分")
            scores = self._fallback_score(candidate)
        else:
            try:
                scores = await self._call_llm(candidate)
            except Exception as exc:
                logger.error("LLM评分失败,使用兜底: %s", exc)
                scores = self._fallback_score(candidate)
            else:
                await self._set_cached_score(candidate, scores)

    # 解析三域评分
    capability_scores = AgentCapabilityScores(**scores.get("capability_scores", {}))
    risk_scores = RiskDomainScores(**scores.get("risk_scores", {}))
    operational_scores = OperationalScores(**scores.get("operational_scores", {}))

    # 计算三域总分
    capability_total = (
        capability_scores.planning_score * constants.CAPABILITY_WEIGHTS["planning"] +
        capability_scores.tool_use_score * constants.CAPABILITY_WEIGHTS["tool_use"] +
        capability_scores.memory_score * constants.CAPABILITY_WEIGHTS["memory"] +
        capability_scores.collaboration_score * constants.CAPABILITY_WEIGHTS["collaboration"] +
        capability_scores.reasoning_score * constants.CAPABILITY_WEIGHTS["reasoning"]
    )

    risk_total = (
        risk_scores.security_score * constants.RISK_WEIGHTS["security"] +
        risk_scores.robustness_score * constants.RISK_WEIGHTS["robustness"] +
        risk_scores.hallucination_risk * constants.RISK_WEIGHTS["hallucination_risk"] +
        risk_scores.compliance_score * constants.RISK_WEIGHTS["compliance"]
    )

    operational_total = (
        operational_scores.activity_score * constants.SCORE_WEIGHTS["activity"] +
        operational_scores.reproducibility_score * constants.SCORE_WEIGHTS["reproducibility"] +
        operational_scores.license_score * constants.SCORE_WEIGHTS["license"] +
        operational_scores.novelty_score * constants.SCORE_WEIGHTS["novelty"] +
        operational_scores.relevance_score * constants.SCORE_WEIGHTS["relevance"]
    )

    # 综合总分
    total_score = (
        capability_total * constants.SCORE_WEIGHTS_V2["capability_domain"] +
        risk_total * constants.SCORE_WEIGHTS_V2["risk_domain"] +
        operational_total * constants.SCORE_WEIGHTS_V2["operational_domain"]
    )

    # 判定风险等级
    if risk_total < constants.RISK_CRITICAL_THRESHOLD:
        risk_level = "critical"
    elif risk_total < constants.RISK_HIGH_THRESHOLD:
        risk_level = "high"
    elif risk_total < constants.RISK_MODERATE_THRESHOLD:
        risk_level = "moderate"
    else:
        risk_level = "safe"

    # 判定优先级（能力高 + 风险低 = 高优先级）
    if total_score >= constants.PRIORITY_HIGH_THRESHOLD_V2 and risk_level in ["safe", "moderate"]:
        priority = "high"
    elif total_score >= constants.PRIORITY_MEDIUM_THRESHOLD_V2:
        priority = "medium"
    else:
        priority = "low"

    return ScoredCandidate(
        **candidate.dict(),
        capability_scores=capability_scores,
        risk_scores=risk_scores,
        operational_scores=operational_scores,
        capability_total=capability_total,
        risk_total=risk_total,
        operational_total=operational_total,
        total_score=total_score,
        priority=priority,
        risk_level=risk_level,
        reasoning=scores.get("reasoning", ""),
        last_evaluated_at=datetime.now(),
        evaluation_version="v2.0"
    )
```

---

### Task 2: 引入自进化样本池

#### 2.1 创建样本生成器

**新文件**: `src/scorer/prompt_evolution.py`

```python
"""Prompt自进化模块 - 基于Benchmark Self-Evolving思想"""
from __future__ import annotations

import logging
from typing import List, Dict
from openai import AsyncOpenAI

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)

class PromptEvolutionEngine:
    """提示词自进化引擎"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=constants.OPENAI_API_KEY,
            base_url=constants.OPENAI_BASE_URL
        )

    async def generate_evolved_scenarios(
        self,
        high_confidence_candidates: List[RawCandidate],
        num_variations: int = 3
    ) -> List[Dict[str, str]]:
        """
        基于高置信候选生成演化情境

        Args:
            high_confidence_candidates: 评分>8.5的高质量候选
            num_variations: 每个候选生成的变体数量

        Returns:
            演化后的评测情境列表
        """
        evolved_scenarios = []

        for candidate in high_confidence_candidates[:5]:  # 限制前5个高质量候选
            prompt = self._build_evolution_prompt(candidate)

            response = await self.client.chat.completions.create(
                model=constants.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是Benchmark演化专家"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # 提高创造性
                n=num_variations,
                max_tokens=800
            )

            for choice in response.choices:
                evolved_scenarios.append({
                    "original_title": candidate.title,
                    "evolved_scenario": choice.message.content,
                    "source": "self-evolution"
                })

        logger.info(f"生成{len(evolved_scenarios)}个演化情境")
        return evolved_scenarios

    def _build_evolution_prompt(self, candidate: RawCandidate) -> str:
        """构建演化prompt"""
        return f"""基于以下高质量Benchmark，生成3个演化变体：

原始Benchmark:
- 标题: {candidate.title}
- 摘要: {candidate.abstract[:300]}

演化要求:
1. **高置信重述**: 保留核心评测目标，换用不同表述
2. **情境扩展**: 增加新的评测维度（如时间约束、多模态）
3. **难度提升**: 引入更复杂的场景（如对抗样本、长期记忆）

输出格式:
1. [变体1描述]
2. [变体2描述]
3. [变体3描述]
"""
```

#### 2.2 集成到主流程

**文件**: `src/main.py`

在主流程中，定期执行自进化：

```python
async def run_self_evolution(scored_candidates: List[ScoredCandidate]):
    """运行自进化流程"""
    from src.scorer.prompt_evolution import PromptEvolutionEngine

    # 筛选高质量候选
    high_quality = [c for c in scored_candidates if c.total_score >= 8.5]

    if len(high_quality) < 3:
        logger.info("高质量候选不足3个，跳过自进化")
        return

    engine = PromptEvolutionEngine()
    evolved_scenarios = await engine.generate_evolved_scenarios(high_quality)

    # 保存演化结果到本地
    import json
    with open("data/evolved_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(evolved_scenarios, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 自进化完成，生成{len(evolved_scenarios)}个新情境")
```

---

### Task 3: 安全/可控回路

#### 3.1 创建安全评估模块

**新文件**: `src/scorer/security_validator.py`

```python
"""安全验证模块 - 基于RAS-Eval思想"""
from __future__ import annotations

import logging
import re
from typing import List, Dict, Tuple
from openai import AsyncOpenAI

from src.common import constants
from src.models import ScoredCandidate

logger = logging.getLogger(__name__)

class SecurityValidator:
    """安全验证器"""

    # CWE常见漏洞模式（简化版）
    SECURITY_PATTERNS = {
        "command_injection": r"(os\.system|subprocess\.call|eval\()",
        "sql_injection": r"(SELECT.*FROM.*WHERE|INSERT INTO)",
        "xss": r"(<script|javascript:|onerror=)",
        "path_traversal": r"\.\./",
        "hardcoded_secret": r"(password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]"
    }

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=constants.OPENAI_API_KEY,
            base_url=constants.OPENAI_BASE_URL
        )

    async def validate_candidate(
        self,
        candidate: ScoredCandidate
    ) -> Tuple[bool, List[str]]:
        """
        验证候选安全性

        Returns:
            (is_safe, warnings) - 是否安全 + 警告列表
        """
        warnings = []

        # 1. 静态模式检测（基于正则）
        if candidate.github_url:
            pattern_warnings = self._detect_security_patterns(candidate)
            warnings.extend(pattern_warnings)

        # 2. LLM自我评估（对抗性提示）
        llm_warnings = await self._llm_security_check(candidate)
        warnings.extend(llm_warnings)

        # 3. 风险评分二次验证
        if candidate.risk_scores and candidate.risk_scores.security_score < 5.0:
            warnings.append(f"风险评分过低: security_score={candidate.risk_scores.security_score}")

        is_safe = len(warnings) == 0
        return is_safe, warnings

    def _detect_security_patterns(self, candidate: ScoredCandidate) -> List[str]:
        """静态模式检测"""
        warnings = []
        text = f"{candidate.title} {candidate.abstract or ''} {candidate.reasoning}"

        for pattern_name, regex in self.SECURITY_PATTERNS.items():
            if re.search(regex, text, re.IGNORECASE):
                warnings.append(f"检测到潜在安全模式: {pattern_name}")

        return warnings

    async def _llm_security_check(self, candidate: ScoredCandidate) -> List[str]:
        """LLM对抗性安全检查"""
        prompt = f"""以安全审计专家身份，检查以下Benchmark候选的安全风险：

标题: {candidate.title}
来源: {candidate.source}
URL: {candidate.url}
摘要: {candidate.abstract[:500]}

请检查以下安全风险：
1. 是否包含恶意代码或后门？
2. 数据集是否存在隐私泄露风险？
3. 是否有未授权的外部调用？
4. License是否存在法律风险？
5. 是否存在已知的CVE漏洞？

输出格式（仅返回发现的问题，无问题返回"SAFE"）:
[风险类型]: [具体描述]
"""

        response = await self.client.chat.completions.create(
            model=constants.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是网络安全专家，专注漏洞检测"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 低温度，保持严谨
            max_tokens=500
        )

        result = response.choices[0].message.content or ""

        if "SAFE" in result.upper():
            return []
        else:
            # 解析风险项
            warnings = [line.strip() for line in result.split("\n") if line.strip()]
            return warnings
```

#### 3.2 集成到存储前验证

**文件**: `src/main.py`

在存储前增加安全回路：

```python
async def security_validation_loop(candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """安全验证循环"""
    from src.scorer.security_validator import SecurityValidator

    validator = SecurityValidator()
    safe_candidates = []
    rejected_candidates = []

    for candidate in candidates:
        is_safe, warnings = await validator.validate_candidate(candidate)

        if is_safe:
            safe_candidates.append(candidate)
        else:
            logger.warning(
                f"候选被安全拒绝: {candidate.title[:50]}\n"
                f"原因: {'; '.join(warnings)}"
            )
            rejected_candidates.append((candidate, warnings))

    # 记录被拒绝的候选
    if rejected_candidates:
        import json
        with open("logs/security_rejected.json", "w", encoding="utf-8") as f:
            json.dump([
                {
                    "title": c.title,
                    "url": c.url,
                    "warnings": w
                }
                for c, w in rejected_candidates
            ], f, ensure_ascii=False, indent=2)

    logger.info(
        f"✅ 安全验证完成: 通过{len(safe_candidates)}, "
        f"拒绝{len(rejected_candidates)}"
    )

    return safe_candidates
```

---

### Task 4: 持续学习校验

#### 4.1 创建复测调度器

**新文件**: `src/tracker/rescore_scheduler.py`

```python
"""复测调度器 - 基于LifelongAgentBench思想"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from src.storage.feishu_storage import FeishuStorage
from src.scorer.llm_scorer import LLMScorer
from src.models import RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)

class RescoreScheduler:
    """定期复测调度器"""

    RESCORE_INTERVAL_DAYS = 14  # 每14天复测一次

    def __init__(self):
        self.storage = FeishuStorage()
        self.scorer = LLMScorer()

    async def run_rescore(self):
        """执行复测任务"""
        # 1. 从飞书表格获取需要复测的候选
        candidates_to_rescore = await self._get_candidates_for_rescore()

        if not candidates_to_rescore:
            logger.info("无需复测的候选")
            return

        logger.info(f"开始复测 {len(candidates_to_rescore)} 个候选")

        # 2. 重新评分
        async with self.scorer:
            rescored = []
            for old_candidate in candidates_to_rescore:
                # 转换为RawCandidate
                raw = self._convert_to_raw(old_candidate)

                # 重新评分
                new_scored = await self.scorer.score(raw)

                # 计算分数漂移
                score_drift = new_scored.total_score - old_candidate["total_score"]

                rescored.append({
                    "title": new_scored.title,
                    "old_score": old_candidate["total_score"],
                    "new_score": new_scored.total_score,
                    "drift": score_drift,
                    "risk_level": new_scored.risk_level
                })

                # 3. 更新飞书表格
                await self.storage.update_score(
                    record_id=old_candidate["record_id"],
                    new_scores=new_scored
                )

                # 4. 如果分数下降超过2分，发送告警
                if score_drift < -2.0:
                    logger.warning(
                        f"⚠️ 候选质量下降: {new_scored.title[:50]}\n"
                        f"分数变化: {old_candidate['total_score']:.1f} → "
                        f"{new_scored.total_score:.1f} ({score_drift:+.1f})"
                    )

        # 5. 生成复测报告
        self._generate_rescore_report(rescored)

    async def _get_candidates_for_rescore(self) -> List[dict]:
        """获取需要复测的候选"""
        # 从飞书表格查询 last_evaluated_at 距今超过14天的记录
        # 这里简化实现，实际需要调用飞书API
        cutoff_date = datetime.now() - timedelta(days=self.RESCORE_INTERVAL_DAYS)

        # TODO: 实现飞书API查询
        # candidates = await self.storage.query_old_evaluations(cutoff_date)

        return []

    def _convert_to_raw(self, feishu_record: dict) -> RawCandidate:
        """将飞书记录转换为RawCandidate"""
        return RawCandidate(
            title=feishu_record["title"],
            url=feishu_record["url"],
            source=feishu_record["source"],
            abstract=feishu_record.get("abstract", ""),
            # ... 其他字段
        )

    def _generate_rescore_report(self, rescored: List[dict]):
        """生成复测报告"""
        import json

        report_path = f"logs/rescore_report_{datetime.now():%Y%m%d}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_rescored": len(rescored),
                "significant_changes": [
                    r for r in rescored if abs(r["drift"]) > 1.0
                ],
                "details": rescored
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 复测报告已生成: {report_path}")
```

#### 4.2 添加GitHub Actions定时任务

**新文件**: `.github/workflows/rescore_candidates.yml`

```yaml
name: BenchScope Rescore Scheduler

on:
  schedule:
    - cron: '0 10 */14 * *'  # 每14天的10:00运行
  workflow_dispatch:

jobs:
  rescore:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run rescore scheduler
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
        run: |
          python -c "
          import asyncio
          from src.tracker.rescore_scheduler import RescoreScheduler

          async def main():
              scheduler = RescoreScheduler()
              await scheduler.run_rescore()

          asyncio.run(main())
          "

      - name: Upload rescore report
        uses: actions/upload-artifact@v4
        with:
          name: rescore-report
          path: logs/rescore_report_*.json
          retention-days: 30
```

---

### Task 5: 信息抽取双轨制

#### 5.1 创建传统解析器

**新文件**: `src/collectors/fallback_extractor.py`

```python
"""传统解析器 - 作为LLM抽取的校验"""
from __future__ import annotations

import re
import logging
from typing import Optional, Dict
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

class FallbackExtractor:
    """规则解析器（传统方法）"""

    @staticmethod
    async def extract_arxiv_metadata(arxiv_url: str) -> Dict[str, Optional[str]]:
        """从arXiv URL提取元数据"""
        # 提取arXiv ID
        match = re.search(r"arxiv\.org/abs/(\d+\.\d+)", arxiv_url)
        if not match:
            return {}

        arxiv_id = match.group(1)

        # 调用arXiv API
        api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(api_url, timeout=10)
            soup = BeautifulSoup(resp.text, "xml")

            entry = soup.find("entry")
            if not entry:
                return {}

            return {
                "title": entry.find("title").text.strip() if entry.find("title") else None,
                "abstract": entry.find("summary").text.strip() if entry.find("summary") else None,
                "published_date": entry.find("published").text[:10] if entry.find("published") else None,
                "authors": [
                    author.find("name").text
                    for author in entry.find_all("author")
                ] if entry.find_all("author") else None
            }

    @staticmethod
    async def extract_github_metadata(github_url: str) -> Dict[str, Optional[str]]:
        """从GitHub URL提取元数据"""
        # 提取owner/repo
        match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)
        if not match:
            return {}

        owner, repo = match.groups()

        # 调用GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github+json"},
                timeout=10
            )

            if resp.status_code != 200:
                return {}

            data = resp.json()

            return {
                "title": data.get("full_name"),
                "abstract": data.get("description"),
                "stars": data.get("stargazers_count"),
                "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
                "updated_at": data.get("updated_at", "")[:10]
            }

class ConsistencyChecker:
    """一致性检查器"""

    @staticmethod
    def check_consistency(
        llm_extracted: Dict,
        fallback_extracted: Dict,
        threshold: float = 0.8
    ) -> Dict[str, bool]:
        """检查LLM抽取与传统抽取的一致性"""
        results = {}

        # 标题一致性（使用编辑距离）
        if "title" in llm_extracted and "title" in fallback_extracted:
            similarity = ConsistencyChecker._string_similarity(
                llm_extracted["title"],
                fallback_extracted["title"]
            )
            results["title_consistent"] = similarity >= threshold

        # 日期一致性（精确匹配）
        if "published_date" in llm_extracted and "published_date" in fallback_extracted:
            results["date_consistent"] = (
                llm_extracted["published_date"] == fallback_extracted["published_date"]
            )

        # Stars一致性（误差<10%）
        if "stars" in llm_extracted and "stars" in fallback_extracted:
            llm_stars = int(llm_extracted.get("stars", 0) or 0)
            fb_stars = int(fallback_extracted.get("stars", 0) or 0)

            if fb_stars > 0:
                error_rate = abs(llm_stars - fb_stars) / fb_stars
                results["stars_consistent"] = error_rate < 0.1

        return results

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """计算字符串相似度（简化版Levenshtein）"""
        if not s1 or not s2:
            return 0.0

        # 简化：计算共同词汇占比
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0
```

#### 5.2 集成到采集流程

**文件**: `src/collectors/arxiv_collector.py`

在采集后增加一致性校验：

```python
async def collect_with_validation(self) -> List[RawCandidate]:
    """采集 + 一致性校验"""
    from src.collectors.fallback_extractor import FallbackExtractor, ConsistencyChecker

    # 1. 原有采集流程
    candidates = await self.collect()

    # 2. 对前10个候选进行一致性校验
    validated = []
    extractor = FallbackExtractor()
    checker = ConsistencyChecker()

    for candidate in candidates[:10]:
        # LLM已抽取的数据
        llm_data = {
            "title": candidate.title,
            "abstract": candidate.abstract,
            "published_date": candidate.publish_date
        }

        # 传统方法抽取
        fallback_data = await extractor.extract_arxiv_metadata(candidate.url)

        # 一致性检查
        consistency = checker.check_consistency(llm_data, fallback_data)

        if all(consistency.values()):
            validated.append(candidate)
        else:
            logger.warning(
                f"⚠️ 一致性检查失败: {candidate.title[:50]}\n"
                f"不一致字段: {[k for k, v in consistency.items() if not v]}"
            )

    logger.info(f"一致性验证: {len(validated)}/{len(candidates[:10])} 通过")

    return candidates  # 返回全部，但记录不一致的
```

---

## 四、飞书表格字段更新

### 4.1 新增字段清单

在飞书多维表格中新增以下字段（执行脚本 `scripts/create_feishu_fields_v2.py`）：

**能力域字段** (5个):
- `planning_score` (数字，0-10)
- `tool_use_score` (数字，0-10)
- `memory_score` (数字，0-10)
- `collaboration_score` (数字，0-10)
- `reasoning_score` (数字，0-10)

**风险域字段** (5个):
- `security_score` (数字，0-10)
- `robustness_score` (数字，0-10)
- `hallucination_risk` (数字，0-10)
- `compliance_score` (数字，0-10)
- `risk_level` (单选：safe/moderate/high/critical)

**元数据字段** (3个):
- `capability_total` (数字，能力域总分)
- `risk_total` (数字，风险域总分)
- `operational_total` (数字，运营域总分)
- `last_evaluated_at` (日期时间)
- `evaluation_version` (文本，如"v2.0")

### 4.2 飞书通知卡片更新

**文件**: `src/notifier/feishu_notifier.py`

更新卡片内容，展示三域评分：

```python
def _build_card(self, title: str, candidate: ScoredCandidate) -> dict:
    """构建高优先级候选卡片 - 三域评分版"""

    content = (
        f"**{candidate.title[:constants.TITLE_TRUNCATE_LONG]}**\n\n"
        f"综合评分: **{candidate.total_score:.1f}** / 10  |  "
        f"优先级: **{priority_label}**  |  "
        f"风险: **{candidate.risk_level}**\n\n"

        "**能力域** (总分: {candidate.capability_total:.1f})\n"
        f"规划 {candidate.capability_scores.planning_score:.1f}  |  "
        f"工具 {candidate.capability_scores.tool_use_score:.1f}  |  "
        f"记忆 {candidate.capability_scores.memory_score:.1f}  |  "
        f"协作 {candidate.capability_scores.collaboration_score:.1f}  |  "
        f"推理 {candidate.capability_scores.reasoning_score:.1f}\n\n"

        "**风险域** (总分: {candidate.risk_total:.1f})\n"
        f"安全 {candidate.risk_scores.security_score:.1f}  |  "
        f"鲁棒 {candidate.risk_scores.robustness_score:.1f}  |  "
        f"幻觉 {candidate.risk_scores.hallucination_risk:.1f}  |  "
        f"合规 {candidate.risk_scores.compliance_score:.1f}\n\n"

        "**运营域** (总分: {candidate.operational_total:.1f})\n"
        f"活跃 {candidate.operational_scores.activity_score:.1f}  |  "
        f"复现 {candidate.operational_scores.reproducibility_score:.1f}  |  "
        f"许可 {candidate.operational_scores.license_score:.1f}  |  "
        f"新颖 {candidate.operational_scores.novelty_score:.1f}  |  "
        f"适配 {candidate.operational_scores.relevance_score:.1f}\n\n"

        f"**来源**: {source_name}\n\n"
        f"**评分依据**\n{candidate.reasoning}"
    )

    # ... 其余卡片结构保持不变
```

---

## 五、测试与验收

### 5.1 单元测试

**新文件**: `tests/test_three_domain_scoring.py`

```python
"""三域评分测试"""
import pytest
from src.scorer.llm_scorer import LLMScorer
from src.models import RawCandidate

@pytest.mark.asyncio
async def test_three_domain_scoring():
    """测试三域评分功能"""
    scorer = LLMScorer()

    # 创建测试候选
    candidate = RawCandidate(
        title="WebArena: A Realistic Web Environment for Building Autonomous Agents",
        url="https://arxiv.org/abs/2307.13854",
        source="arxiv",
        abstract="A benchmark for web-based agent tasks..."
    )

    async with scorer:
        scored = await scorer.score(candidate)

    # 验证三域评分存在
    assert scored.capability_scores is not None
    assert scored.risk_scores is not None
    assert scored.operational_scores is not None

    # 验证总分计算
    assert scored.capability_total > 0
    assert scored.risk_total > 0
    assert scored.operational_total > 0

    # 验证风险等级
    assert scored.risk_level in ["safe", "moderate", "high", "critical"]

    # 验证优先级
    assert scored.priority in ["high", "medium", "low"]
```

### 5.2 集成测试

**测试步骤**:

1. **运行完整流程**:
```bash
uv run python src/main.py
```

2. **检查飞书表格**:
- 验证新增的能力域/风险域字段是否正确填充
- 确认 `risk_level` 和 `evaluation_version` 字段

3. **验证安全回路**:
```bash
uv run python -c "
import asyncio
from src.scorer.security_validator import SecurityValidator
from src.models import ScoredCandidate

async def test():
    validator = SecurityValidator()
    # 创建测试候选...
    is_safe, warnings = await validator.validate_candidate(candidate)
    print(f'安全: {is_safe}, 警告: {warnings}')

asyncio.run(test())
"
```

4. **验证复测调度**:
```bash
# 手动触发复测
uv run python -c "
import asyncio
from src.tracker.rescore_scheduler import RescoreScheduler

asyncio.run(RescoreScheduler().run_rescore())
"
```

### 5.3 验��标准

✅ **功能验收**:
- [ ] 三域评分正确计算（能力/风险/运营）
- [ ] 风险等级正确判定（safe/moderate/high/critical）
- [ ] 安全验证器能识别5类常见漏洞
- [ ] 复测调度器每14天自动运行
- [ ] 信息抽取一致性检查通过率>80%

✅ **性能验收**:
- [ ] LLM评分时间<10秒/候选（max_tokens=1600）
- [ ] 安全验证增加的开销<20%
- [ ] 复测任务完成时间<30分钟（100个候选）

✅ **数据验收**:
- [ ] 飞书表格新增字段全部正确创建
- [ ] 飞书通知卡片正确展示三域评分
- [ ] reasoning字段平均长度>500字（vs 旧版200字）

---

## 六、注意事项

### ⚠️ 重要约束

1. **向后兼容**: 旧的5维评分模型（v1.0）仍需支持，新模型标记为v2.0
2. **成本控制**: 三域评分token消耗增加~3倍，需监控OpenAI费用
3. **测试优先**: 所有新模块必须先在测试数据上验证，再上线生产
4. **飞书字段**: 在创建新字段前，先在测试表格验证，避免污染生产数据

### 📋 实施顺序

**Phase 7.1** (Week 1-2):
1. Task 1: 重构评分模型（数据模型 + LLM prompt + 计算逻辑）
2. Task 5: 信息抽取双轨制（先实现，用于校验新评分准确性）

**Phase 7.2** (Week 3):
3. Task 3: 安全/可控回路（基于新评分模型）
4. 飞书字段更新 + 通知卡片改版

**Phase 7.3** (Week 4):
5. Task 4: 持续学习校验（复测调度器）
6. Task 2: 自进化样本池（长期运行）

**Phase 7.4** (Week 5):
7. 全面测试 + 性能优化
8. 文档更新 + 上线部署

---

## 七、参考文献

1. arXiv 2503.16416 - Agent评测综述
2. arXiv 2502.15865 - 金融Agent风险评估
3. arXiv 2506.15253 - RAS-Eval安全评测
4. arXiv 2505.11942 - LifelongAgentBench
5. aclanthology.org/2025.coling-main.223 - Benchmark Self-Evolving
6. scisimple.com - GPT-4科学信息抽取评估

---

**Codex，请严格按照本文档实施Phase 7改进。遇到不明确的地方，先询问再动手。记得单元测试先行，手动测试必做。**
