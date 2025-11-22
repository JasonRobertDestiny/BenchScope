# Codex开发指令：修复arXiv去重窗口配置

## 文档元信息
- **创建时间**: 2025-11-22
- **创建者**: Claude Code
- **执行者**: Codex
- **优先级**: P1 (高优先级)
- **预计工作量**: 5分钟
- **前置依赖**: CODEX-DEDUP-OPTIMIZATION.md已完成

---

## 问题诊断

### 飞书数据分析结果（2025-11-22 22:25）

```
总记录: 365条
arXiv记录: 133条 (36.4%)
  - 最近7天: 133条 (100%)
  - 7-14天: 0条 (0%)
```

### 当前配置问题

**文件**: `src/common/constants.py` (第545-548行)
```python
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 7,      # ❌ 问题：与采集窗口完全重叠
    "default": 14,
}
```

**采集窗口**: `config/sources.yaml`
```yaml
arxiv:
  lookback_hours: 168  # 7天
```

### 根本原因

```
采集窗口 = 7天
去重窗口 = 7天
↓
完全重叠 = 100%去重率 = 0条新发现
```

**逻辑冲突**:
- 每天采集最近7天的论文
- 去重时对比最近7天的飞书历史
- 导致：今天采集的论文全部在昨天的7天窗口内 → 100%重复

---

## 解决方案

### 核心思路：错位窗口设计

**变更前**:
```
采集窗口: 7天
去重窗口: 7天
重叠率: 100%
```

**变更后**:
```
采集窗口: 7天 (保持不变)
去重窗口: 3天 (缩短)
重叠率: 42%
新发现: 4-7天前的论文 (预计30-50条/天)
```

**预期效果**:
- arXiv去重率: 100% → 30-50%
- arXiv新发现: 0条/天 → 30-50条/天
- 保留最近3天历史，允许4-7天论文通过

---

## 实施步骤

### Step 1: 修改去重窗口配置

**文件**: `src/common/constants.py`
**位置**: 第545-548行

**当前代码**:
```python
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 7,
    "default": DEDUP_LOOKBACK_DAYS,
}
```

**修改后代码**:
```python
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 3,  # arXiv采集7天，去重对比3天，保留4-7天新论文
    "default": DEDUP_LOOKBACK_DAYS,
}
```

**关键变化**:
- 第546行: `"arxiv": 7` → `"arxiv": 3`
- 新增注释说明逻辑

---

## 完整代码对比

### 修改前

```python
# src/common/constants.py (第545-548行)

DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 7,
    "default": DEDUP_LOOKBACK_DAYS,
}
```

### 修改后

```python
# src/common/constants.py (第545-548行)

DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 3,  # arXiv采集7天，去重对比3天，保留4-7天新论文
    "default": DEDUP_LOOKBACK_DAYS,
}
```

---

## 测试验证计划

### 测试1: 验证去重率下降

**运行命令**:
```bash
.venv/bin/python -m src.main 2>&1 | grep -E "arxiv.*去重率"
```

**预期输出**:
```
  arxiv          : XX条新发现 / 100条采集 (去重率30-50%)
```

**验收标准**:
- arXiv去重率 < 60% (之前100%)
- arXiv新发现 > 30条 (之前0条)

### 测试2: 验证窗口逻辑

**运行命令**:
```bash
.venv/bin/python -m src.main 2>&1 | grep -E "去重完成.*arxiv.*窗口"
```

**预期输出**:
```
去重完成: arxiv窗口3天, 其他窗口14天, 过滤XXX条重复, 保留XXX条新发现
```

**验收标准**:
- 日志显示arXiv使用3天窗口
- 其他来源仍使用14天窗口

### 测试3: 完整流程验证

**运行命令**:
```bash
.venv/bin/python -m src.main
```

**验收标准**:
- 流程正常完成
- arXiv有新发现
- 飞书推送包含arXiv来源
- 无报错

---

## 成功标准和检查清单

### 代码修改检查
- [ ] `src/common/constants.py` 第546行已修改 (7→3)
- [ ] 新增注释说明窗口逻辑
- [ ] 代码符合PEP8规范

### 功能验证检查
- [ ] arXiv去重率显著下降 (<60%)
- [ ] arXiv有新发现 (>30条)
- [ ] 日志显示arXiv使用3天窗口
- [ ] 其他来源仍使用14天窗口

### 性能验证检查
- [ ] 去重速度未明显变化
- [ ] 飞书API调用次数未增加
- [ ] 日志输出清晰

---

## 风险评估与缓解

### 风险1: 可能重复入库旧数据

**风险**: 3天前的旧论文可能被重新入库
**概率**: 极低 (arXiv采集窗口只有7天，3天外的论文只有4-7天前)
**缓解**: 这是预期行为，正是要保留4-7天的新论文

### 风险2: 3天窗口可能过短

**风险**: 某些场景下3天窗口不够
**概率**: 低
**缓解**: 配置化设计，可快速调整为5天或10天

---

## 后续微调建议

### 优化1: 监控新发现数量

运行1-2天后，根据实际新发现数量微调窗口：
- 如果新发现<20条/天 → 缩短到2天
- 如果新发现>70条/天 → 扩大到5天

### 优化2: 按需调整其他来源

如果HuggingFace/GitHub出现类似问题，可单独设置：
```python
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 3,
    "huggingface": 7,  # HF采集14天，去重7天
    "github": 15,      # GitHub采集30天，去重15天
    "default": 14,
}
```

---

## 参考信息

### arXiv采集配置

**文件**: `config/sources.yaml`
```yaml
arxiv:
  enabled: true
  max_results: 50
  lookback_hours: 168  # 7天窗口
```

### 当前飞书数据分布

| 时间段 | 记录数 | 占比 |
|-------|--------|------|
| 7天内 | 176条 | 48.2% |
| 7-14天 | 16条 | 4.4% |
| 14-30天 | 13条 | 3.6% |

**arXiv数据**:
- 总数: 133条
- 7天内: 133条 (100%)
- 7-14天: 0条 (0%) ← 验证了100%去重率的原因

---

**文档结束**
