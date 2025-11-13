# 飞书字段映射完善说明

## 完成时间
2025-11-13

## 背景

Codex完成Semantic Scholar采集器开发后，用户明确提出核心目标：

> 希望能做一个Benchmark的资讯信息自动播报Agent：
> 1. 系统性调研与评估新的GUI/Web/Coding/DeepResearch/Agent协作相关Benchmarks
> 2. 建立"可定期更新"的自动化情报流，降低人工维护成本
> 3. **一键添加到Benchmark候选表**，包含论文地址、数据集地址、复现脚本、评估指标、开源时间等基础信息

## 问题发现

检查当前飞书字段映射（`src/storage/feishu_storage.py`）发现：
- ✅ 已有22个字段：基础信息(4) + 评分维度(9) + Phase 6新增(9)
- ❌ **缺失1个关键字段**: `license_type` (License类型)

虽然`src/models.py`中的`ScoredCandidate`定义了`license_type`字段，但飞书存储层未映射和处理该字段。

## 解决方案

### 1. 添加license_type到FIELD_MAPPING

**文件**: `src/storage/feishu_storage.py:25-51`

```python
FIELD_MAPPING: Dict[str, str] = {
    # ... 其他字段 ...
    "license_type": "License类型",  # 新增
}
```

### 2. 在_to_feishu_record中处理license_type

**文件**: `src/storage/feishu_storage.py:172-173`

```python
if hasattr(candidate, "license_type") and candidate.license_type:
    fields[self.FIELD_MAPPING["license_type"]] = candidate.license_type
```

### 3. 更新项目规范（.claude/CLAUDE.md）

添加以下内容：

#### 核心目标（Core Objectives）
1. 系统性调研与评估新Benchmarks
2. 建立"可定期更新"的自动化情报流
3. **一键添加到候选池**（完整基础信息）

#### 工作流（Workflow）
```
自动发现 → 预筛与评分 → 一键添加 → 飞书播报与人工审核
```

#### 飞书必需字段清单（23个字段）

详细列表见`.claude/CLAUDE.md:141-173`，包含：
- 基础信息(4): 标题、来源、URL、摘要
- 关键资源(3): 论文URL、数据集URL、复现脚本链接
- 元数据(6): 评价指标、开源时间、任务类型、License类型、GitHub Stars、作者信息
- 评分维度(9): 5维评分 + 总分 + 优先级 + 评分依据 + 状态

**字段优先级**：
- ✅ **必需**: 系统自动填充，缺失会导致评分失败
- ⚠️ **强烈推荐**: 支撑快速决策的关键信息
- **可选**: 锦上添花的补充信息

---

## 完整字段映射对照表

| # | Python字段 | 飞书列名 | 数据类型 | 优先级 | 说明 |
|---|-----------|---------|---------|-------|------|
| **基础信息** |
| 1 | title | 标题 | 文本 | ✅ 必需 | Benchmark名称 |
| 2 | source | 来源 | 单选 | ✅ 必需 | arXiv/GitHub/HuggingFace/SemanticScholar |
| 3 | url | URL | URL | ✅ 必需 | 主要链接 |
| 4 | abstract | 摘要 | 文本 | ✅ 必需 | Benchmark简介（≤500字） |
| **关键资源** |
| 5 | paper_url | 论文 URL | URL | ⚠️ 强烈推荐 | 论文原文链接 |
| 6 | dataset_url | 数据集 URL | URL | ⚠️ 强烈推荐 | 数据集下载/查看链接 |
| 7 | reproduction_script_url | 复现脚本链接 | URL | 可选 | 评估/复现脚本仓库 |
| **元数据** |
| 8 | evaluation_metrics | 评价指标摘要 | 文本 | ⚠️ 强烈推荐 | 如"Accuracy, F1, BLEU" |
| 9 | publish_date | 开源时间 | 日期 | 可选 | 首次发布日期（YYYY-MM-DD） |
| 10 | task_type | 任务类型 | 单选 | ⚠️ 强烈推荐 | Code Generation/QA/Reasoning |
| 11 | **license_type** | **License类型** | **文本** | **可选** | **MIT/Apache-2.0/GPL** |
| 12 | github_stars | GitHub Stars | 数字 | 可选 | GitHub项目星标数 |
| 13 | authors | 作者信息 | 文本 | 可选 | 主要作者列表（≤200字） |
| **评分维度** |
| 14 | activity_score | 活跃度 | 数字 | ✅ 必需 | 0-10分 (25%权重) |
| 15 | reproducibility_score | 可复现性 | 数字 | ✅ 必需 | 0-10分 (30%权重) |
| 16 | license_score | 许可合规 | 数字 | ✅ 必需 | 0-10分 (20%权重) |
| 17 | novelty_score | 任务新颖性 | 数字 | ✅ 必需 | 0-10分 (15%权重) |
| 18 | relevance_score | MGX适配度 | 数字 | ✅ 必需 | 0-10分 (10%权重) |
| 19 | total_score | 总分 | 数字 | ✅ 必需 | 加权总分(0-10) |
| 20 | priority | 优先级 | 单选 | ✅ 必需 | high/medium/low (自动计算) |
| 21 | reasoning | 评分依据 | 文本 | ✅ 必需 | LLM解释为何作为候选（≤500字） |
| **状态管理** |
| 22 | status | 状态 | 单选 | ✅ 必需 | pending/approved/rejected |

**第11个字段license_type为本次新增**，其余22个字段已在Phase 6实现。

---

## 数据类型处理规则

### URL字段（5个）
```python
# url, paper_url, dataset_url, reproduction_script_url
fields["论文 URL"] = {"link": candidate.paper_url}  # 飞书URL类型要求
```

### 日期字段（1个）
```python
# publish_date
fields["开源时间"] = candidate.publish_date.strftime("%Y-%m-%d")  # YYYY-MM-DD格式
```

### 列表字段（2个）
```python
# authors: List[str] → "作者1, 作者2" (逗号分隔，限制200字)
fields["作者信息"] = ", ".join(candidate.authors)[:200]

# evaluation_metrics: List[str] → "Accuracy, F1, BLEU" (逗号分隔，限制200字)
fields["评价指标摘要"] = ", ".join(candidate.evaluation_metrics)[:200]
```

### 文本字段（5个）
```python
# title, abstract, reasoning, task_type, license_type
fields["摘要"] = candidate.abstract or ""
fields["评分依据"] = candidate.reasoning[:500] if candidate.reasoning else ""  # 限制500字
```

### 数字字段（8个）
```python
# 5维评分 + total_score + github_stars
fields["活跃度"] = candidate.activity_score  # 直接传递浮点数
fields["GitHub Stars"] = candidate.github_stars  # 整数
```

### 单选字段（4个）
```python
# source, priority, status, task_type (如果飞书设为单选)
fields["来源"] = candidate.source  # "arxiv" / "github" / "huggingface" / "semantic_scholar"
fields["优先级"] = candidate.priority  # "high" / "medium" / "low"
fields["状态"] = "pending"  # 默认值
```

---

## 飞书表格配置要求

为确保系统正常运行，飞书多维表格需包含以下列（共23列）：

### 第一组：基础信息（4列）
1. **标题** - 文本
2. **来源** - 单选：`arXiv` / `GitHub` / `HuggingFace` / `SemanticScholar`
3. **URL** - URL
4. **摘要** - 文本

### 第二组：关键资源（3列）
5. **论文 URL** - URL
6. **数据集 URL** - URL
7. **复现脚本链接** - URL

### 第三组：元数据（6列）
8. **评价指标摘要** - 文本
9. **开源时间** - 日期
10. **任务类型** - 单选或文本
11. **License类型** - 文本 ⚡ **本次新增**
12. **GitHub Stars** - 数字
13. **作者信息** - 文本

### 第四组：评分维度（9列）
14. **活跃度** - 数字
15. **可复现性** - 数字
16. **许可合规** - 数字
17. **任务新颖性** - 数字
18. **MGX适配度** - 数字
19. **总分** - 数字
20. **优先级** - 单选：`high` / `medium` / `low`
21. **评分依据** - 文本
22. **状态** - 单选：`pending` / `approved` / `rejected`

**重要提示**: 如果飞书表格缺少某些列，系统仍可运行，但会导致数据不完整。建议创建完整的23列。

---

## 测试验证

### 1. 单元测试（已有）
```bash
pytest tests/unit/test_collectors.py -v
```

### 2. 手动测试步骤

#### 步骤1: 运行Pipeline
```bash
python src/main.py
```

#### 步骤2: 检查飞书表格
访问飞书多维表格，确认以下字段有数据：

**必填字段（应该全部有值）**:
- ✅ 标题、来源、URL、摘要
- ✅ 活跃度、可复现性、许可合规、任务新颖性、MGX适配度
- ✅ 总分、优先级、评分依据、状态

**强烈推荐字段（大部分应该有值）**:
- ⚠️ 论文URL（arXiv/SemanticScholar来源必有）
- ⚠️ 数据集URL（HuggingFace来源必有）
- ⚠️ 评价指标摘要
- ⚠️ 任务类型

**可选字段（有则更好）**:
- License类型（GitHub来源可能有）
- GitHub Stars（GitHub来源必有）
- 作者信息（arXiv/SemanticScholar来源必有）
- 开源时间（有publish_date的来源）
- 复现脚本链接（需LLM抽取或人工补充）

#### 步骤3: 验证License类型字段
```bash
# 检查GitHub来源的候选项是否有License类型
# 示例: MIT, Apache-2.0, GPL-3.0等
```

---

## 后续改进建议

### 1. License自动检测（GitHub采集器）
当前GitHub采集器未抽取License信息，建议：
```python
# src/collectors/github_collector.py
license_info = repo_data.get("license")
if license_info:
    candidate.license_type = license_info.get("name")  # "MIT", "Apache-2.0"等
```

### 2. License映射（其他来源）
- arXiv/SemanticScholar: 通常无License信息（论文不需要License）
- HuggingFace: 可能在dataset card中提到License
- 需LLM从README/描述中抽取

### 3. 评估指标自动抽取
当前evaluation_metrics需要手动填充或LLM抽取，建议：
- Phase 6.6: 优化LLM评分Prompt，要求返回评估指标列表
- 从论文摘要中识别常见指标关键词（Accuracy, F1, BLEU, ROUGE等）

---

## 相关文档

- `.claude/CLAUDE.md` - 项目规范（已更新核心目标和工作流）
- `src/storage/feishu_storage.py` - 飞书存储实现（已添加license_type）
- `src/models.py` - 数据模型定义（已有license_type字段）
- `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md` - Phase 6详细PRD

---

**文档生成时间**: 2025-11-13
**负责人**: Claude Code
**状态**: ✅ 字段映射完善完成，共23个字段
**变更**: 新增license_type字段 (22→23)
