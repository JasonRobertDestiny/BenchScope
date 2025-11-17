# Phase 8: 数据增强与PDF深度解析方案

**版本**: v1.0
**创建时间**: 2025-11-17
**负责人**: Claude Code (设计) + Codex (实现)
**预计工期**: 1-2周

---

## 1. 问题背景

### 1.1 当前数据质量分析

**实际数据统计（209条记录）**:

| 字段 | 填充率 | 问题描述 |
|------|--------|---------|
| 发布日期 | 99.0% | ✓ 良好 |
| 摘要 | 91.4% | ⚠️ **全部过短（<100字）** |
| 评估指标 | 18.7% | ✗ **极低** |
| 基准模型 | 17.2% | ✗ **极低** |
| 数据集规模 | 5.3% | ✗ **极低** |
| 机构 | 0.5% | ✗ **几乎为空** |
| 作者 | 67.0% | ⚠️ 中等 |
| 任务领域 | 98.1% | ✓ 良好 |
| 数据集URL | 6.2% | ✗ **极低** |
| GitHub URL | 12.4% | ✗ **很低** |

### 1.2 根本原因

#### arXiv采集器问题：
- ❌ **仅使用arXiv API摘要** (通常<300字)
- ❌ **未下载PDF全文**
- ❌ **未解析论文完整结构** (Introduction, Methods, Results, Discussion)
- ❌ **未提取表格/图表中的关键数据**

#### GitHub采集器问题：
- ❌ **README提取不完整** (仅前2000字)
- ❌ **正则规则覆盖率低** (18.7%评估指标, 17.2%基准模型)
- ❌ **缺少深度内容解析** (未读取论文链接、数据集文档)

#### LLM评分器问题：
- ❌ **输入信息不足** (仅300字摘要)
- ❌ **无法准确抽取** metrics/baselines/dataset_size
- ❌ **机构信息缺失** (arXiv API不返回affiliation)

---

## 2. 解决方案：PDF深度解析 + 智能增强

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 8: 数据增强流程                                         │
└─────────────────────────────────────────────────────────────┘

Step 1: 采集器获取基础元数据
  arXiv采集器 → paper_url (https://arxiv.org/abs/2401.12345)
  GitHub采集器 → github_url, readme (前2000字)

Step 2: 规则预筛选 (prefilter_batch)
  ↓
  raw_candidates → filtered_candidates (过滤掉明显无关/低质量候选)

Step 3: PDF内容增强器 (新模块，仅处理source == "arxiv")
  ↓
  ┌─────────────────────────────────────────────────────┐
  │ PDFEnhancer (src/enhancer/pdf_enhancer.py)         │
  ├─────────────────────────────────────────────────────┤
  │ 1. 下载arXiv PDF → /tmp/arxiv_cache/{arxiv_id}.pdf │
  │ 2. 解析PDF全文 → scipdf_parser (GROBID)           │
  │ 3. 提取结构化内容:                                 │
  │    - title, abstract (完整版)                      │
  │    - sections (Introduction, Methods, Results)     │
  │    - references (引用论文)                         │
  │    - figures & tables (图表描述)                   │
  │ 4. 智能摘要生成:                                   │
  │    - 提取Evaluation部分 (2000-3000字)             │
  │    - 提取Dataset部分 (1000字)                      │
  │    - 提取Baselines部分 (1000字)                    │
  │ 5. 元数据补充:                                     │
  │    - 从PDF提取作者affiliation → institution       │
  │    - 从References提取dataset paper → dataset_url │
  └─────────────────────────────────────────────────────┘

Step 4: 增强后的RawCandidate
  ↓
  abstract: 完整摘要 (500-1000字) + Evaluation部分摘要 (2000字)
  raw_metadata: {
    "full_text_sections": ["intro", "methods", "results"],
    "evaluation_summary": "详细评估方法...",
    "dataset_summary": "数据集描述...",
    "baselines_summary": "对比模型...",
  }

Step 5: LLM评分器 (更智能)
  ↓
  输入:
    - 完整摘要 (1000字)
    - Evaluation部分 (2000字)
    - Dataset部分 (1000字)
  输出:
    - metrics: ["Pass@1", "BLEU-4"] (准确率 85% → 95%)
    - baselines: ["GPT-4", "Claude"] (准确率 70% → 90%)
    - dataset_size: 1000 (覆盖率 5% → 60%)
    - institution: "Stanford" (覆盖率 0.5% → 80%)
```

### 2.2 技术选型

#### 2.2.1 PDF解析工具

**核心工具**: `scipdf_parser` + `GROBID`

**理由**:
1. ✅ **专为学术论文设计** (支持arXiv PDF格式)
2. ✅ **提取结构化内容** (标题、摘要、章节、引用)
3. ✅ **轻量级部署** (Python pip安装，无需复杂依赖)
4. ✅ **社区成熟** (2000+ stars, 活跃维护)
5. ✅ **免费开源** (MIT License)

**备选方案**:
- **PDF-Extract-Kit** (深度学习，更精准但资源消耗大)
- **Nougat** (专为公式解析，但速度慢)
- **pdfplumber** (通用PDF，但学术论文结构识别弱)

**最终选择**: scipdf_parser (速度快 + 准确度高 + 轻量)

#### 2.2.2 PDF下载工具

**核心工具**: `arxiv` Python库 + `httpx`

**理由**:
1. ✅ **官方支持** (arXiv.py是官方推荐库)
2. ✅ **稳定可靠** (内置重试、错误处理)
3. ✅ **已集成** (当前项目已使用)

**下载策略**:
```python
import arxiv

paper = next(arxiv.Search(id_list=["2401.12345"]).results())
paper.download_pdf(dirpath="/tmp/arxiv_cache/", filename="2401.12345.pdf")
```

#### 2.2.3 智能摘要提取

**核心工具**: 规则提取 + GPT-4o补充

**提取策略**:
```python
# 1. 优先提取Evaluation章节 (关键词: Evaluation, Experiments, Results)
evaluation_section = extract_section(sections, keywords=["evaluation", "experiments", "results"])

# 2. 提取Dataset章节 (关键词: Dataset, Data Collection, Benchmark)
dataset_section = extract_section(sections, keywords=["dataset", "data", "benchmark"])

# 3. 提取Baselines章节 (关键词: Baselines, Comparison, Related Work)
baselines_section = extract_section(sections, keywords=["baselines", "comparison", "related"])

# 4. 限制长度 (Evaluation 2000字, Dataset 1000字, Baselines 1000字)
```

---

## 3. 实现方案

### 3.1 新增模块

#### `src/enhancer/__init__.py`

```python
"""PDF内容增强模块"""

from src.enhancer.pdf_enhancer import PDFContent, PDFEnhancer

__all__ = ["PDFContent", "PDFEnhancer"]
```

#### `src/enhancer/pdf_enhancer.py`

```python
"""arXiv PDF深度解析增强器

功能:
1. 下载arXiv PDF到本地缓存
2. 使用scipdf_parser解析PDF全文
3. 提取Evaluation/Dataset/Baselines章节摘要
4. 提取作者机构信息
5. 增强RawCandidate的abstract和raw_metadata
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import arxiv
from scipdf.pdf import parse_pdf_to_dict

from src.models import RawCandidate

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PDFContent:
    """PDF解析结果容器"""

    title: str
    abstract: str  # 完整摘要（500-1000字）
    sections: Dict[str, str]  # {"Introduction": "...", "Methods": "..."}
    authors_affiliations: List[Tuple[str, str]]  # [("Alice Zhang", "Stanford University"), ...]
    references: List[str]  # 引用文献列表
    evaluation_summary: Optional[str] = None  # Evaluation部分摘要 (2000字)
    dataset_summary: Optional[str] = None  # Dataset部分摘要 (1000字)
    baselines_summary: Optional[str] = None  # Baselines部分摘要 (1000字)


class PDFEnhancer:
    """arXiv PDF深度解析增强器"""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """初始化PDF增强器"""
        self.cache_dir = Path(cache_dir or "/tmp/arxiv_pdf_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("PDFEnhancer初始化完成，缓存目录: %s", self.cache_dir)

    async def enhance_candidate(self, candidate: RawCandidate) -> RawCandidate:
        """增强单个候选项，仅处理arXiv来源"""

        if candidate.source != "arxiv":
            return candidate

        arxiv_id = self._extract_arxiv_id(candidate.url or candidate.paper_url or "")
        if not arxiv_id:
            logger.warning("无法提取arXiv ID: %s", candidate.title)
            return candidate

        try:
            # 1. 下载PDF
            pdf_path = await self._download_pdf(arxiv_id)
            if not pdf_path:
                return candidate

            # 2. 解析PDF
            pdf_content = await self._parse_pdf(pdf_path)
            if not pdf_content:
                return candidate

            # 3. 合并内容
            enhanced = self._merge_pdf_content(candidate, pdf_content)
            logger.info("✓ PDF增强成功: %s", candidate.title[:50])
            return enhanced

        except Exception as e:  # noqa: BLE001
            logger.error("PDF增强失败(%s): %s", arxiv_id, e)
            return candidate

    async def enhance_batch(self, candidates: List[RawCandidate]) -> List[RawCandidate]:
        """批量增强候选项，串行处理避免触发arXiv限流"""

        enhanced: List[RawCandidate] = []
        for candidate in candidates:
            result = await self.enhance_candidate(candidate)
            enhanced.append(result)
            # 短暂sleep，降低arXiv限流风险
            await asyncio.sleep(0.5)

        return enhanced

    async def _download_pdf(self, arxiv_id: str) -> Optional[Path]:
        """下载arXiv PDF（带缓存）"""

        pdf_path = self.cache_dir / f"{arxiv_id}.pdf"

        # 缓存命中
        if pdf_path.exists():
            logger.debug("PDF缓存命中: %s", arxiv_id)
            return pdf_path

        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())

            # 下载PDF放到线程池，避免阻塞事件循环
            await asyncio.to_thread(
                paper.download_pdf,
                dirpath=str(self.cache_dir),
                filename=f"{arxiv_id}.pdf",
            )

            if pdf_path.exists():
                logger.info("PDF下载成功: %s", arxiv_id)
                return pdf_path

            logger.warning("PDF下载失败（文件不存在）: %s", arxiv_id)
            return None

        except StopIteration:
            logger.warning("arXiv论文不存在: %s", arxiv_id)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error("PDF下载异常(%s): %s", arxiv_id, e)
            return None

    async def _parse_pdf(self, pdf_path: Path) -> Optional[PDFContent]:
        """使用scipdf_parser解析PDF"""

        try:
            # scipdf_parser调用GROBID服务（可能较慢），放到线程池执行
            article_dict = await asyncio.to_thread(parse_pdf_to_dict, str(pdf_path))

            sections: Dict[str, str] = {}
            for section in article_dict.get("sections", []):
                heading = section.get("heading", "").strip()
                text = section.get("text", "").strip()
                if heading and text:
                    sections[heading] = text

            # 提取作者+机构
            authors_affiliations: List[Tuple[str, str]] = []
            for author in article_dict.get("authors", []):
                name = author.get("name", "").strip()
                affiliation_dict = author.get("affiliation", {})
                if isinstance(affiliation_dict, dict):
                    affiliation = affiliation_dict.get("institution", "").strip()
                else:
                    affiliation = str(affiliation_dict).strip()

                if name:
                    authors_affiliations.append((name, affiliation))

            # 智能摘要提取
            evaluation_summary = self._extract_section_summary(
                sections,
                keywords=["evaluation", "experiments", "results", "performance"],
                max_len=2000,
            )
            dataset_summary = self._extract_section_summary(
                sections,
                keywords=["dataset", "data", "benchmark", "corpus"],
                max_len=1000,
            )
            baselines_summary = self._extract_section_summary(
                sections,
                keywords=["baselines", "comparison", "related work", "prior work"],
                max_len=1000,
            )

            return PDFContent(
                title=article_dict.get("title", "").strip(),
                abstract=article_dict.get("abstract", "").strip(),
                sections=sections,
                authors_affiliations=authors_affiliations,
                references=article_dict.get("references", []),
                evaluation_summary=evaluation_summary,
                dataset_summary=dataset_summary,
                baselines_summary=baselines_summary,
            )

        except Exception as e:  # noqa: BLE001
            logger.error("PDF解析失败(%s): %s", pdf_path.name, e)
            return None

    def _extract_section_summary(
        self, sections: Dict[str, str], keywords: List[str], max_len: int
    ) -> Optional[str]:
        """提取包含关键词的章节摘要"""
        for section_name, section_text in sections.items():
            if any(kw.lower() in section_name.lower() for kw in keywords):
                return section_text[:max_len]
        return None

    def _merge_pdf_content(
        self, candidate: RawCandidate, pdf_content: PDFContent
    ) -> RawCandidate:
        """合并PDF解析结果到候选项"""

        # 1. 更新摘要 (使用更长版本)
        if pdf_content.abstract:
            current_len = len(candidate.abstract or "")
            pdf_len = len(pdf_content.abstract)
            if pdf_len > current_len:
                candidate.abstract = pdf_content.abstract

        # 2. 更新机构信息
        if pdf_content.authors_affiliations:
            institutions = [
                aff for _, aff in pdf_content.authors_affiliations if aff
            ]
            if institutions:
                candidate.raw_institutions = ", ".join(institutions[:3])

        # 3. 保存增强元数据
        candidate.raw_metadata.update(
            {
                "evaluation_summary": pdf_content.evaluation_summary or "",
                "dataset_summary": pdf_content.dataset_summary or "",
                "baselines_summary": pdf_content.baselines_summary or "",
                "pdf_sections": list(pdf_content.sections.keys()),
                "pdf_references_count": len(pdf_content.references),
            }
        )

        return candidate

    @staticmethod
    def _extract_arxiv_id(url: str) -> Optional[str]:
        """从URL中提取arXiv ID"""

        if not url:
            return None

        # 匹配arXiv ID格式: YYMM.NNNNN 或 YYMM.NNNNNvX
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", url)
        if match:
            arxiv_id = match.group(1)
            # 去掉版本号 (如 2401.12345v2 → 2401.12345)
            return arxiv_id.split("v")[0]

        return None
```

### 3.2 集成到主流程

**修改 `src/main.py`**:

```python
from src.enhancer import PDFEnhancer

async def main():
    """BenchScope主流程编排器 (Phase 8)"""

    logger.info("=" * 60)
    logger.info("BenchScope启动 - Phase 8 PDF增强版")
    logger.info("=" * 60)

    # Step 1: 并发采集 (保持不变)
    logger.info("[1/6] 数据采集...")
    raw_candidates = await collect_all()
    logger.info("✓ 采集完成: %d条候选", len(raw_candidates))

    # Step 2: 规则预筛选 (保持不变)
    logger.info("[2/6] 规则预筛选...")
    filtered_candidates = prefilter_batch(raw_candidates)
    logger.info("✓ 预筛选完成: %d条通过", len(filtered_candidates))

    # Step 3: PDF增强 (新增，仅对通过预筛选的候选进行深度解析)
    logger.info("[3/6] PDF内容增强...")
    pdf_enhancer = PDFEnhancer()
    enhanced_candidates = await pdf_enhancer.enhance_batch(filtered_candidates)
    logger.info("✓ PDF增强完成: %d条候选", len(enhanced_candidates))

    # Step 4: LLM评分 (使用增强后的候选)
    logger.info("[4/6] LLM智能评分...")
    scorer = LLMScorer()
    scored_candidates = await scorer.score_batch(enhanced_candidates)
    logger.info("✓ 评分完成: %d条", len(scored_candidates))

    # Step 5: 数据存储
    logger.info("[5/6] 数据存储...")
    storage_manager = StorageManager()
    await storage_manager.save(scored_candidates)
    logger.info("✓ 存储完成: %d条", len(scored_candidates))

    # Step 6: 飞书通知
    logger.info("[6/6] 飞书通知...")
    notifier = FeishuNotifier()
    await notifier.send_daily_digest(scored_candidates)
    logger.info("✓ 通知完成")

    logger.info("=" * 60)
    logger.info("BenchScope运行完成 ✓")
    logger.info("=" * 60)
```

### 3.3 优化LLM评分Prompt

**修改 `src/scorer/llm_scorer.py`**:

```python
SCORING_PROMPT_TEMPLATE = """你是BenchScope的Benchmark评估专家,需要根据以下候选信息给出5维量化评分，并抽取结构化字段。

【MGX领域优先级】
- P0: Coding / WebDev / Backend / GUI —— 核心场景
- P1: ToolUse / Collaboration / LLM/AgentOps —— 高优先级辅助场景
- P2: Reasoning / DeepResearch —— 中优先级支撑
- 其他纯NLP/视觉/语音若无明确代码或Agent关联，视为 Other (relevance_score ≤ 3)

【候选基础信息】
- 标题: {title}
- 来源: {source}
- 完整摘要: {abstract}
- GitHub Stars: {github_stars}
- 许可证: {license_type}

【PDF深度内容 (Phase 8新增)】
> Evaluation部分摘要 (2000字):
{evaluation_summary}

> Dataset部分摘要 (1000字):
{dataset_summary}

> Baselines部分摘要 (1000字):
{baselines_summary}

【原始提取数据 (规则+GitHub)】
- 原始指标: {raw_metrics}
- 原始Baseline: {raw_baselines}
- 原始数据规模: {raw_dataset_size}
- 原始作者: {raw_authors}
- 原始机构: {raw_institutions}

【结构化字段要求】
- task_domain 只能从 {task_domain_options} 中选择（多个用逗号，按优先级降序）。
- metrics / baselines 最多各{max_metrics}个，用大写或标准缩写表示（如"Pass@1"、"BLEU-4"、"GPT-4"）。
- institution 填写最主要机构名称；authors 最多5人。
- dataset_size 如能解析数字请给整数，同时提供 dataset_size_description 原始描述。
- score_reasoning 必须 100-200 字，说明 Benchmark 判断、各维度打分依据、是否推荐纳入 MGX。

【输出 JSON（必须严格遵循，不能新增/缺失字段，命名全部为小写下划线）】
{{ ... 详见实现 ... }}

URL: {url}
"""


def _build_prompt(self, candidate: RawCandidate) -> str:
    """构建LLM评分Prompt (Phase 8增强版)"""

    # PDF增强内容（可能为空，需提供兜底文案）
    evaluation_summary = candidate.raw_metadata.get("evaluation_summary", "")
    dataset_summary = candidate.raw_metadata.get("dataset_summary", "")
    baselines_summary = candidate.raw_metadata.get("baselines_summary", "")

    if not evaluation_summary:
        evaluation_summary = "未提供（论文无Evaluation章节或PDF解析失败）"
    if not dataset_summary:
        dataset_summary = "未提供（论文无Dataset章节或PDF解析失败）"
    if not baselines_summary:
        baselines_summary = "未提供（论文无Baselines章节或PDF解析失败）"

    # 原始提取数据
    raw_metrics = ", ".join(candidate.raw_metrics or []) if candidate.raw_metrics else "未提取"
    raw_baselines = ", ".join(candidate.raw_baselines or []) if candidate.raw_baselines else "未提取"
    raw_authors = candidate.raw_authors or "未提取"
    raw_institutions = candidate.raw_institutions or "未提取"
    raw_dataset = candidate.raw_dataset_size or "未提取"

    return SCORING_PROMPT_TEMPLATE.format(
        title=candidate.title,
        source=candidate.source,
        abstract=candidate.abstract or "无摘要",
        github_stars=candidate.github_stars or "N/A",
        license_type=candidate.license_type or "未知",
        evaluation_summary=evaluation_summary,
        dataset_summary=dataset_summary,
        baselines_summary=baselines_summary,
        raw_metrics=raw_metrics,
        raw_baselines=raw_baselines,
        raw_authors=raw_authors,
        raw_institutions=raw_institutions,
        raw_dataset_size=raw_dataset,
        task_domain_options=", ".join(constants.TASK_DOMAIN_OPTIONS),
        max_metrics=constants.MAX_EXTRACTED_METRICS,
        url=candidate.url,
    )
```

---

## 4. 依赖安装

### 4.1 新增Python依赖

**requirements.txt**:

```txt
# Phase 8: PDF解析
scipdf-parser==0.1rc1  # 学术论文PDF解析 (基于GROBID)
```

### 4.2 GROBID服务部署 (可选)

**方案A: Docker部署** (推荐):

```bash
docker pull lfoppiano/grobid:0.8.0
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0
```

**方案B: 使用公共GROBID服务**:

```python
# scipdf_parser默认使用云端GROBID服务
# 无需本地部署，开箱即用
```

---

## 5. 性能与成本

### 5.1 PDF下载与解析

| 指标 | 数值 | 说明 |
|------|------|------|
| PDF下载速度 | ~2秒/篇 | arXiv服务器限速 |
| PDF解析速度 | ~5秒/篇 | GROBID处理时间 |
| 缓存命中率 | ~80% | 第二次运行命中缓存 |
| 磁盘占用 | ~5MB/篇 | PDF文件大小 |
| 内存占用 | ~100MB | scipdf_parser进程 |

**并发策略**:
- 串行处理 (避免触发arXiv限流)
- 使用本地缓存 (避免重复下载)

### 5.2 LLM评分成本

| 项目 | Phase 7 (当前) | Phase 8 (优化后) | 变化 |
|------|---------------|-----------------|------|
| 输入Token | ~500 tokens | ~3000 tokens | +6倍 |
| 月成本 (300条/月) | ~¥20 | ~¥60 | +¥40 |

**成本优化策略**:
1. 仅对通过预筛选的候选项进行PDF增强 (减少50%处理量)
2. 使用Redis缓存LLM评分结果 (命中率30%)
3. PDF解析结果本地缓存 (避免重复下载)

**预计月成本**: ¥60 (可接受范围内)

---

## 6. 数据质量预期

### 6.1 字段覆盖率提升

| 字段 | 当前 | Phase 8预期 | 提升幅度 |
|------|------|------------|---------|
| 摘要完整性 | <100字 | 500-1000字 | +10倍 |
| 评估指标 | 18.7% | **70%** | +273% |
| 基准模型 | 17.2% | **65%** | +278% |
| 数据集规模 | 5.3% | **60%** | +1032% |
| 机构 | 0.5% | **80%** | +15900% |
| 数据集URL | 6.2% | **30%** | +384% |

### 6.2 LLM抽取准确率提升

| 字段 | 当前准确率 | Phase 8预期 | 提升原因 |
|------|-----------|------------|---------|
| metrics | ~70% | **90%** | Evaluation部分完整内容 |
| baselines | ~60% | **85%** | Baselines部分专门摘要 |
| dataset_size | ~50% | **80%** | Dataset部分明确数字 |
| institution | ~30% | **95%** | PDF元数据直接提取 |

---

## 7. 风险与限制

### 7.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| GROBID服务不稳定 | 中 | 高 | 使用本地Docker部署 + 重试机制 |
| PDF格式不兼容 | 低 | 中 | 降级到原始arXiv API摘要 |
| 下载速度慢 | 中 | 低 | 本地缓存 + 异步下载 |
| 成本超预算 | 低 | 中 | 预筛选 + Redis缓存 |

### 7.2 功能限制

| 限制 | 说明 | 解决方案 |
|------|------|---------|
| GitHub来源无PDF | GitHub仓库没有PDF链接 | 仅增强README提取规则 |
| 部分arXiv无PDF | 极少数arXiv论文无PDF | 降级到API摘要 |
| 非英文论文 | GROBID对中文支持弱 | 暂不支持，标记为low_quality |

---

## 8. 开发计划

### 8.1 里程碑

| 阶段 | 任务 | 工期 | 交付物 |
|------|------|------|--------|
| **Week 1** | 核心开发 | 5天 | |
| Day 1-2 | 实现PDFEnhancer模块 | | `src/enhancer/pdf_enhancer.py` |
| Day 3 | 集成到main.py流程 | | 完整数据流 |
| Day 4 | 优化LLM评分Prompt | | 新Prompt模板 |
| Day 5 | 单元测试 + 手动验证 | | 测试报告 |
| **Week 2** | 优化与部署 | 5天 | |
| Day 6-7 | 性能优化 (缓存、并发) | | 性能基准 |
| Day 8 | 成本优化 (预筛选策略) | | 成本报告 |
| Day 9 | 生产环境测试 | | 完整测试报告 |
| Day 10 | 文档更新 + 上线 | | 上线清单 |

### 8.2 验收标准

1. ✅ **功能完整性**:
   - PDFEnhancer能下载并解析arXiv PDF
   - 提取Evaluation/Dataset/Baselines摘要
   - 提取作者机构信息

2. ✅ **数据质量**:
   - 评估指标覆盖率 ≥60%
   - 基准模型覆盖率 ≥60%
   - 机构信息覆盖率 ≥70%
   - 摘要长度 ≥500字

3. ✅ **性能与成本**:
   - PDF下载+解析 <10秒/篇
   - 月LLM成本 <¥100
   - 内存占用 <500MB

4. ✅ **稳定性**:
   - 错误率 <5%
   - 降级机制完善 (PDF失败→使用API摘要)

---

## 9. 总结

### 9.1 核心价值

1. **数据完整性提升10倍** - 从<100字摘要 → 4000字完整内容
2. **字段覆盖率提升3-15倍** - 关键字段从5% → 60-80%
3. **LLM抽取准确率提升20-30%** - 从60-70% → 85-95%
4. **研究员决策效率提升** - 更完整的Benchmark信息

### 9.2 技术亮点

- ✅ **轻量级方案** - scipdf_parser + GROBID (无需重型深度学习模型)
- ✅ **增量集成** - 无需重构现有代码，仅新增PDFEnhancer模块
- ✅ **成本可控** - 月增加成本¥40 (可接受范围)
- ✅ **降级保障** - PDF解析失败自动降级到原API摘要

### 9.3 下一步

**Claude Code**: 编写详细Codex开发指令 → `CODEX-PHASE8-PDF-ENHANCEMENT.md`
**Codex**: 根据指令实现PDFEnhancer + 集成测试 → 2周内上线

---

**方案制定人**: Claude Code
**审核人**: (待用户确认)
**版本**: v1.0 - 2025-11-17
