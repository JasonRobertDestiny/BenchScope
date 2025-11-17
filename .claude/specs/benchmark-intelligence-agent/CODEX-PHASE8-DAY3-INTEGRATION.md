# Phase 8 Day 3: PDFEnhancer集成指令

**任务范围**: 将Day 1-2完成的PDFEnhancer模块集成到主流程

**预计工期**: 2-3小时

---

## 1. 任务清单

- [ ] 修改 `src/main.py` - 插入PDF增强步骤
- [ ] 修改 `src/scorer/llm_scorer.py` - 更新LLM评分Prompt
- [ ] 更新 `requirements.txt` - 添加scipdf-parser依赖
- [ ] 运行完整流程测试 - 验证集成成功

---

## 2. 文件修改详情

### 2.1 修改 `src/main.py`

**位置**: 在预筛选之后、LLM评分之前插入PDF增强步骤

**具体修改**:

```python
# 在文件顶部import区域添加
from src.enhancer import PDFEnhancer

# 在main()函数中，找到Step 2 预筛选之后的位置
# 原代码:
# Step 2: 规则预筛选
logger.info("[2/5] 规则预筛选...")
filtered_candidates = prefilter_batch(all_candidates)
logger.info("✓ 预筛选完成: %d条候选 (过滤掉 %d条)", len(filtered_candidates), len(all_candidates) - len(filtered_candidates))

# Step 3: LLM评分 (原来的代码)
logger.info("[3/5] LLM评分...")
scorer = LLMScorer()
scored_candidates = await scorer.score_batch(filtered_candidates)

# 修改为:
# Step 2: 规则预筛选
logger.info("[2/6] 规则预筛选...")
filtered_candidates = prefilter_batch(all_candidates)
logger.info("✓ 预筛选完成: %d条候选 (过滤掉 %d条)", len(filtered_candidates), len(all_candidates) - len(filtered_candidates))

# Step 3: PDF内容增强 (新增)
logger.info("[3/6] PDF内容增强...")
pdf_enhancer = PDFEnhancer()
enhanced_candidates = await pdf_enhancer.enhance_batch(filtered_candidates)
arxiv_count = sum(1 for c in filtered_candidates if c.source == "arxiv")
logger.info("✓ PDF增强完成: %d条候选 (其中arXiv %d条)", len(enhanced_candidates), arxiv_count)

# Step 4: LLM评分 (原Step 3)
logger.info("[4/6] LLM评分...")
scorer = LLMScorer()
scored_candidates = await scorer.score_batch(enhanced_candidates)  # 使用增强后的候选
logger.info("✓ LLM评分完成: %d条", len(scored_candidates))

# 后续步骤编号相应调整:
# Step 5: 存储管理器 (原Step 4)
logger.info("[5/6] 存储...")

# Step 6: 飞书通知 (原Step 5)
logger.info("[6/6] 飞书通知...")
```

**注意事项**:
- 所有后续步骤的编号从 `[3/5]` 改为 `[4/6]`, `[4/5]` 改为 `[5/6]`, `[5/5]` 改为 `[6/6]`
- 使用 `enhanced_candidates` 而不是 `filtered_candidates` 传给LLM评分器
- 添加日志显示arXiv候选数量（方便验证PDF增强是否正常工作）

---

### 2.2 修改 `src/scorer/llm_scorer.py`

**目标**: 更新LLM评分Prompt，包含PDF深度内容

**具体修改**:

#### 步骤1: 更新 `SCORING_PROMPT_TEMPLATE`

找到原来的Prompt模板（约在第25-78行），在"【候选信息】"部分之后添加PDF深度内容：

```python
SCORING_PROMPT_TEMPLATE = """你是BenchScope的Benchmark评估专家，专门识别AI/Agent/Coding/Backend领域的高质量评测基准。

【候选信息】
- 标题: {title}
- 来源: {source}
- 摘要: {abstract}
- 原始指标: {raw_metrics}
- 原始Baseline: {raw_baselines}
- 原始作者: {raw_authors}
- 原始机构: {raw_institutions}
- 原始数据规模: {raw_dataset_size}

【PDF深度内容 (Phase 8新增)】
> Evaluation部分摘要 (2000字):
{evaluation_summary}

> Dataset部分摘要 (1000字):
{dataset_summary}

> Baselines部分摘要 (1000字):
{baselines_summary}

【评分任务】
请根据以上信息，为该候选Benchmark打分，并补充缺失字段。

... (后续Prompt内容保持不变)
"""
```

#### 步骤2: 修改 `_build_prompt()` 方法

找到 `_build_prompt()` 方法（约在第80-120行），添加PDF内容提取逻辑：

```python
def _build_prompt(self, candidate: RawCandidate) -> str:
    """构建评分Prompt"""

    # 提取PDF增强内容 (如果存在)
    raw_metadata = candidate.raw_metadata or {}
    evaluation_summary = raw_metadata.get("evaluation_summary", "")
    dataset_summary = raw_metadata.get("dataset_summary", "")
    baselines_summary = raw_metadata.get("baselines_summary", "")

    # 如果PDF解析失败，提供fallback消息
    if not evaluation_summary:
        evaluation_summary = "未提供（论文无Evaluation章节或PDF解析失败）"
    if not dataset_summary:
        dataset_summary = "未提供（论文无Dataset章节或PDF解析失败）"
    if not baselines_summary:
        baselines_summary = "未提供（论文无Baselines章节或PDF解析失败）"

    # 原有字段提取逻辑保持不变
    abstract = candidate.abstract or "无摘要"
    raw_metrics = ", ".join(candidate.raw_metrics) if candidate.raw_metrics else "未提供"
    raw_baselines = ", ".join(candidate.raw_baselines) if candidate.raw_baselines else "未提供"
    raw_authors = candidate.raw_authors or "未提供"
    raw_institutions = candidate.raw_institutions or "未提供"
    raw_dataset_size = candidate.raw_dataset_size or "未提供"

    # 填充Prompt模板
    prompt = SCORING_PROMPT_TEMPLATE.format(
        title=candidate.title,
        source=candidate.source,
        abstract=abstract,
        raw_metrics=raw_metrics,
        raw_baselines=raw_baselines,
        raw_authors=raw_authors,
        raw_institutions=raw_institutions,
        raw_dataset_size=raw_dataset_size,
        # 新增PDF内容字段
        evaluation_summary=evaluation_summary,
        dataset_summary=dataset_summary,
        baselines_summary=baselines_summary,
    )

    return prompt
```

**关键点**:
- 从 `candidate.raw_metadata` 提取3个summary字段
- 如果字段为空，提供清晰的fallback消息（告诉LLM这是正常情况）
- 保持原有字段提取逻辑不变

---

### 2.3 更新 `requirements.txt`

在文件末尾添加：

```txt
# PDF解析 (Phase 8)
scipdf-parser==0.52  # 学术论文PDF解析 (基于GROBID)
```

**注意**:
- scipdf-parser依赖Java环境（GROBID服务）
- 首次运行会自动下载GROBID模型（约200MB）
- 也可以使用云端GROBID服务，无需本地安装

---

## 3. 集成测试

### 3.1 安装依赖

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
.venv/bin/pip install scipdf-parser==0.1rc1
```

### 3.2 运行完整流程

```bash
.venv/bin/python -m src.main
```

### 3.3 验证点

**日志检查**:
```
[1/6] 数据采集...
✓ 采集完成: XX条

[2/6] 规则预筛选...
✓ 预筛选完成: XX条候选 (过滤掉 XX条)

[3/6] PDF内容增强...
✓ PDF增强完成: XX条候选 (其中arXiv XX条)  ← 新增步骤

[4/6] LLM评分...
✓ LLM评分完成: XX条

[5/6] 存储...
✓ 存储完成

[6/6] 飞书通知...
✓ 飞书通知完成
```

**关键验证**:
1. ✅ PDF增强步骤正常执行（日志中有"[3/6] PDF内容增强..."）
2. ✅ arXiv候选数量 > 0（说明有PDF需要解析）
3. ✅ LLM评分步骤正常完成（使用增强后的候选）
4. ✅ 无崩溃或异常错误

### 3.4 数据质量验证

运行数据质量分析脚本：

```bash
.venv/bin/python scripts/analyze_data_quality.py
```

**期望改进** (对比Phase 7基线):

| 字段 | Phase 7 | Phase 8目标 | 改进幅度 |
|------|---------|------------|---------|
| 摘要长度 | <100字 | 500-1000字 | +10x |
| 评估指标覆盖率 | 18.7% | 70% | +273% |
| 基准模型覆盖率 | 17.2% | 65% | +278% |
| 数据集规模覆盖率 | 5.3% | 60% | +1032% |
| 机构覆盖率 | 0.5% | 80% | +15900% |

---

## 4. 常见问题处理

### Q1: scipdf-parser安装失败

**症状**: `pip install scipdf-parser` 报错

**解决**:
```bash
# 方法1: 使用云端GROBID服务（推荐）
# 在pdf_enhancer.py中设置GROBID URL
export GROBID_URL="https://kermitt2-grobid.hf.space"

# 方法2: 本地安装GROBID (需要Java 11+)
# 下载GROBID: https://github.com/kermitt2/grobid/releases
# 启动服务: java -jar grobid-core-0.7.3.jar
```

### Q2: PDF下载超时

**症状**: `asyncio.TimeoutError` 或 arXiv API限流

**解决**:
- PDF下载已有30秒超时（`src/enhancer/pdf_enhancer.py` 中设置）
- 超时会graceful degradation（返回原始候选）
- 建议保持串行处理 + 0.5s sleep（避免触发arXiv限流）

### Q3: LLM Token超限

**症状**: OpenAI API返回 `context_length_exceeded`

**解决**:
- 当前设计已限制section summary长度（Evaluation 2000字, Dataset 1000字, Baselines 1000字）
- 如仍超限，可在 `pdf_enhancer.py` 中缩短 `_extract_section_summary` 返回的字符数

### Q4: PDF解析全部失败

**症状**: 日志显示 "PDF增强完成" 但所有候选都是 "未提供（PDF解析失败）"

**排查**:
1. 检查scipdf-parser是否正确安装
2. 检查GROBID服务是否可用
3. 检查PDF下载是否成功（查看 `/tmp/arxiv_pdf_cache` 目录）
4. 查看详细错误日志

---

## 5. 完成标准

Day 3任务完成需满足：

- [ ] `src/main.py` 已修改，PDF增强步骤正确插入
- [ ] `src/scorer/llm_scorer.py` 已修改，Prompt包含PDF深度内容
- [ ] `requirements.txt` 已更新，包含scipdf-parser依赖
- [ ] 完整流程运行成功，日志显示6个步骤
- [ ] 至少1个arXiv候选成功下载并解析PDF（日志中无严重错误）
- [ ] LLM评分正常完成（使用增强后的候选）
- [ ] 数据写入飞书表格成功

**验收方式**:
1. 运行 `python -m src.main` 成功完成
2. 检查日志文件，确认6个步骤全部执行
3. 运行 `scripts/analyze_data_quality.py`，观察字段覆盖率是否提升
4. 将测试结果写入 `docs/phase8-day3-test-report.md`

---

## 6. 下一步 (Day 4预告)

Day 3完成后，Day 4任务：

- 编写单元测试 `tests/test_pdf_enhancer.py`
- 编写集成测试 `tests/test_integration.py`
- 手动测试5-10个真实arXiv论文
- 生成详细测试报告

---

**开发时间**: 预计2-3小时
**开发者**: Codex
**监督**: Claude Code (你负责验收)
