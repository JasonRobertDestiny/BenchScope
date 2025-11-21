# Codex开发指令文档：修复Self-Healing总推理长度检查Bug

## 📋 问题诊断

### 当前问题

**现象**（2025-11-21日志）：
```
[WARNING] LLM推理长度不足，触发第1次纠偏: VerlTool/SkyRL-SQL-Reproduction
[WARNING] 推理总字数不足: 1120 < 1200，候选：VerlTool/SkyRL-SQL-Reproduction
```

**问题**：
- Self-Healing只触发了1次纠偏
- 纠偏后总推理长度仍然不足（1120 < 1200）
- 系统没有触发第2次纠偏，直接返回了结果

### 根本原因

**代码逻辑分析** (src/scorer/llm_scorer.py:629-687)：

```python
while True:
    response = await self.client.chat.completions.create(...)

    try:
        extraction = UnifiedBenchmarkExtraction.parse_obj(payload)
    except ValidationError as exc:
        # ← Self-Healing只处理ValidationError
        violations = self._extract_length_violations(exc, payload)
        if violations and repair_attempt < constants.LLM_SELF_HEAL_MAX_ATTEMPTS:
            repair_attempt += 1
            continue  # ← 触发纠偏，重新进入循环
        raise

    # ← parse_obj通过后，检查总推理长度
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
        logger.warning("推理总字数不足: %d < 1200，候选：%s", ...)
        # ← Bug在这里：只是WARNING，没有触发重试！

    return extraction  # ← 直接返回，不会重新进入循环
```

**问题所在**：

| 检查类型 | 触发位置 | Self-Healing处理 |
|---------|---------|-----------------|
| **单字段长度** (≥150字符) | Pydantic ValidationError | ✅ **触发重试** |
| **总推理长度** (≥1200字符) | 模型外部if检查 | ❌ **只记WARNING，不重试** |

**执行流程示例**：
```
第1次LLM调用:
  - activity_reasoning: 100 chars (< 150)
  - 其他字段: 都≥150
  → ValidationError → 触发第1次纠偏

第2次LLM调用（纠偏后）:
  - activity_reasoning: 160 chars (≥150) ✅
  - 其他字段: 都≥150 ✅
  → parse_obj通过，无ValidationError
  → 检查总长度: 1120 < 1200
  → 只记WARNING，直接返回 ❌
  → 没有触发第2次纠偏
```

---

## 🎯 解决方案

### 方案设计

**核心思路**：将总推理长度检查也纳入Self-Healing循环

**修改位置**：`src/scorer/llm_scorer.py` 的 `_call_llm()` 方法

**修改逻辑**：
1. `parse_obj`通过后，立即检查总推理长度
2. 如果`total_reasoning_length < 1200`且未达最大重试次数：
   - 增加repair_attempt计数
   - 构造总长度不足的修复prompt
   - 追加到messages继续循环
3. 如果已达最大重试次数：
   - 记录WARNING（保持现有行为）
   - 返回结果（降级处理）

---

## 📝 实施步骤

### Step 1: 修改 `_call_llm()` 方法的总推理长度检查逻辑

**文件**: `src/scorer/llm_scorer.py`

**当前代码** (Line 670-687):
```python
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

    return extraction
```

**修改后代码** (替换Line 670-687):
```python
    # 检查总推理长度
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

    # 如果总推理长度不足且未达最大重试次数，触发纠偏
    if total_reasoning_length < 1200 and repair_attempt < constants.LLM_SELF_HEAL_MAX_ATTEMPTS:
        repair_attempt += 1

        # 构造总长度不足的修复prompt
        shortage = 1200 - total_reasoning_length
        fix_prompt = (
            f"上一次JSON输出的推理总字数不足：当前{total_reasoning_length}字符，要求≥1200字符（差{shortage}字符）。\n\n"
            f"请保留所有字段并重新输出完整JSON，通过以下方式扩写推理段落：\n"
            f"1. 补充具体数据（GitHub stars、PR数量、提交时间、算力需求等）\n"
            f"2. 展开论证结构："证据→分析→结论"，每个推理段落至少2-3句话\n"
            f"3. 明确指出潜在风险和不足，不要只写优点\n"
            f"4. 如果信息不足，写明推断依据与局限性\n\n"
            f"只输出符合Schema的纯JSON，不要添加额外解释或省略字段。"
        )

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": fix_prompt})

        logger.warning(
            "推理总字数不足（%d < 1200），触发第%d次纠偏: %s",
            total_reasoning_length,
            repair_attempt,
            candidate.title[:50],
        )
        continue  # ← 重新进入while循环

    # 如果已达最大重试次数，降级处理：记录WARNING但返回结果
    if total_reasoning_length < 1200:
        logger.warning(
            "推理总字数不足: %d < 1200（已达最大重试%d次），候选：%s",
            total_reasoning_length,
            constants.LLM_SELF_HEAL_MAX_ATTEMPTS,
            candidate.title[:50],
        )

    return extraction
```

**关键改动说明**：
1. **新增纠偏触发条件** (Line 681-706)：
   - 总长度<1200 且 未达最大重试次数 → 触发纠偏
   - 构造专门的"总长度不足"修复prompt（不同于单字段不足）
   - 追加到messages并`continue`重新进入循环

2. **降级处理** (Line 708-714)：
   - 如果已达最大重试次数（2次）仍不足
   - 记录详细WARNING（标注"已达最大重试"）
   - 返回结果（保证流程不中断）

3. **日志改进**：
   - 纠偏时记录当前字数、差距、重试次数
   - 降级时明确标注"已达最大重试"

---

## ✅ 测试验证

### 测试用例1：验证纠偏逻辑触发

**测试目标**：确认总推理长度不足时能触发第2次纠偏

**测试步骤**：
```bash
# 运行完整流程，观察日志
.venv/bin/python -m src.main 2>&1 | grep -E "(纠偏|推理总字数)"
```

**期望结果**：
```
[WARNING] LLM推理长度不足，触发第1次纠偏: XXX  # ← 单字段不足
[WARNING] 推理总字数不足（1120 < 1200），触发第2次纠偏: XXX  # ← 新增：总长度不足
[INFO] 批量评分完成: 成功1条/共1条  # ← 最终成功
```

### 测试用例2：验证降级处理

**测试目标**：确认最大重试2次后仍不足时能降级处理（不中断流程）

**期望结果**：
```
[WARNING] LLM推理长度不足，触发第1次纠偏: XXX
[WARNING] 推理总字数不足（1100 < 1200），触发第2次纠偏: XXX
[WARNING] 推理总字数不足: 1150 < 1200（已达最大重试2次），候选：XXX  # ← 降级
[INFO] 批量评分完成: 成功1条/共1条  # ← 不中断
```

### 测试用例3：验证正常流程不受影响

**测试目标**：确认总长度≥1200时不触发纠偏

**测试步骤**：
```bash
# 使用之前的测试脚本
.venv/bin/python scripts/test_writing_style.py 2>&1
```

**期望结果**：
```
✅ PASS - 总推理长度达标 (1484 ≥ 1200)
# 无纠偏日志
```

---

## 📊 预期效果

### 改进前 vs 改进后

| 场景 | 改进前 | 改进后 |
|------|--------|--------|
| 单字段<150 | ✅ 触发纠偏（最多2次） | ✅ 保持不变 |
| 总长度<1200 | ❌ 只WARNING，不纠偏 | ✅ 触发纠偏（最多2次） |
| 2次纠偏后仍不足 | ❌ 直接失败 | ✅ 降级处理，不中断流程 |
| 正常情况（≥1200） | ✅ 正常返回 | ✅ 保持不变 |

### 预期数据改善

**基于日志`1120 < 1200`（差80字符）的情况**：
- 改进前：触发1次纠偏后不足，直接返回
- 改进后：触发第2次纠偏，目标补足80字符，成功率≥80%

**总推理长度不足告警率**：
- 当前：约10-15%的候选出现告警
- 目标：降至<5%

---

## 🛡️ 代码质量要求

- ✅ **PEP8合规**：变量命名、空格、缩进
- ✅ **中文注释**：关键逻辑必须注释
- ✅ **向后兼容**：不影响现有单字段纠偏逻辑
- ✅ **错误处理**：降级处理确保流程不中断
- ✅ **嵌套层级≤3**（Linus规则）：当前代码已符合

---

## 📅 验收标准

| 验收项 | 标准 |
|--------|------|
| 代码编译 | ✅ `python -m py_compile src/scorer/llm_scorer.py` 通过 |
| 单元测试 | ✅ 运行`test_writing_style.py`，总长度≥1200 |
| 集成测试 | ✅ 运行完整流程，观察纠偏日志 |
| 告警率改善 | ✅ 总推理长度不足告警率<5% |
| 流程健壮性 | ✅ 2次纠偏后仍不足时不中断流程 |

---

**开发人员**: Codex
**文档编写**: Claude Code
**优先级**: 🔥 **HIGH** - 影响LLM评分质量
**预计工作量**: 30分钟
