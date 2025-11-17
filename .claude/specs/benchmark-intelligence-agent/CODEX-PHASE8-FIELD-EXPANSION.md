# Phase 8: 5字段扩展 - Codex开发指令

**创建时间**: 2025-11-16
**优先级**: P0（紧急 - 修复Phase 7评分问题）
**预计工期**: 2-3天
**开发者**: Codex

---

## 1. 背景与目标

### 1.1 Phase 7验收发现的问题

Phase 7完整流程验收结果：
- ✅ 采集优化达标：90条总量，HELM 14条（目标≤20），GitHub恢复正常
- ❌ **评分严重偏低**：平均分4.36/10（目标≥6.5），高优先级命中率0%（目标≥20%）
- ⚠️ 预筛选过滤率9.1%（目标20-60%，但为保留GitHub数据做的妥协）

**根本原因**：
1. LLM评分信息不足：仅有标题、摘要、URL，缺乏Benchmark核心特征
2. MGX适配度评分偏低（仅4.08/10）：无法判断任务类型是否符合MGX场景
3. 可复现性评分不准确：无法识别是否提供了Metrics、Baseline、数据集

### 1.2 Phase 8目标

**核心目标**：通过新增5个字段，提升LLM评分准确性，将平均分从4.36提升至6.5+，高优先级命中率提升至20%+

**新增字段**：
1. **任务领域** (Task Domain): Coding / DeepResearch / Reasoning / ToolUse / Collaboration / WebDev / GUI（可进一步细化）
2. **评估指标** (Metrics): 从论文/README中提取评估指标和口径（如Pass@1, BLEU, F1-Score）
3. **基准模型** (Baseline): Benchmark验证过的baseline模型或框架名称（如GPT-4, Claude-3.5-Sonnet）
4. **机构和作者** (Institution & Authors): 研究机构、作者信息（如Stanford, OpenAI）
5. **数据集样本数量** (Dataset Sample Size): 数据集规模（如1000 samples, 500 test cases）

---

## 2. 技术方案

### 2.1 数据模型修改

#### 2.1.1 RawCandidate 模型（src/models.py）

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class RawCandidate:
    """原始候选数据模型"""

    title: str
    url: str
    source: str
    abstract: Optional[str] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    license_type: Optional[str] = None

    # Phase 8新增字段（采集器层级提取）
    task_type: Optional[str] = None  # 已有字段，保留

    # Phase 8新增：从README/论文中初步提取的信息（后续LLM精炼）
    raw_metrics: Optional[List[str]] = None  # 原始指标列表
    raw_baselines: Optional[List[str]] = None  # 原始baseline列表
    raw_authors: Optional[str] = None  # 原始作者信息
    raw_institutions: Optional[str] = None  # 原始机构信息
    raw_dataset_size: Optional[str] = None  # 原始数据集规模描述

    raw_metadata: Dict[str, str] = field(default_factory=dict)
```

#### 2.1.2 ScoredCandidate 模型（src/models.py）

```python
@dataclass
class ScoredCandidate:
    """评分后的候选数据模型"""

    # 基础字段（已有）
    title: str
    url: str
    source: str
    abstract: Optional[str] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    license_type: Optional[str] = None
    task_type: Optional[str] = None

    # 5维评分（已有）
    activity_score: float = 0.0
    reproducibility_score: float = 0.0
    license_score: float = 0.0
    novelty_score: float = 0.0
    relevance_score: float = 0.0
    total_score: float = 0.0
    priority: str = "low"
    score_reasoning: Optional[str] = None

    # Phase 8新增：LLM精炼后的结构化字段
    task_domain: Optional[str] = None  # Coding | DeepResearch | Reasoning | ToolUse | Collaboration | WebDev | GUI
    metrics: Optional[List[str]] = None  # ["Pass@1", "BLEU", "F1-Score"]
    baselines: Optional[List[str]] = None  # ["GPT-4", "Claude-3.5-Sonnet", "Llama-3.1-70B"]
    institution: Optional[str] = None  # "Stanford University"
    authors: Optional[List[str]] = None  # ["John Doe", "Jane Smith"]
    dataset_size: Optional[int] = None  # 1000（统一为数字）
    dataset_size_description: Optional[str] = None  # "1000 coding problems"（原始描述）
```

---

### 2.2 采集器层优化（初步提取）

**目标**：在采集阶段从README/论文摘要中粗提取信息，减轻LLM负担

#### 2.2.1 GitHub Collector 优化（src/collectors/github_collector.py）

**新增方法**：`_extract_raw_metadata(readme_text: str) -> Dict[str, Any]`

```python
@staticmethod
def _extract_raw_metadata(readme_text: str) -> Dict[str, Any]:
    """从GitHub README中粗提取元数据（规则+正则）"""

    text_lower = readme_text.lower()
    metadata = {
        "raw_metrics": [],
        "raw_baselines": [],
        "raw_dataset_size": None,
    }

    # 1. 提取常见Metrics关键词
    metric_patterns = [
        r'pass@\d+',  # Pass@1, Pass@5
        r'bleu[-\s]?\d*',  # BLEU, BLEU-4
        r'rouge[-\s]?[lf\d]*',  # ROUGE-L, ROUGE-1
        r'f1[-\s]?score',  # F1-Score
        r'accuracy',
        r'precision',
        r'recall',
        r'exact\s+match',
        r'code\s+pass\s+rate',
    ]

    for pattern in metric_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            metric = match.group().strip()
            if metric and metric not in metadata["raw_metrics"]:
                metadata["raw_metrics"].append(metric)

    # 2. 提取Baseline模型名称
    baseline_patterns = [
        r'gpt-?[34](?:-turbo|-o)?',
        r'claude[-\s]?(?:3\.?5?|2|opus|sonnet)',
        r'llama[-\s]?[23]?\.?\d*[-\s]?\d*[bm]?',
        r'codex',
        r'starcoder',
        r'code\s?llama',
        r'mistral',
        r'deepseek',
    ]

    for pattern in baseline_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            baseline = match.group().strip()
            if baseline and baseline not in metadata["raw_baselines"]:
                metadata["raw_baselines"].append(baseline)

    # 3. 提取数据集规模描述
    size_patterns = [
        r'\d+[,\s]*(?:k|thousand|samples?|problems?|questions?|tasks?|examples?|test\s+cases?)',
        r'(?:contains?|includes?|consists?\s+of)\s+\d+[,\s]*\w+',
    ]

    for pattern in size_patterns:
        match = re.search(pattern, text_lower)
        if match:
            metadata["raw_dataset_size"] = match.group().strip()
            break  # 只取第一个匹配

    return metadata
```

**修改位置**：`_build_candidate()` 方法，在返回RawCandidate前调用：

```python
async def _build_candidate(
    self,
    client: httpx.AsyncClient,
    repo: Dict[str, Any],
    topic: str,
) -> Optional[RawCandidate]:
    """拉取README并根据白/黑名单判断是否为Benchmark"""

    # ... 现有逻辑 ...

    # Phase 8新增：粗提取元数据
    raw_meta = self._extract_raw_metadata(readme_text)

    return RawCandidate(
        title=repo.get("full_name", ""),
        url=repo.get("html_url", ""),
        source="github",
        abstract=readme_text,
        github_stars=stars,
        github_url=repo.get("html_url"),
        publish_date=self._parse_datetime(repo.get("pushed_at")),
        license_type=license_type,
        task_type=task_type,
        # Phase 8新增
        raw_metrics=raw_meta.get("raw_metrics"),
        raw_baselines=raw_meta.get("raw_baselines"),
        raw_dataset_size=raw_meta.get("raw_dataset_size"),
        raw_metadata={
            "topic": topic,
            "language": repo.get("language"),
        },
    )
```

#### 2.2.2 arXiv Collector 优化（src/collectors/arxiv_collector.py）

**新增方法**：`_extract_authors_institutions(result: Dict) -> Tuple[str, str]`

```python
@staticmethod
def _extract_authors_institutions(result: Dict) -> Tuple[Optional[str], Optional[str]]:
    """从arXiv结果中提取作者和机构信息"""

    authors = []
    institutions = set()

    # arXiv API返回authors列表
    for author in result.get("authors", []):
        name = author.get("name", "").strip()
        if name:
            authors.append(name)

        # 部分arXiv结果包含affiliation
        affiliation = author.get("affiliation", {}).get("name", "").strip()
        if affiliation:
            institutions.add(affiliation)

    authors_str = ", ".join(authors[:5]) if authors else None  # 最多保留前5位作者
    institutions_str = ", ".join(sorted(institutions)) if institutions else None

    return authors_str, institutions_str
```

**修改位置**：`_parse_entry()` 方法：

```python
def _parse_entry(self, result: Dict) -> RawCandidate:
    """解析单个arXiv条目"""

    # ... 现有逻辑 ...

    # Phase 8新增：提取作者和机构
    raw_authors, raw_institutions = self._extract_authors_institutions(result)

    return RawCandidate(
        title=title,
        url=entry_id,
        source="arxiv",
        abstract=summary,
        publish_date=published_datetime,
        # Phase 8新增
        raw_authors=raw_authors,
        raw_institutions=raw_institutions,
        raw_metadata={
            "arxiv_id": arxiv_id,
            "categories": categories,
        },
    )
```

---

### 2.3 LLM评分器优化（核心修改）

#### 2.3.1 优化评分Prompt（src/scorer/llm_scorer.py）

**关键修改**：
1. 增加5个新字段的提取指令
2. 优化MGX适配度评分逻辑（明确任务领域权重）
3. 增加可复现性评分依据（Metrics、Baseline、数据集）

**新增Pydantic模型**：

```python
from pydantic import BaseModel, Field
from typing import List, Optional


class BenchmarkExtraction(BaseModel):
    """Benchmark信息提取结果（Phase 8扩展）"""

    # 5维评分（已有）
    activity_score: float = Field(..., ge=0, le=10, description="活跃度评分 0-10")
    reproducibility_score: float = Field(..., ge=0, le=10, description="可复现性评分 0-10")
    license_score: float = Field(..., ge=0, le=10, description="许可合规评分 0-10")
    novelty_score: float = Field(..., ge=0, le=10, description="新颖性评分 0-10")
    relevance_score: float = Field(..., ge=0, le=10, description="MGX适配度评分 0-10")

    score_reasoning: str = Field(..., description="评分依据（100-200字）")

    # Phase 8新增字段
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

**优化后的评分Prompt**：

```python
SCORING_PROMPT_TEMPLATE = """你是BenchScope系统的Benchmark评估专家。请根据以下信息对候选Benchmark进行5维评分并提取关键字段。

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

1. **活跃度** (0-10分，权重15%)
   - GitHub Stars数量（10: >1000, 8: 500-1000, 6: 100-500, 4: 50-100, 2: 10-50, 0: <10或无数据）
   - 最近更新时间（近3个月+2分，近6个月+1分，超过1年-2分）
   - 社区活跃度（有PR/Issue讨论+1分）

2. **可复现性** (0-10分，权重30%)
   - **数据集开源**（10分: 完全开源+公开下载链接, 7分: 开源但需申请, 4分: 仅示例数据, 0分: 闭源）
   - **代码开源**（+3分: 完整评估脚本, +2分: 部分代码, +1分: 仅示例）
   - **评估指标明确**（+2分: 提供详细Metrics定义和计算方法）
   - **Baseline可验证**（+2分: 提供主流模型评测结果）
   - **文档完整**（+1分: 有详细README/论文）

3. **许可合规** (0-10分，权重15%)
   - 10分: MIT/Apache-2.0/BSD（完全开放）
   - 7分: GPL系列（传染性开源）
   - 4分: CC-BY（学术使用）
   - 0分: 专有许可或无许可证

4. **新颖性** (0-10分，权重15%)
   - 任务创新性（10分: 全新任务, 7分: 现有任务新角度, 4分: 改进现有Benchmark, 2分: 数据扩充）
   - 评估方法创新（+2分: 新颖的评估指标）
   - 时间性（2024-2025年+2分，2023年+1分，2022年及更早0分）

5. **MGX适配度** (0-10分，权重25% - **Phase 8重点提升**)
   - **任务领域匹配度**（按优先级）：
     * 10分: P0领域（Coding/WebDev/GUI）直接适用
     * 8分: P1领域（ToolUse/Collaboration）高度相关
     * 6分: P2领域（Reasoning/DeepResearch）中度相关
     * 3分: 其他领域（NLP/CV/语音）但有可迁移性
     * 0分: 完全不相关（纯NLP分类/图像识别等）

   - **任务类型细化**（额外加分）：
     * Coding细分: +2分代码生成, +1分代码理解/补全
     * WebDev细分: +2分浏览器自动化, +1分Web爬虫/测试
     * GUI细分: +2分跨平台GUI操作, +1分特定平台
     * ToolUse细分: +2分复杂API调用链, +1分单一API调用
     * Collaboration细分: +2分多智能体协作, +1分单智能体规划

   - **评估维度匹配**：
     * +1分: 评估代码正确性（Pass@k, 功能测试）
     * +1分: 评估执行效率（时间/步数/成本）
     * +1分: 评估真实场景表现（非synthetic数据）

---

【字段提取指令】

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

2. **metrics**（评估指标）
   - 从摘要/README中提取评估指标，格式统一为：
     * Pass@1, Pass@5, Pass@10（代码通过率）
     * BLEU, ROUGE-L（文本相似度）
     * Exact Match, F1-Score（匹配度）
     * Success Rate, Completion Rate（成功率）
     * Accuracy, Precision, Recall（分类指标）
   - 最多提取5个主要指标
   - 如果摘要中未明确提及，可根据任务类型推断常用指标（标注"推断"）

3. **baselines**（基准模型）
   - 从摘要/README中提取已验证的基准模型，统一命名：
     * GPT-4, GPT-4-Turbo, GPT-3.5-Turbo（OpenAI系列）
     * Claude-3.5-Sonnet, Claude-3-Opus（Anthropic系列）
     * Llama-3.1-70B, Llama-2-13B（Meta系列）
     * Mistral-7B, DeepSeek-Coder（开源系列）
     * Codex, StarCoder, CodeLlama（代码专用）
   - 最多提取5个主流模型
   - 优先提取论文中明确提及的模型

4. **institution**（机构）
   - 优先提取第一作者或通讯作者的单位
   - 统一命名：Stanford University, MIT, OpenAI, Google DeepMind, Meta AI
   - 如果有多个机构，选择最知名的一个

5. **authors**（作者）
   - 提取前5位作者，格式：["FirstName LastName", ...]
   - 如果摘要中无作者信息，可从GitHub仓库owner或论文作者推断

6. **dataset_size**（数据集规模）
   - 从描述中提取数字并统一为整数（如"1k samples" → 1000）
   - 如果是范围（如"500-1000 problems"），取平均值（750）
   - 常见单位换算：k=1000, M=1000000

7. **dataset_size_description**（数据集规模描述）
   - 保留原始描述，如"1000 coding problems", "500 test cases", "10k web tasks"

---

【评分输出要求】

1. 每个维度必须给出0-10的分数，允许小数点后1位
2. score_reasoning字段必须说明：
   - 总分如何计算（各维度得分*权重）
   - 为何给出该MGX适配度评分（匹配哪个优先级领域）
   - 为何给出该可复现性评分（是否开源数据/代码/Metrics）
   - 是否推荐纳入MGX Benchmark池（总分≥6.5 + 适配度≥7推荐）
3. 字数控制在100-200字

---

【输出格式】
请严格按照BenchmarkExtraction模型返回JSON格式结果。
"""
```

#### 2.3.2 修改 `_score_single()` 方法

```python
async def _score_single(self, candidate: RawCandidate) -> ScoredCandidate:
    """使用LLM评分单个候选并提取Phase 8新字段"""

    # 构造Prompt
    prompt = SCORING_PROMPT_TEMPLATE.format(
        title=candidate.title,
        source=candidate.source,
        abstract=(candidate.abstract or "")[:2000],  # 限制长度
        github_stars=candidate.github_stars or "无数据",
        license_type=candidate.license_type or "未知",
        task_type=candidate.task_type or "未识别",
        # Phase 8新增
        raw_metrics=candidate.raw_metrics or "未提取",
        raw_baselines=candidate.raw_baselines or "未提取",
        raw_authors=candidate.raw_authors or "未提取",
        raw_institutions=candidate.raw_institutions or "未提取",
        raw_dataset_size=candidate.raw_dataset_size or "未提取",
    )

    # 调用LLM（使用structured output）
    try:
        extraction = await self._call_llm_with_structure(
            prompt=prompt,
            response_model=BenchmarkExtraction
        )

        # 计算总分（加权平均）
        total_score = (
            extraction.activity_score * SCORE_WEIGHTS["activity"]
            + extraction.reproducibility_score * SCORE_WEIGHTS["reproducibility"]
            + extraction.license_score * SCORE_WEIGHTS["license"]
            + extraction.novelty_score * SCORE_WEIGHTS["novelty"]
            + extraction.relevance_score * SCORE_WEIGHTS["relevance"]
        )

        # 计算优先级
        priority = self._calculate_priority(total_score, extraction.relevance_score)

        return ScoredCandidate(
            # 基础字段
            title=candidate.title,
            url=candidate.url,
            source=candidate.source,
            abstract=candidate.abstract,
            publish_date=candidate.publish_date,
            github_stars=candidate.github_stars,
            github_url=candidate.github_url,
            license_type=candidate.license_type,
            task_type=candidate.task_type,

            # 5维评分
            activity_score=extraction.activity_score,
            reproducibility_score=extraction.reproducibility_score,
            license_score=extraction.license_score,
            novelty_score=extraction.novelty_score,
            relevance_score=extraction.relevance_score,
            total_score=total_score,
            priority=priority,
            score_reasoning=extraction.score_reasoning,

            # Phase 8新增字段
            task_domain=extraction.task_domain,
            metrics=extraction.metrics,
            baselines=extraction.baselines,
            institution=extraction.institution,
            authors=extraction.authors,
            dataset_size=extraction.dataset_size,
            dataset_size_description=extraction.dataset_size_description,
        )

    except Exception as e:
        logger.warning(f"LLM评分失败: {e}，回退到规则评分")
        return self._fallback_rule_score(candidate)
```

#### 2.3.3 新增LLM调用方法（structured output）

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

---

### 2.4 飞书存储层修改

#### 2.4.1 新增字段映射（src/storage/feishu_storage.py）

```python
class FeishuStorage:
    """飞书Bitable存储实现"""

    # Phase 8扩展字段映射
    FIELD_MAPPING = {
        # 基础字段（已有）
        "title": "标题",
        "url": "URL",
        "source": "来源",
        "abstract": "摘要",
        # ... 其他已有字段 ...

        # Phase 8新增字段
        "task_domain": "任务领域",  # 多选字段
        "metrics": "评估指标",  # 多行文本（JSON数组转换为逗号分隔）
        "baselines": "基准模型",  # 多行文本（JSON数组转换为逗号分隔）
        "institution": "机构",  # 单行文本
        "authors": "作者",  # 多行文本（JSON数组转换为逗号分隔）
        "dataset_size": "数据集规模",  # 数字字段
        "dataset_size_description": "数据集规模描述",  # 单行文本
    }
```

#### 2.4.2 修改 `_to_feishu_record()` 方法

```python
def _to_feishu_record(self, candidate: ScoredCandidate) -> dict:
    """转换为飞书Bitable记录格式（Phase 8扩展）"""

    fields = {
        # 基础字段（已有）
        self.FIELD_MAPPING["title"]: candidate.title,
        self.FIELD_MAPPING["url"]: {
            "link": candidate.url,
            "text": candidate.title[:50],
        },
        self.FIELD_MAPPING["source"]: self._format_source_name(candidate.source),
        self.FIELD_MAPPING["abstract"]: self._clean_abstract(candidate.abstract),

        # 5维评分（已有）
        self.FIELD_MAPPING["activity_score"]: candidate.activity_score,
        self.FIELD_MAPPING["reproducibility_score"]: candidate.reproducibility_score,
        self.FIELD_MAPPING["license_score"]: candidate.license_score,
        self.FIELD_MAPPING["novelty_score"]: candidate.novelty_score,
        self.FIELD_MAPPING["relevance_score"]: candidate.relevance_score,
        self.FIELD_MAPPING["total_score"]: candidate.total_score,
        self.FIELD_MAPPING["priority"]: candidate.priority,
        self.FIELD_MAPPING["score_reasoning"]: candidate.score_reasoning[:1500] if candidate.score_reasoning else "",

        # Phase 8新增字段
        self.FIELD_MAPPING["task_domain"]: candidate.task_domain if candidate.task_domain else "",

        self.FIELD_MAPPING["metrics"]: ", ".join(candidate.metrics) if candidate.metrics else "",

        self.FIELD_MAPPING["baselines"]: ", ".join(candidate.baselines) if candidate.baselines else "",

        self.FIELD_MAPPING["institution"]: candidate.institution if candidate.institution else "",

        self.FIELD_MAPPING["authors"]: ", ".join(candidate.authors) if candidate.authors else "",

        self.FIELD_MAPPING["dataset_size"]: candidate.dataset_size if candidate.dataset_size else 0,

        self.FIELD_MAPPING["dataset_size_description"]: candidate.dataset_size_description if candidate.dataset_size_description else "",
    }

    # ... 其他已有字段处理逻辑 ...

    return {"fields": fields}
```

---

## 3. 实施步骤

### Step 1: 数据模型修改（1小时）

1. 修改 `src/models.py`：
   - 在RawCandidate中新增raw_*字段（6个）
   - 在ScoredCandidate中新增精炼字段（7个）

2. 运行单元测试确认无Breaking Change：
   ```bash
   PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_models.py -v
   ```

### Step 2: 采集器优化（3小时）

1. 修改 `src/collectors/github_collector.py`：
   - 新增 `_extract_raw_metadata()` 方法（80行）
   - 修改 `_build_candidate()` 调用新方法

2. 修改 `src/collectors/arxiv_collector.py`：
   - 新增 `_extract_authors_institutions()` 方法（30行）
   - 修改 `_parse_entry()` 调用新方法

3. 运行采集器单元测试：
   ```bash
   PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_collectors.py -v
   ```

### Step 3: LLM评分器核心改造（5小时）

1. 修改 `src/scorer/llm_scorer.py`：
   - 新增 `BenchmarkExtraction` Pydantic模型（60行）
   - 重写 `SCORING_PROMPT_TEMPLATE`（150行）
   - 新增 `_call_llm_with_structure()` 方法（30行）
   - 修改 `_score_single()` 方法（50行）

2. 运行评分器单元测试：
   ```bash
   PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_scorer.py -v
   ```

### Step 4: 飞书存储层修改（2小时）

1. **前置步骤：手动创建飞书表格字段**（⚠️ 必须先执行）

   登录飞书多维表格，手动添加以下7个字段：

   | 字段名 | 字段类型 | 说明 |
   |--------|----------|------|
   | 任务领域 | 多选 | 选项：Coding, DeepResearch, Reasoning, ToolUse, Collaboration, WebDev, GUI, Other |
   | 评估指标 | 多行文本 | 存储逗号分隔的指标列表 |
   | 基准模型 | 多行文本 | 存储逗号分隔的模型列表 |
   | 机构 | 单行文本 | 主要研究机构 |
   | 作者 | 多行文本 | 存储逗号分隔的作者列表 |
   | 数据集规模 | 数字 | 样本数量（整数） |
   | 数据集规模描述 | 单行文本 | 原始描述文本 |

2. 修改 `src/storage/feishu_storage.py`：
   - 扩展 `FIELD_MAPPING`（新增7个字段）
   - 修改 `_to_feishu_record()` 方法

3. 运行存储层单元测试：
   ```bash
   PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_storage.py -v
   ```

### Step 5: 集成测试（2小时）

1. 创建测试脚本 `scripts/test_phase8_integration.py`：
   ```python
   """Phase 8集成测试：端到端验证新字段提取"""
   import asyncio
   from src.collectors import ArxivCollector, GitHubCollector
   from src.scorer import LLMScorer

   async def test_phase8_integration():
       # 1. 采集少量样本
       arxiv_collector = ArxivCollector()
       github_collector = GitHubCollector()

       arxiv_candidates = await arxiv_collector.collect()
       github_candidates = await github_collector.collect()

       test_candidates = (arxiv_candidates[:5] + github_candidates[:5])

       # 2. LLM评分
       async with LLMScorer() as scorer:
           scored = await scorer.score_batch(test_candidates)

       # 3. 验证新字段是否被正确提取
       for candidate in scored:
           print(f"\n标题: {candidate.title[:60]}")
           print(f"任务领域: {candidate.task_domain}")
           print(f"评估指标: {candidate.metrics}")
           print(f"基准模型: {candidate.baselines}")
           print(f"机构: {candidate.institution}")
           print(f"作者: {candidate.authors}")
           print(f"数据集规模: {candidate.dataset_size} ({candidate.dataset_size_description})")
           print(f"MGX适配度: {candidate.relevance_score}/10")
           print(f"总分: {candidate.total_score}/10")

           # 验证关键字段非空
           assert candidate.task_domain is not None, "task_domain不应为空"
           assert candidate.relevance_score >= 0, "relevance_score必须≥0"

   if __name__ == "__main__":
       asyncio.run(test_phase8_integration())
   ```

2. 运行集成测试：
   ```bash
   PYTHONPATH=. .venv/bin/python scripts/test_phase8_integration.py
   ```

### Step 6: 完整流程验收（3小时）

1. 运行3次完整main.py流程：
   ```bash
   PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_run1.log
   PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_run2.log
   PYTHONPATH=. .venv/bin/python src/main.py 2>&1 | tee logs/phase8_run3.log
   ```

2. 分析评分改善效果：
   ```bash
   PYTHONPATH=. .venv/bin/python scripts/analyze_phase8_scores.py
   ```

3. 检查飞书表格新字段是否正确写入

---

## 4. 测试用例

### 4.1 单元测试

#### test_models.py（新增）

```python
"""测试Phase 8新增数据模型字段"""

def test_raw_candidate_phase8_fields():
    """测试RawCandidate新字段"""
    candidate = RawCandidate(
        title="Test Benchmark",
        url="https://example.com",
        source="github",
        raw_metrics=["Pass@1", "BLEU"],
        raw_baselines=["GPT-4", "Claude-3.5-Sonnet"],
        raw_dataset_size="1000 samples",
    )

    assert candidate.raw_metrics == ["Pass@1", "BLEU"]
    assert candidate.raw_baselines == ["GPT-4", "Claude-3.5-Sonnet"]
    assert candidate.raw_dataset_size == "1000 samples"


def test_scored_candidate_phase8_fields():
    """测试ScoredCandidate新字段"""
    candidate = ScoredCandidate(
        title="Test Benchmark",
        url="https://example.com",
        source="github",
        task_domain="Coding, WebDev",
        metrics=["Pass@1", "Success Rate"],
        baselines=["GPT-4"],
        institution="Stanford University",
        authors=["John Doe", "Jane Smith"],
        dataset_size=1000,
        dataset_size_description="1000 coding problems",
        total_score=7.5,
    )

    assert candidate.task_domain == "Coding, WebDev"
    assert len(candidate.metrics) == 2
    assert candidate.dataset_size == 1000
```

#### test_github_collector.py（新增）

```python
"""测试GitHub Collector新增的元数据提取"""

def test_extract_raw_metadata():
    """测试README元数据提取"""
    readme = """
    # CodeBench

    We evaluate models on Pass@1 and Pass@5 metrics.
    Baselines: GPT-4, Claude-3.5-Sonnet, Llama-3.1-70B.
    Dataset contains 1000 coding problems.
    """

    metadata = GitHubCollector._extract_raw_metadata(readme)

    assert "pass@1" in metadata["raw_metrics"]
    assert "pass@5" in metadata["raw_metrics"]
    assert any("gpt" in b.lower() for b in metadata["raw_baselines"])
    assert "1000" in metadata["raw_dataset_size"]
```

#### test_llm_scorer.py（新增）

```python
"""测试LLM评分器新增的字段提取"""

@pytest.mark.asyncio
async def test_benchmark_extraction_schema():
    """测试BenchmarkExtraction Pydantic模型"""

    test_data = {
        "activity_score": 7.5,
        "reproducibility_score": 8.0,
        "license_score": 10.0,
        "novelty_score": 6.0,
        "relevance_score": 9.0,
        "score_reasoning": "高质量Coding Benchmark，开源完整，MGX场景高度适配",
        "task_domain": "Coding, WebDev",
        "metrics": ["Pass@1", "Success Rate"],
        "baselines": ["GPT-4", "Claude-3.5-Sonnet"],
        "institution": "Stanford University",
        "authors": ["John Doe"],
        "dataset_size": 1000,
        "dataset_size_description": "1000 coding problems",
    }

    extraction = BenchmarkExtraction(**test_data)

    assert extraction.relevance_score == 9.0
    assert extraction.task_domain == "Coding, WebDev"
    assert extraction.dataset_size == 1000
```

---

## 5. 验收标准

### 5.1 功能验收

| 验收项 | 标准 | 验收方法 |
|--------|------|----------|
| **数据模型扩展** | RawCandidate新增6个字段，ScoredCandidate新增7个字段，无Breaking Change | 运行test_models.py，所有测试通过 |
| **GitHub元数据提取** | 能从README中提取≥3个Metrics，≥2个Baselines，数据集规模 | 运行test_github_collector.py，准确率≥80% |
| **arXiv作者提取** | 能提取前5位作者和机构信息 | 运行test_arxiv_collector.py，提取成功率≥90% |
| **LLM字段提取** | 7个新字段提取成功率≥80%（允许部分字段为空） | 运行集成测试，检查10个样本 |
| **飞书字段写入** | 新字段正确写入飞书表格，无数据丢失 | 手动检查飞书表格最新20条记录 |

### 5.2 性能验收

| 指标 | Phase 7实测 | Phase 8目标 | 验收方法 |
|------|-------------|------------|----------|
| **平均分** | 4.36/10 | ≥6.5/10 | 3次运行平均值 |
| **高优先级命中率** | 0% | ≥20% | 3次运行平均值 |
| **MGX适配度评分** | 平均4.08 | 平均≥7.0 | 分析最新60条记录 |
| **字段完整率** | 13/22（59%） | 20/22（91%） | 新增7个字段中至少5个非空 |
| **LLM调用成本** | 约¥0.50/run | <¥1.00/run | 记录OpenAI API消耗 |

### 5.3 回归验收

| 验收项 | 标准 | 验收方法 |
|--------|------|----------|
| **采集功能** | 采集总量保持40-100条，HELM≤20条 | 运行main.py，检查日志 |
| **预筛选功能** | 过滤率保持在合理范围（不要求20-60%） | 运行main.py，检查日志 |
| **飞书通知** | 高/中优先级正确推送，卡片格式正常 | 检查飞书群消息 |
| **单元测试** | 所有已有单元测试仍然通过 | 运行pytest tests/unit/ |

---

## 6. 风险与缓解

### 6.1 LLM提取不准确

**风险**：LLM可能误提取字段（如将作者名误识别为模型名）

**缓解**：
1. Prompt中提供明确的格式示例
2. 使用Pydantic强类型校验
3. 采集器层先做粗提取，LLM只做精炼
4. 对关键字段（task_domain）提供枚举选项

### 6.2 飞书字段映射错误

**风险**：新增字段名称与飞书表格不匹配导致写入失败

**缓解**：
1. 在Step 4前**必须先手动创建飞书字段**
2. 运行存储层单元测试验证映射
3. 集成测试阶段检查实际写入结果

### 6.3 评分Prompt过长

**风险**：新Prompt包含大量指令，可能超出context length或导致LLM困惑

**缓解**：
1. 将Prompt分段，用清晰的markdown标题
2. 评分维度说明保持简洁（每项≤5行）
3. 使用示例而非长篇解释

### 6.4 成本超支

**风险**：新Prompt更长，LLM调用成本可能翻倍

**缓解**：
1. 继续使用gpt-4o-mini（成本低）
2. Redis缓存策略不变
3. 限制abstract长度为2000字符
4. 监控每次运行的API消耗

---

## 7. 交付物清单

1. **源代码修改**（6个文件）
   - `src/models.py` - 数据模型扩展
   - `src/collectors/github_collector.py` - GitHub元数据提取
   - `src/collectors/arxiv_collector.py` - arXiv作者提取
   - `src/scorer/llm_scorer.py` - LLM评分Prompt重写 + 新字段提取
   - `src/storage/feishu_storage.py` - 飞书字段映射扩展
   - `src/common/constants.py` - 新增常量（如果需要）

2. **测试代码**（3个文件）
   - `tests/unit/test_models.py` - 新增数据模型测试
   - `tests/unit/test_github_collector.py` - 新增元数据提取测试
   - `scripts/test_phase8_integration.py` - 集成测试脚本

3. **分析脚本**（1个文件）
   - `scripts/analyze_phase8_scores.py` - 评分改善效果分析

4. **文档**（2个文件）
   - `.claude/specs/benchmark-intelligence-agent/PHASE8-IMPLEMENTATION-REPORT.md` - 实施报告
   - `.claude/specs/benchmark-intelligence-agent/PHASE8-ACCEPTANCE-CHECKLIST.md` - 验收清单

---

## 8. 注意事项（Codex必读）

### 8.1 开发前必做

1. ✅ **确认飞书字段已创建**：手动登录飞书表格，创建7个新字段后再开始编码
2. ✅ **备份现有main分支**：`git checkout -b phase7-backup`
3. ✅ **创建Phase 8开发分支**：`git checkout -b phase8-field-expansion`

### 8.2 编码规范

1. **魔法数字**：所有数字常量定义在`src/common/constants.py`
2. **中文注释**：关键逻辑必须写中文注释（如Prompt构造、字段映射）
3. **PEP8格式**：编码完成后运行`black . && ruff check --fix .`
4. **类型提示**：所有新方法必须有完整的类型提示

### 8.3 测试要求

1. **单元测试先行**：每个新方法都要有对应单元测试
2. **集成测试验证**：Step 5必须完整运行，输出日志检查
3. **手动验收**：Step 6必须检查飞书表格实际写入结果

### 8.4 Git提交规范

```bash
# 示例Commit Message
feat(models): 新增Phase 8的7个字段（task_domain/metrics/baselines等）

- RawCandidate新增6个raw_*字段用于采集器粗提取
- ScoredCandidate新增7个精炼字段用于LLM提取
- 无Breaking Change，向后兼容
```

---

## 9. FAQ

**Q1: 为什么要在采集器层做粗提取？**
A: 减轻LLM负担，提高准确率。采集器用正则+规则快速提取高置信度信息（如明确的"Pass@1"），LLM只需验证和补充。

**Q2: 如果LLM提取某个字段失败怎么办？**
A: 允许字段为空（Optional类型）。评分系统会根据已有字段调整评分，不会因为单个字段缺失而崩溃。

**Q3: task_domain允许多选吗？**
A: 是的。一个Benchmark可能同时评估Coding和ToolUse（如代码生成+API调用）。用逗号分隔多个领域。

**Q4: 评分Prompt太长会影响性能吗？**
A: 不会。gpt-4o-mini支持128k context，当前Prompt约4k tokens，加上abstract最多6k tokens，在安全范围内。

**Q5: Phase 8完成后还需要Phase 9吗？**
A: 视Phase 8验收结果而定。如果平均分≥6.5且高优先级命中率≥20%，则不需要Phase 9。否则继续优化Prompt或新增字段。

---

## 10. 验收流程

1. **Codex完成开发** → 提交PR → 打tag `phase8-v1.0`
2. **Claude Code执行验收**：
   - Step 1-3: 单元测试（自动化）
   - Step 4: 飞书字段映射验证（手动）
   - Step 5: 集成测试（半自动）
   - Step 6: 完整流程验收（3次运行 + 分析）
3. **验收通过** → 合并到main分支 → 部署到GitHub Actions
4. **验收不通过** → Codex修复 → 重新验收

---

**预期成果**：Phase 8完成后，BenchScope将具备完整的Benchmark智能识别能力，平均分从4.36提升至6.5+，高优先级Benchmark发现效率提升5倍以上，MGX Benchmark池扩充速度从2-3个/月提升至10-20个/月。
