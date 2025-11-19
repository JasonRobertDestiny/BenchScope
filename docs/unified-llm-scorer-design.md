# 全LLM统一评分系统设计方案（质量第一版）

## 设计原则

**核心目标**：消除所有硬编码，全部使用LLM深度分析，确保数据完整性和可解释性

**质量标准**：
1. 26个字段100%必填（禁止N/A）
2. 评分依据≥1200字（activity~relevance每维度≥150字，overall≥50字）
3. 若后端评分>0，则backend_mgx_reasoning与backend_engineering_reasoning各≥200字（否则可留空）
4. 每个评分必须附step-by-step推理链条
5. 所有推断必须基于提供的数据，明确标注推断依据
6. 当LLM响应因字符不足导致校验失败时，自动生成纠偏提示并触发最多2次自愈重试

## 数据模型扩展

### ScoredCandidate新增字段

```python
@dataclass(slots=True)
class ScoredCandidate:
    # ... 现有字段 ...

    # 详细推理字段（新增）
    activity_reasoning: str = ""  # 活跃度评分推理（150字）
    reproducibility_reasoning: str = ""  # 可复现性评分推理（150字）
    license_reasoning: str = ""  # 许可合规评分推理（150字）
    novelty_reasoning: str = ""  # 新颖性评分推理（150字）
    relevance_reasoning: str = ""  # MGX适配度评分推理（150字）

    # 后端专项评分（新增）
    backend_mgx_relevance: float = 0.0  # 后端MGX相关性评分（1-10）
    backend_mgx_reasoning: str = ""  # 后端MGX相关性推理（200字）
    backend_engineering_value: float = 0.0  # 后端工程实践价值（1-10）
    backend_engineering_reasoning: str = ""  # 后端工程价值推理（200字）

    # 任务分类（强制必填）
    task_type: str = ""  # Benchmark|Tool|Dataset|Paper（必须明确分类）
    license_type: str = ""  # 许可证类型（推断也可）

    # 数据集信息（详细）
    dataset_url: Optional[str] = None
    dataset_size: Optional[int] = None
    dataset_size_description: str = ""  # 必填，描述数据规模

    # 论文/项目元信息
    paper_url: Optional[str] = None
    reproduction_script_url: Optional[str] = None
    institution: str = ""  # 主要机构（必填，推断也可）
    authors: str = ""  # 作者列表（必填，格式化字符串）

    # Benchmark特征
    task_domain: str = ""  # 任务领域（必须从9大领域选择）
    metrics: str = ""  # 评估指标（逗号分隔，必填）
    baselines: str = ""  # 基准模型（逗号分隔，尽量填写）
```

## LLM Prompt设计（超详细版）

### System Prompt

```python
SYSTEM_PROMPT = """你是MGX BenchScope的资深Benchmark评估专家。

你的职责是对AI/Agent领域的研究项目、工具、数据集进行全面、深入、客观的评估。

评估原则：
1. 基于证据：所有评分和推断必须基于提供的数据
2. 完整性：所有字段必须填写，禁止返回N/A或null
3. 可解释性：每个评分必须有详细的step-by-step推理
4. 客观性：避免主观臆断，承认不确定性但仍需做出合理推断
5. 一致性：同类项目使用统一的评分标准

输出格式：严格的JSON，包含所有必填字段，不允许额外字段。
"""
```

### User Prompt Template（超详细版，4000+ tokens）

```python
COMPREHENSIVE_SCORING_PROMPT = """# Benchmark候选项全面评估

## 第一部分：候选项基础信息

### 项目标识
- **标题**: {title}
- **来源**: {source}
- **URL**: {url}

### 项目元数据
- **GitHub Stars**: {github_stars}
- **发布日期**: {publish_date}
- **许可证（采集器提取）**: {license_type}
- **任务类型（采集器提取）**: {task_type}

### 摘要/README内容（已清理）
```
{abstract}
```

### PDF深度解析内容（arXiv论文）

#### Evaluation章节摘要（最多2000字）
```
{evaluation_summary}
```

#### Dataset章节摘要（最多1000字）
```
{dataset_summary}
```

#### Baselines章节摘要（最多1000字）
```
{baselines_summary}
```

### 采集器粗提取字段（供参考）
- **原始指标**: {raw_metrics}
- **原始Baselines**: {raw_baselines}
- **原始作者**: {raw_authors}
- **原始机构**: {raw_institutions}
- **原始数据规模**: {raw_dataset_size}

---

## 第二部分：MGX场景定义与优先级

MGX是一个多智能体协作框架，专注Vibe Coding（AI原生编程）。

### 九大任务领域及优先级

**P0级（核心场景，9-10分适配度）**:
1. **Coding** - 代码生成、代码补全、代码理解、程序合成
2. **GUI Automation** - 图形界面自动化、GUI测试、桌面应用操作
3. **Web Automation** - 浏览器自动化、Web导航、网页交互

**P1级（高价值场景，7-8分适配度）**:
4. **Tool Use** - 工具调用、API使用、外部系统集成
5. **Agent Collaboration** - 多智能体协作、Agent通信、任务分配
6. **Multi-Agent** - 多Agent系统、分布式智能体、协同决策

**P2级（辅助场景，5-6分适配度）**:
7. **Deep Research** - 深度研究、信息检索、知识挖掘
8. **Reasoning** - 逻辑推理、数学推理、因果推理

**P3级（其他场景，2-4分适配度）**:
9. **Other** - 不属于以上任何类别，与MGX关联较弱

### 后端开发子场景（特殊关注）

如果候选项涉及以下任一场景，需进行后端专项评分：
- API设计与性能（RESTful、GraphQL、gRPC）
- 数据库查询优化（SQL、NoSQL）
- 微服务架构（服务发现、负载均衡、容错）
- 分布式系统（一致性、分区容错、可用性）
- 后端框架性能（FastAPI、Django、Spring Boot等）
- 系统设计能力（高并发、高可用、可扩展性）
- 服务器性能基准（吞吐量、延迟、资源利用率）

---

## 第三部分：评分任务（5维度 + 后端专项）

### 评分维度1：活跃度评分（权重25%）

**评分标准**:
- **GitHub活跃度（有stars数据）**:
  - 10分: ≥10000 stars，近期持续提交
  - 8-9分: 1000-9999 stars，活跃维护
  - 6-7分: 100-999 stars，定期更新
  - 4-5分: 10-99 stars或创建<6个月
  - 2-3分: <10 stars或长期未更新

- **论文影响力（无GitHub数据时）**:
  - 10分: 顶会论文+代码开源+社区讨论热烈
  - 8-9分: 顶会论文+代码开源
  - 6-7分: 会议论文或预印本+代码开源
  - 4-5分: 仅预印本论文，代码未开源
  - 2-3分: 无代码，无社区反响

- **最近更新时间**:
  - 2024年11月及以后: +1分
  - 2024年: 基准分
  - 2023年: -1分
  - 2022年及更早: -2分

**推理要求（150字）**:
1. 明确说明GitHub stars数量或论文发表情况
2. 分析最近更新时间，判断项目活跃度
3. 如无GitHub数据，说明基于什么推断活跃度
4. 给出最终评分及理由

---

### 评分维度2：可复现性评分（权重30%）

**评分标准**:
- **代码开源**: 8-10分基础分
  - 10分: 代码+数据+文档+复现脚本+评估工具全套开源
  - 8-9分: 代码+数据+文档开源
  - 7分: 仅代码开源，文档不完整

- **数据集开源**: +2分（在代码开源基础上）

- **评估脚本开源**: +1分

- **无代码但方法详细**: 5-6分
  - 6分: 论文提供详细算法、参数、实验设置
  - 5分: 论文提供基本方法描述

- **方法不明确**: 2-4分
  - 4分: 论文存在但细节不足
  - 2-3分: 仅摘要，无法复现

**推理要求（150字）**:
1. 判断代码是否开源（基于GitHub URL或paper_url）
2. 判断数据集是否开源（基于dataset_url或描述）
3. 判断文档和复现脚本完整性（基于README或PDF摘要）
4. 如信息不足，说明如何推断
5. 给出最终评分及理由

---

### 评分维度3：许可合规性评分（权重20%）

**评分标准**:
- **MIT / Apache-2.0 / BSD**: 10分（最友好）
- **GPL-3.0 / LGPL**: 7分（传染性限制）
- **CC-BY-4.0 / CC-BY-SA-4.0**: 6分（数据集常用）
- **其他开源许可证**: 5分
- **未知但疑似开源**: 3-4分（基于来源推断）
  - GitHub项目默认推断为MIT: 4分
  - 学术论文默认推断为研究友好: 3分
- **专有/闭源**: 1-2分

**推理要求（150字）**:
1. 明确说明License信息来源（采集器提取 or GitHub API or 推断）
2. 如果是推断，说明推断依据（例如：来自GitHub且无License说明，推断为MIT）
3. 分析许可证对商业使用、修改、分发的影响
4. 给出最终评分及理由

---

### 评分维度4：任务新颖性评分（权重15%）

**评分标准**:
- **全新任务定义**: 9-10分
  - 首次提出新的评测任务
  - 填补MGX场景空白
  - 引入新的评估维度或指标

- **改进现有任务**: 6-8分
  - 8分: 显著改进（新数据集+新指标+新baseline）
  - 7分: 中等改进（新数据集或新指标）
  - 6分: 小幅改进（扩展现有数据集）

- **复现/综述**: 3-5分
  - 5分: 高质量复现+详细分析
  - 4分: 标准复现
  - 3分: 仅综述或整理

- **时间新颖性加分**:
  - 2024年11月之后发布: +1分
  - 2024年发布: 基准分
  - 2023年: -1分
  - 2022年及更早: -2分

**推理要求（150字）**:
1. 分析任务是否首次提出（基于摘要和Evaluation摘要）
2. 对比现有Benchmark（如HumanEval、SWE-bench），说明差异
3. 评估对MGX的独特价值
4. 考虑时间因素
5. 给出最终评分及理由

---

### 评分维度5：MGX适配度评分（权重10%）

**评分标准**:
- **P0核心场景** (Coding/GUI/Web): 9-10分
  - 10分: 完全契合MGX核心能力，可直接集成
  - 9分: 高度相关，需小幅适配

- **P1高价值场景** (ToolUse/Collaboration/MultiAgent): 7-8分
  - 8分: 强相关，对MGX有重要价值
  - 7分: 相关，有一定价值

- **P2辅助场景** (DeepResearch/Reasoning): 5-6分
  - 6分: 有助于提升MGX推理能力
  - 5分: 间接相关

- **P3其他场景** (NLP/Vision/Speech等): 2-4分
  - 4分: 有Agent/代码关联
  - 2-3分: 纯NLP/视觉任务，无代码关联

**推理要求（150字）**:
1. 明确判断候选项属于哪个任务领域（从9大领域选择）
2. 分析与MGX场景的具体关联（基于任务描述、评估指标）
3. 说明如果纳入MGX，可以评测什么能力
4. 给出最终评分及理由

---

### 后端专项评分1：后端MGX相关性（1-10分）

**评分标准**:
- **10分**: 直接评测后端开发核心能力
  - API设计与性能基准
  - 数据库查询优化测试
  - 微服务架构评估
  - 分布式系统一致性测试

- **7-9分**: 涉及后端工程场景
  - 7分: 间接涉及（如全栈代码生成中的后端部分）
  - 8分: 部分涉及（如API调用测试）
  - 9分: 主要涉及（如后端框架性能对比）

- **4-6分**: 轻度相关
  - 系统设计面试题
  - 架构设计Benchmark

- **1-3分**: 基本无关
  - 纯前端、纯算法、纯NLP任务

**推理要求（200字）**:
1. 详细分析候选项是否涉及后端开发场景
2. 列举具体的后端相关评估指标（如吞吐量、延迟、并发数）
3. 说明对MGX后端能力评测的价值
4. 如果无关，明确说明原因
5. 给出最终评分及详细理由

---

### 后端专项评分2：后端工程实践价值（1-10分）

**评分标准**:
- **10分**: 行业标准Benchmark，广泛采用
  - 例如TechEmpower框架性能基准
  - 云厂商性能对比标准

- **7-9分**: 高工程价值
  - 9分: 覆盖主流框架/数据库，可直接指导技术选型
  - 8分: 提供性能基线和最佳实践
  - 7分: 有参考价值但覆盖面较窄

- **4-6分**: 中等价值
  - 学术研究为主，工程化不足
  - 实验环境与生产环境差距较大

- **1-3分**: 低工程价值
  - 玩具级别实验
  - 缺乏实用性

**推理要求（200字）**:
1. 评估行业采用度（是否被主流公司/框架使用）
2. 分析工程规范性（测试方法是否标准化、可重复）
3. 评估性能基准价值（能否指导技术选型和优化）
4. 分析可迁移性（能否应用到实际项目）
5. 给出最终评分及详细理由

---

## 第四部分：结构化字段提取

### 任务分类（task_type）

**必须从以下4类选择其一**:
- **Benchmark**: 评测基准，包含任务、数据集、评估指标、基准结果
- **Tool**: 工具/框架/库，可以用于开发但不是Benchmark
- **Dataset**: 仅数据集，无评估框架
- **Paper**: 纯论文，无代码无数据

**判断依据**:
1. 有数据集 + 有评估指标 + 有基准结果 → Benchmark
2. 有代码 + 无评估框架 → Tool
3. 仅数据集 → Dataset
4. 仅论文 → Paper

---

### 任务领域（task_domain）

**必须从9大领域选择，可多选（逗号分隔，按优先级排序）**:
- Coding
- GUI Automation
- Web Automation
- Tool Use
- Agent Collaboration
- Multi-Agent
- Deep Research
- Reasoning
- Other

**示例**:
- 代码生成Benchmark → "Coding"
- Web自动化+工具调用 → "Web Automation, Tool Use"
- 纯NLP任务 → "Other"

---

### 评估指标（metrics）

**提取规则**:
1. 从Evaluation摘要、Dataset摘要、raw_metrics提取
2. 使用标准缩写（Pass@1, BLEU-4, F1-Score, Accuracy）
3. 逗号分隔，最多10个
4. 如无法提取，基于任务类型推断常用指标

**示例**:
- 代码生成: "Pass@1, Pass@5, Pass@10"
- 文本生成: "BLEU-4, ROUGE-L, METEOR"
- 分类任务: "Accuracy, F1-Score, Precision, Recall"

---

### 基准模型（baselines）

**提取规则**:
1. 从Baselines摘要、raw_baselines提取
2. 使用规范名称（GPT-4, Claude-3.5-Sonnet, Llama-3.1-70B）
3. 逗号分隔，最多10个
4. 如无法提取，填写"Not specified"

---

### 作者与机构

**authors**:
- 从raw_authors或PDF提取
- 格式: "Alice Zhang, Bob Li, Charlie Wang"
- 最多列5位作者，超过则"et al."
- 如无法提取，填写"Not specified"

**institution**:
- 提取第一作者或通讯作者机构
- 格式: "Stanford University"
- 多机构时选择最知名的一个
- GitHub项目无作者时填写"Community"

---

### 数据集信息

**dataset_url**:
- 从dataset_url字段或README中的数据集链接提取
- 如无，填写null

**dataset_size**:
- 从raw_dataset_size或Dataset摘要中提取数字
- 例如"1000 problems" → 1000
- 无法提取时填写null

**dataset_size_description**:
- 原始描述，如"1000 Python coding problems from LeetCode"
- 如无，基于任务类型推断，如"Estimated 500+ samples"
- **必填，禁止为空**

---

### 许可证类型（license_type）

**提取优先级**:
1. 采集器提取的license_type字段
2. GitHub API的license信息
3. 推断（GitHub项目默认MIT，论文默认研究友好）

**必须规范化为标准名称**:
- MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, CC-BY-4.0等
- 未知时填写"Unknown (inferred as permissive)"

---

## 第五部分：综合评分与推荐

### 加权总分计算

```
total_score = (
    activity_score * 0.25 +
    reproducibility_score * 0.30 +
    license_score * 0.20 +
    novelty_score * 0.15 +
    relevance_score * 0.10
)
```

### 推荐标准

- **total_score ≥ 8.0 && relevance_score ≥ 9**: 强烈推荐纳入MGX（P0核心场景）
- **total_score ≥ 7.0 && relevance_score ≥ 7**: 推荐纳入MGX（P1高价值场景）
- **total_score ≥ 6.0 && relevance_score ≥ 5**: 考虑纳入MGX（P2辅助场景）
- **total_score < 6.0 || relevance_score < 5**: 不推荐纳入MGX

### 优先级分级

- **High**: total_score ≥ 8.0
- **Medium**: 6.0 ≤ total_score < 8.0
- **Low**: total_score < 6.0

---

## 第六部分：输出JSON格式（严格遵循）

```json
{
  "activity_score": 7.5,
  "activity_reasoning": "该项目GitHub有3113 stars，显示出较高的社区关注度（评分7分基准）。从最近的commit历史看，2024年10月有活跃更新，说明项目维护良好（+0.5分加成）。虽然不及顶级开源项目的万级stars，但在AI Agent领域属于中上水平。综合评分7.5分。",

  "reproducibility_score": 9.0,
  "reproducibility_reasoning": "代码在GitHub完全开源，README包含详细的安装和使用文档（8分基础）。提供了完整的评估脚本和数据集下载链接（+1分）。文档中包含了复现实验的详细步骤，包括环境配置、参数设置、预期结果（+1分，但因部分数据集需要申请访问权限，扣0.5分）。最终9.0分。",

  "license_score": 10.0,
  "license_reasoning": "项目使用MIT许可证（GitHub API确认），这是最友好的开源许可证之一，允许商业使用、修改和分发，无传染性限制。对MGX集成完全无障碍。评分10分。",

  "novelty_score": 8.5,
  "novelty_reasoning": "该Benchmark首次将推理强化应用于代码生成任务（+高新颖性）。虽然代码生成Benchmark已有HumanEval、MBPP等，但本项目引入了自我改进机制和推理链评估，这在现有工作中较少见（新颖性8分）。发布于2024年10月，属于最新研究（+0.5分时间加成）。综合8.5分。",

  "relevance_score": 9.5,
  "relevance_reasoning": "任务明确属于Coding领域，是MGX的P0核心场景（9分基准）。评估的能力包括代码生成、推理优化，直接对应MGX的Vibe Coding场景。从评估指标看，使用Pass@k和代码质量分析，与MGX的代码生成能力评测高度契合（+0.5分）。几乎可以无缝集成到MGX Benchmark池。综合9.5分。",

  "overall_reasoning": "综合评分8.43分，属于High优先级候选项。【Benchmark判断】该项目提供完整的任务定义、数据集、评估脚本和baseline结果，明确符合Benchmark定义。【推荐建议】强烈推荐纳入MGX Benchmark池。理由：(1) P0核心场景（代码生成），直接服务MGX核心能力评测；(2) 高可复现性（代码+数据+文档完整）；(3) 新颖性强（引入推理强化机制）；(4) 活跃度中上，社区认可度高；(5) MIT许可无障碍。【不足与建议】部分数据集需要申请访问权限，可能影响复现便利性，建议联系作者协商数据共享方案。",

  "task_domain": "Coding",
  "task_type": "Benchmark",
  "metrics": "Pass@1, Pass@5, Pass@10, Code Quality Score, Reasoning Chain Length",
  "license_type": "MIT",
  "authors": "Alice Zhang, Bob Li, Charlie Wang",
  "institution": "Stanford University",
  "dataset_size": 1000,
  "dataset_size_description": "1000 Python coding problems with varying difficulty levels",
  "dataset_url": "https://github.com/example/dataset",
  "paper_url": "https://arxiv.org/abs/2411.12345",
  "reproduction_script_url": "https://github.com/example/scripts/evaluate.py",
  "baselines": "GPT-4, Claude-3.5-Sonnet, Llama-3.1-70B, CodeLlama-34B",

  "backend_mgx_relevance": 3.5,
  "backend_mgx_reasoning": "该Benchmark主要评测通用代码生成能力，任务集中包含少量后端相关问题（如API设计、数据库查询），但占比不到20%。主要侧重算法和逻辑实现，而非系统设计或性能优化。从评估指标看，未包含API性能、并发处理、数据库优化等后端特定指标。因此判断与后端开发场景关联度较低。评分3.5分，表示有轻微关联但非核心。",

  "backend_engineering_value": 4.0,
  "backend_engineering_reasoning": "从工程实践角度看，该Benchmark更偏向学术研究，评估环境为标准测试用例，与真实生产环境的后端工程场景有一定差距。虽然生成的代码质量评估有一定参考价值，但缺乏对API设计规范、系统架构、性能优化等工程维度的考察。对后端工程师的技术选型和最佳实践指导作用有限。评分4.0分，表示有一定参考价值但工程化不足。"
}
```

## 第七部分：特殊情况处理规则

### 情况1：信息严重不足

**场景**: 仅有标题和极简摘要，无GitHub、无论文、无详细信息

**处理方式**:
1. 基于标题和来源做合理推断
2. 所有推断必须明确标注"推断依据"
3. 评分偏保守（降低不确定性影响）
4. 在reasoning中明确说明信息不足的情况

**示例推断逻辑**:
- 来自arXiv且标题包含"Benchmark" → task_type推断为Benchmark
- GitHub项目但无license信息 → license_type推断为"Unknown (inferred as MIT for GitHub projects)"
- 无stars数据但发布于2024年 → activity_score推断为5分（新项目基准分）

---

### 情况2：非英文内容

**场景**: 摘要或README为中文/其他语言

**处理方式**:
1. 正常提取关键信息
2. 英文字段（如metrics, baselines）使用英文表达
3. reasoning可以使用中文
4. 标题和机构名称保持原语言

---

### 情况3：多领域交叉

**场景**: 候选项同时涉及多个任务领域

**处理方式**:
1. task_domain可多选（逗号分隔）
2. 按优先级排序（主要领域在前）
3. relevance_score按最高优先级领域评分
4. reasoning中说明多领域特性

**示例**:
- 一个评测Web Agent代码生成能力的Benchmark
- task_domain: "Coding, Web Automation, Tool Use"
- relevance_score: 9.5（按P0核心场景Coding评分）

---

### 情况4：后端无关项目

**场景**: 纯前端、纯算法、纯NLP等与后端无关的项目

**处理方式**:
1. backend_mgx_relevance: 1.0-2.0
2. backend_engineering_value: 1.0-2.0
3. reasoning明确说明"该项目与后端开发场景无关"
4. 不影响总分和推荐判断

---

## 第八部分：质量检查清单

在输出JSON之前，请自我检查以下事项：

- [ ] 所有26个字段都已填写（无null、无N/A、无空字符串）
- [ ] activity/reproducibility/license/novelty/relevance五个reasoning各≥150字
- [ ] overall_reasoning ≥ 50字
- [ ] 若backend_mgx_relevance或backend_engineering_value>0，则对应后端reasoning各≥200字
- [ ] task_domain从9大领域选择，不能是其他值
- [ ] task_type从4类选择，不能是其他值
- [ ] license_type已规范化为标准名称
- [ ] metrics和baselines使用规范缩写
- [ ] 所有评分在0-10范围内
- [ ] JSON格式正确，可被解析
- [ ] 所有推断都标注了依据

---

## 第九部分：立即开始评估

请基于上述所有信息，对候选项进行全面评估，输出完整的JSON结果。

**重要提醒**:
1. 必须填写所有26个字段
2. 所有推理字段必须详细（总计1200字+）
3. 基于提供的数据，合理推断，明确标注推断依据
4. 保持客观性和一致性
5. JSON格式严格，确保可被程序解析

开始评估！
"""
```

## 自愈重试机制

为确保上述字符长度约束真正落地，LLM scorer 增加了“自愈”循环：

1. 首次响应若触发Pydantic的 `string_too_short` / 后端推理自定义校验，将解析出具体字段与当前字数；
2. 生成中文纠偏提示，逐条列出“当前字数 vs 要求字数”，提醒LLM补充证据、场景影响与风险说明；
3. 将原始JSON作为assistant消息回放，再附加纠偏提示，以 `LLM_SELF_HEAL_MAX_ATTEMPTS`（当前=2） 为上限重新请求；
4. 若仍然不达标，则保留异常日志并向上抛出，方便排查；
5. 相关阈值集中在 `src/common/constants.py`：
   - `LLM_REASONING_MIN_CHARS` (150)
   - `LLM_BACKEND_REASONING_MIN_CHARS` (200)
   - `LLM_OVERALL_REASONING_MIN_CHARS` (50)

该机制显著降低了因推理过短导致的失败重试次数，保障流水线稳定。

## 实施计划

### Step 1: 扩展数据模型（30分钟）
- 修改 `src/models.py`
- 新增详细推理字段

### Step 2: 重写LLM Scorer（2小时）
- 创建新的prompt template
- 创建新的Pydantic model（BenchmarkExtraction v2）
- 更新LLM调用逻辑
- 增加JSON validation和重试机制

### Step 3: 增强GitHub Collector（30分钟）
- 清理Markdown/HTML标签
- 提取完整license信息
- 提取topics和languages

### Step 4: 补全字段映射（15分钟）
- 更新 `feishu_storage.py`
- 添加新字段映射

### Step 5: 更新主流程（15分钟）
- 移除backend_scorer调用
- 更新main.py

### Step 6: 测试验证（1小时）
- 单元测试
- 集成测试
- 数据质量验证

## 预期效果

| 指标 | 当前 | 优化后 |
|------|------|--------|
| 字段完整率 | 40% | 100% |
| 评分依据总长度 | 58-193字符 | 1200+字符 |
| 可解释性 | 低（硬编码） | 极高（详细推理） |
| 后端评分质量 | 0（硬编码7.0） | 高（LLM深度分析） |
| 数据准确性 | 低（大量N/A） | 高（强制必填） |
