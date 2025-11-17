# Phase 8: PDF 深度解析与数据增强效果报告

**版本**: v1.0（模板）  
**日期**: _TODO: 填写实际日期_  
**负责人**: _TODO: 填写执行人_  

---

## 1. 实验背景

- 目标：验证 Phase 8 PDF 深度解析能力是否显著提升数据质量（摘要长度、评估指标、基准模型、数据集规模、机构等字段覆盖率）。
- 对比基线：Phase 7（仅依赖 arXiv API 摘要 + GitHub README 正则抽取）。
- 主要改动：
  - 新增 `PDFEnhancer` 模块，对 arXiv 论文执行 PDF 下载与深度解析。
  - 在主流程 `src/main.py` 中插入 PDF 增强步骤（预筛选之后、LLM 评分之前）。
  - 更新 `LLMScorer` Prompt，加入 Evaluation / Dataset / Baselines 摘要三块 PDF 深度内容。

---

## 2. 实验环境

- 代码仓库：`BenchScope`  
- Git 分支 / Commit：
  - 分支：`_TODO: 如 feature/phase8-pdf-enhancement_`
  - Commit：`_TODO: git rev-parse HEAD_`
- 运行环境：
  - OS：_TODO: 例如 Ubuntu 22.04 / WSL2_
  - Python：`python --version` → _TODO_
  - 虚拟环境：`.venv`（基于 Python 3.11）
- 关键依赖版本：
  - `scipdf-parser==0.1rc1`
  - `arxiv`、`httpx`、`openai`、`redis` 等版本见 `requirements.txt`
- GROBID 部署方式：
  - _TODO: 云端默认服务 / 本地 Docker (`lfoppiano/grobid:0.8.0`)_  
- OpenAI / LLM 配置：
  - 模型：_TODO: 例如 gpt-4o-mini / 自建网关_
  - `OPENAI_API_KEY` / `OPENAI_BASE_URL`：已在 `.env.local` 中配置  

---

## 3. 实验流程与命令

### 3.1 环境初始化

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
python3.11 -m venv .venv          # 如已存在可跳过
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 单元测试（Day 4）

```bash
source .venv/bin/activate
python -m pytest tests/test_pdf_enhancer.py -v
```

需要记录：
- PDF 下载测试（`test_download_pdf`）是否稳定通过；
- arXiv 候选增强测试（`test_enhance_arxiv_candidate`）是否通过；
- 非 arXiv 候选降级行为（`test_enhance_non_arxiv_candidate`）是否符合预期。

### 3.3 主流程运行（Day 5）

```bash
source .venv/bin/activate

# 快速检查关键约束
bash scripts/quick_validation.sh

# 运行完整 Phase 8 流程
python -m src.main
```

记录内容：
- 本次运行时间区间（开始/结束时间）；
- 共采集候选数量 `N_total`；
- 去重后新候选数量 `N_dedup`；
- 预筛选通过数量 `N_filtered`；
- 其中 `source == "arxiv"` 的候选数量 `N_arxiv`；
- LLM 评分完成数量 `N_scored`。

### 3.4 数据质量分析

运行飞书数据质量分析脚本：

```bash
source .venv/bin/activate
python scripts/analyze_data_quality.py
```

从输出中记录：
- 各字段填充率（`发布日期 / 摘要 / 评估指标 / 基准模型 / 数据集规模 / 机构 / 作者 / 任务领域 / 数据集URL / GitHub URL`）
- 摘要过短（<100 字）记录数量；
- 其他异常（如发布日期异常）。

---

## 4. 字段覆盖率对比（Phase 7 → Phase 8）

> 说明：Phase 7 的基线数据可参考历史报告或之前运行 `analyze_data_quality.py` 的结果；Phase 8 的数据来自本次实验。

### 4.1 关键字段覆盖率

| 字段           | Phase 7 填充率 | Phase 8 填充率 | 提升幅度 | 备注                            |
|----------------|----------------|----------------|----------|---------------------------------|
| 摘要（≥500字） | _TODO: e.g. 5%_ | _TODO: e.g. 90%_ | _TODO_   | 统计摘要长度 ≥500 字的比例     |
| 评估指标       | 18.7%          | _TODO: ≥60%_   | _TODO_   | 来自 LLM + PDF Evaluation      |
| 基准模型       | 17.2%          | _TODO: ≥60%_   | _TODO_   | 来自 LLM + PDF Baselines       |
| 数据集规模     | 5.3%           | _TODO: ≥50%_   | _TODO_   | 来自 LLM + PDF Dataset         |
| 机构           | 0.5%           | _TODO: ≥70%_   | _TODO_   | 来自 PDF 作者 affiliation      |
| 数据集URL      | 6.2%           | _TODO: ≥30%_   | _TODO_   | README / 论文 / LLM 综合抽取   |
| GitHub URL     | 12.4%          | _TODO_         | _TODO_   | 受采集器影响，非 PDFEnhancer 核心 |

> 建议：将实际数值替换 `_TODO`，并附上 `analyze_data_quality.py` 的输出片段或截图。

### 4.2 摘要长度分布

- Phase 7：
  - 平均摘要长度：_TODO_ 字
  - 中位数摘要长度：_TODO_ 字
  - `<100` 字摘要占比：_TODO_ %
- Phase 8：
  - 平均摘要长度：_TODO_ 字
  - 中位数摘要长度：_TODO_ 字
  - `<100` 字摘要占比：_TODO_ %

可选：使用简单脚本或飞书导出 CSV 后在本地统计。

---

## 5. 典型样本分析

从飞书表或本地数据中选取 3–5 条具有代表性的样本，比较 Phase 7 vs Phase 8 的差异：

### 5.1 示例 1：高质量 arXiv Benchmark

- 标题：_TODO_
- 来源：arxiv + GitHub
- 变化：
  - 摘要：从 _TODO: 约 xx 字_ → _TODO: 约 xxxx 字_
  - 评估指标：从 _TODO: 无 / 少量_ → _TODO: 若干关键指标_
  - 基准模型：从 _TODO_ → _TODO_
  - 数据集规模：从 _TODO_ → _TODO_
  - 机构：从 _TODO_ → _TODO_

### 5.2 示例 2：仅有 arXiv 的论文

- 标题：_TODO_
- 观察：PDFEnhancer 是否单独就可以补齐绝大多数字段。

### 5.3 示例 3：GitHub-only 或非 Benchmark 条目

- 用于验证 PDFEnhancer 不会误伤非 arXiv 源，流程保持稳定。

---

## 6. 性能与成本评估

### 6.1 性能表现

在一次处理约 N 条候选（其中 M 条为 arXiv）的流程中统计：

| 指标                 | 实测数值    | 目标       | 备注                    |
|----------------------|-------------|------------|-------------------------|
| PDF 下载平均耗时     | _TODO_ 秒/篇 | <3 秒/篇   | 取 10 篇 arXiv 样本    |
| PDF 解析平均耗时     | _TODO_ 秒/篇 | <10 秒/篇  | GROBID 服务稳定情况下  |
| 单批完整流程耗时     | _TODO_ 分钟 | <30 分钟/50条 | 受 LLM 速率限制影响   |
| 峰值内存占用         | _TODO_ MB   | <1000 MB   | 可用 `top`/`htop` 观察 |

### 6.2 LLM 成本

按本次实验的规模估算：

| 项目             | 数值            | 备注                        |
|------------------|-----------------|-----------------------------|
| 样本数           | _TODO_ 条       | 通过预筛选并进入评分       |
| 平均输入 token   | _TODO_ tokens   | 包含 PDF 摘要内容          |
| 总 token 数      | _TODO_ tokens   |                             |
| 单价估算         | _TODO_ 元/1k tokens | 取所用模型官方价格     |
| 本次实验成本估算 | _TODO_ 元       |                             |
| 月度成本估算     | _TODO_ 元/月    | 按月处理规模折算           |

---

## 7. 问题与改进建议

### 7.1 遇到的问题

- _TODO: 例如 GROBID 云服务偶发超时、个别 PDF 解析失败、某些论文章节标题不规范导致关键词匹配不准等。_

### 7.2 改进建议

- _TODO: 例如_
  - 增加 `_extract_section_summary` 的章节名正则扩展；
  - 为 PDF 解析增加超时和重试机制；
  - 为 PDF 缓存添加定期清理脚本；
  - 收窄 LLM Prompt 体积（只保留必要片段）。

---

## 8. 结论与验收结果

- 功能层面：
  - [ ] PDFEnhancer 能稳定完成 arXiv PDF 的下载与解析。
  - [ ] LLM Prompt 成功接入 PDF 三大摘要部分。
  - [ ] 主流程在开启 Phase 8 后无崩溃、错误率 <5%。
- 数据质量：
  - [ ] 摘要长度 ≥500 字的比例达到 / 接近目标。
  - [ ] 评估指标 / 基准模型 / 数据集规模 / 机构 字段覆盖率达到 PRD 目标。
- 性能与成本：
  - [ ] 单篇 PDF 下载+解析耗时在可接受范围内。
  - [ ] 月度 LLM 成本在预算范围内（< ¥100 或团队约定值）。

**最终结论**:  
_TODO: 简要说明 Phase 8 是否达成预期目标，是否建议在生产环境默认启用。_

---

## 9. 操作记录与附件清单

- 运行记录：
  - _TODO: 填写本次实验实际执行的命令、起止时间、触发人（例如附上 `scripts/quick_validation.sh` 与 `python -m src.main` 的完整终端日志片段）。_
- 数据导出：
  - _TODO: 说明从飞书/SQLite 导出的数据表名称、导出时间、过滤条件，以及本地保存路径（例如 `exports/phase8_benchmarks_YYYYMMDD.csv`）。_
- 截图与样例：
  - _TODO: 附上典型样本（第 5 节中提到的几条）的飞书截图、PDF 解析结果对比截图等，用于非技术同学快速理解提升效果。_
- 配置快照：
  - _TODO: 记录关键配置文件的版本与修改点（如 `config/sources.yaml`、`src/common/constants.py` 中新增常量），方便后续复现与排查。_

> 建议：将本报告（Markdown）、导出数据、截图与日志打包放入同一文件夹，并在团队知识库中建立「Phase 8 PDF 增强」专栏，便于后续检索与复用。
