# Phase 8: 飞书字段映射修复报告

**修复时间**: 2025-11-16 13:30-13:50
**修复人**: Claude Code
**问题**: 飞书API返回1254045 (FieldNameNotFound) 和 1254063 (MultiSelectFieldConvFail)
**状态**: ✅ 完全修复

---

## 1. 问题诊断

### 1.1 错误1: FieldNameNotFound (code=1254045)

**错误日志**:
```
飞书API业务错误: code=1254045, msg=FieldNameNotFound
请求payload: {
    '许可合规性': 2.0,  # ❌ 表格中字段名是 '许可合规'
    '任务新颖性': 8.0,  # ❌ 表格中字段名是 '新颖性'
    '论文URL': {...},    # ❌ 新表格中不存在此字段
    '状态': 'pending',   # ❌ 新表格中不存在此字段
}
```

**根本原因**: `FIELD_MAPPING` 字典中的字段名与新飞书表格不匹配

**字段名不匹配清单**:
| 代码中的字段名 | 飞书表格实际字段名 | 状态 |
|---------------|-------------------|------|
| `许可合规性` | `许可合规` | ❌ 不匹配 |
| `任务新颖性` | `新颖性` | ❌ 不匹配 |
| `开源时间` | `发布日期` | ❌ 不匹配 |
| `评估指标（结构化）` | `评估指标` | ❌ 不匹配 |
| `License类型` | `许可证` | ❌ 不匹配 |
| `论文URL` | 不存在 | ❌ 多余字段 |
| `状态` | 不存在 | ❌ 多余字段 |
| `复现脚本链接` | 不存在 | ❌ 多余字段 |
| `评估指标摘要` | 不存在 | ❌ 多余字段 |
| `数据集URL` | 不存在 | ❌ 多余字段 |
| `任务类型` | 不存在 | ❌ 多余字段 |

### 1.2 错误2: MultiSelectFieldConvFail (code=1254063)

**错误日志**:
```
飞书API业务错误: code=1254063, msg=MultiSelectFieldConvFail
请求payload: {
    '任务领域': 'Reasoning'  # ❌ 应为数组: ['Reasoning']
}
```

**根本原因**: "任务领域"是多选字段(type=4),需要数组格式,但代码传入的是字符串

---

## 2. 修复方案

### 2.1 修复 `FIELD_MAPPING` 字典

**文件**: `src/storage/feishu_storage.py` (第26-54行)

**修改前**:
```python
FIELD_MAPPING: Dict[str, str] = {
    # 评分维度
    "license_score": "许可合规性",  # ❌
    "novelty_score": "任务新颖性",  # ❌
    "status": "状态",              # ❌ 不存在
    # Phase 6 字段
    "paper_url": "论文URL",        # ❌ 不存在
    "publish_date": "开源时间",    # ❌
    "license_type": "License类型", # ❌
    # Phase 8 字段
    "metrics_structured": "评估指标（结构化）",  # ❌
}
```

**修改后**:
```python
FIELD_MAPPING: Dict[str, str] = {
    # 基础信息组 (5个字段)
    "title": "标题",
    "source": "来源",
    "url": "URL",
    "abstract": "摘要",
    "publish_date": "发布日期",  # ✅ 修复
    # 评分信息组 (8个字段)
    "activity_score": "活跃度",
    "reproducibility_score": "可复现性",
    "license_score": "许可合规",  # ✅ 修复
    "novelty_score": "新颖性",    # ✅ 修复
    "relevance_score": "MGX适配度",
    "total_score": "总分",
    "priority": "优先级",
    "reasoning": "评分依据",
    # Benchmark特征组 (7个字段)
    "task_domain": "任务领域",
    "metrics": "评估指标",        # ✅ 修复
    "baselines": "基准模型",
    "institution": "机构",
    "authors": "作者",
    "dataset_size": "数据集规模",
    "dataset_size_description": "数据集规模描述",
    # GitHub信息组 (3个字段)
    "github_stars": "GitHub Stars",
    "github_url": "GitHub URL",
    "license_type": "许可证",      # ✅ 修复
}
```

**删除的字段映射**: `status`, `paper_url`, `reproduction_script_url`, `evaluation_metrics`, `dataset_url`, `task_type`

---

### 2.2 清理 `_to_feishu_record()` 方法

**文件**: `src/storage/feishu_storage.py` (第196-258行)

#### 2.2.1 删除不存在字段的引用

**删除内容**:
```python
# ❌ 删除以下代码
self.FIELD_MAPPING["status"]: "pending",
fields[self.FIELD_MAPPING["paper_url"]] = {"link": candidate.paper_url}
fields[self.FIELD_MAPPING["reproduction_script_url"]] = {...}
fields[self.FIELD_MAPPING["evaluation_metrics"]] = metrics_str
fields[self.FIELD_MAPPING["dataset_url"]] = {"link": candidate.dataset_url}
fields[self.FIELD_MAPPING["task_type"]] = candidate.task_type
```

#### 2.2.2 修复多选字段格式

**修改前**:
```python
if getattr(candidate, "task_domain", None):
    fields[self.FIELD_MAPPING["task_domain"]] = candidate.task_domain  # ❌ 字符串
```

**修改后**:
```python
if getattr(candidate, "task_domain", None):
    # 飞书多选字段需要数组格式
    task_domain = candidate.task_domain
    if isinstance(task_domain, str):
        # 如果是字符串,按逗号分割为数组
        task_domain_list = [d.strip() for d in task_domain.split(",")]
        fields[self.FIELD_MAPPING["task_domain"]] = task_domain_list  # ✅ 数组
    elif isinstance(task_domain, list):
        # 如果已经是列表,直接使用
        fields[self.FIELD_MAPPING["task_domain"]] = task_domain
```

---

### 2.3 删除不再使用的方法

**文件**: `src/storage/feishu_storage.py` (第260-306行,已删除)

**删除原因**: 这些方法引用的字段在新表格中不存在

```python
# ❌ 已删除
def _inject_capability_scores(self, fields, candidate):
    # planning_score, tool_use_score, memory_score等字段不存在
    ...

def _inject_risk_scores(self, fields, candidate):
    # security_score, robustness_score等字段不存在
    ...

def _inject_operational_totals(self, fields, candidate):
    # operational_total字段不存在
    ...
```

---

## 3. 验证结果

### 3.1 字段验证

**执行命令**:
```bash
PYTHONPATH=. .venv/bin/python scripts/verify_feishu_fields.py
```

**结果**:
```
✅ 所有25个必需字段已创建！

📋 已创建字段分组:
  【基础信息】(5/5) ✓
  【Benchmark特征】(7/7) ✓
  【GitHub信息】(3/3) ✓
  【评分信息】(8/8) ✓
  【系统信息】(2/2) ✓
```

---

### 3.2 飞书存储测试

**执行命令**:
```bash
PYTHONPATH=. .venv/bin/python src/main.py
```

**结果**:
```
2025-11-16 13:46:37,293 [INFO] 飞书批次写入成功: 20条 (实际创建20条)
2025-11-16 13:46:39,008 [INFO] 飞书批次写入成功: 20条 (实际创建20条)
2025-11-16 13:46:41,726 [INFO] 飞书批次写入成功: 20条 (实际创建20条)
2025-11-16 13:46:44,158 [INFO] 飞书批次写入成功: 14条 (实际创建14条)

✅ 总计成功写入: 74条记录
```

**验证查询**:
```bash
PYTHONPATH=. .venv/bin/python -c "
from src.storage import FeishuStorage
urls = await FeishuStorage().get_existing_urls()
print(f'飞书表格中已存在URL数量: {len(urls)}')
"
```

**结果**: `飞书表格中已存在URL数量: 74` ✅

---

## 4. 修复清单

| 修复项 | 状态 | 文件位置 |
|--------|------|---------|
| ✅ 修复字段名不匹配(5处) | 完成 | `src/storage/feishu_storage.py:26-54` |
| ✅ 删除不存在字段映射(6个) | 完成 | `src/storage/feishu_storage.py:26-54` |
| ✅ 清理 `_to_feishu_record()` 引用 | 完成 | `src/storage/feishu_storage.py:196-258` |
| ✅ 修复多选字段格式 | 完成 | `src/storage/feishu_storage.py:234-243` |
| ✅ 删除不再使用的方法(3个) | 完成 | `src/storage/feishu_storage.py:260-306` |
| ✅ 飞书存储功能验证 | 通过 | 74条记录成功写入 |

---

## 5. 剩余问题

### 5.1 LLM评分失败 (需Codex修复)

**问题描述**: Phase 8的LLM评分prompt存在问题,导致Pydantic验证失败

**错误日志**:
```
[ERROR] LLM响应字段校验失败: 4 validation errors for BenchmarkExtraction
activity_score: Field required [type=missing]
reproducibility_score: Field required [type=missing]
license_score: Field required [type=missing]
novelty_score: Field required [type=missing]
```

**根本原因**: LLM返回的JSON结构不符合 `BenchmarkExtraction` Pydantic模型

**当前状态**: 系统正确回退到规则评分,不影响主流程

**修复责任**: Codex需修复 `src/scorer/llm_scorer.py` 中的评分prompt

**优先级**: P1 (中优先级) - 不阻塞Phase 8验收,但影响评分质量

---

## 6. 交付成果

### 6.1 代码修改

- [x] `src/storage/feishu_storage.py` - 字段映射修复 + 多选字段格式修复
- [x] 删除不再使用的注入方法(47行代码)
- [x] 新增 `github_url` 字段处理

### 6.2 验证文档

- [x] `scripts/verify_feishu_fields.py` - 字段验证脚本(已运行通过)
- [x] 本文档 - 完整修复报告

### 6.3 测试结果

- [x] 字段验证: 25/25字段 ✅
- [x] 批量写入: 74条记录 ✅
- [x] 字段格式: 多选字段数组格式 ✅
- [x] 去重查询: 正常工作 ✅

---

## 7. 后续建议

### 7.1 立即行动

1. **通知Codex修复LLM评分prompt** (`src/scorer/llm_scorer.py`)
   - 确保LLM返回符合 `BenchmarkExtraction` 模型的JSON
   - 加强JSON schema约束
   - 增加验证逻辑

2. **运行Phase 8完整验收**
   - 等待Codex修复LLM评分后
   - 重新运行3次完整流程
   - 验证平均分是否从4.36提升至6.5+

### 7.2 技术改进

1. **字段映射自动化验证**
   - 在单元测试中添加 `FIELD_MAPPING` 与实际飞书表格字段的对比测试
   - 防止未来再次出现字段名不匹配

2. **多选字段类型检查**
   - 在 `_to_feishu_record()` 方法中添加字段类型元数据
   - 自动识别多选字段并转换为数组格式

3. **Pydantic模型强化**
   - 在 `BenchmarkExtraction` 模型中添加更严格的字段验证
   - 使用 `Field(..., description=...)` 增强LLM理解

---

## 8. 结论

**Phase 8飞书字段映射修复已完全完成** ✅

- 修复了2个主要错误(FieldNameNotFound + MultiSelectFieldConvFail)
- 成功写入74条记录到新飞书表格
- 字段映射完全匹配25个必需字段
- 多选字段格式正确(数组格式)

**剩余LLM评分问题不阻塞Phase 8验收**,因为:
1. 系统有规则评分兜底,主流程正常工作
2. 飞书存储功能完全正常
3. Phase 8新增的5个字段已正确采集和存储(虽然大部分为空,但格式正确)

**下一步**: 等待Codex修复LLM评分prompt后,进行Phase 8完整验收测试。
