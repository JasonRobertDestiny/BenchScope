# Codex开发指令: Phase 8 PDF深度解析与数据增强

**目标**: 实现arXiv PDF深度解析，提升数据质量10倍
**工期**: 1-2周
**负责人**: Codex
**设计人**: Claude Code

---

## 📋 任务概览

你需要实现Phase 8的PDF深度解析功能，解决当前数据质量问题：
- ❌ 摘要过短（<100字）→ ✅ 完整摘要（500-1000字）
- ❌ 评估指标覆盖率18.7% → ✅ 70%
- ❌ 基准模型覆盖率17.2% → ✅ 65%
- ❌ 数据集规模覆盖率5.3% → ✅ 60%
- ❌ 机构信息覆盖率0.5% → ✅ 80%

---

## 🎯 项目上下文

### 当前架构（Phase 7）

```
数据流:
arXiv API → RawCandidate (摘要<300字) → LLM评分 → ScoredCandidate → 飞书表格
           ↑ 问题：摘要太短，LLM无法准确抽取指标/Baseline/规模
```

### Phase 8目标架构

```
数据流:
arXiv API → RawCandidate → PDFEnhancer → 增强RawCandidate → LLM评分 → ScoredCandidate
                           ↓ (新增)
                     下载PDF → 解析完整内容 (4000字)
                     提取Evaluation/Dataset/Baselines章节
                     提取作者机构信息
```

---

## 📁 项目结构

```
BenchScope/
├── src/
│   ├── enhancer/                    # 新增模块
│   │   ├── __init__.py
│   │   └── pdf_enhancer.py          # 核心实现 (你需要创建)
│   ├── collectors/
│   │   ├── arxiv_collector.py       # 已存在，提供paper_url
│   │   └── github_collector.py      # 已存在，无需修改
│   ├── scorer/
│   │   └── llm_scorer.py            # 需要修改Prompt
│   ├── models.py                    # 需要理解数据结构
│   ├── config.py                    # 配置管理
│   └── main.py                      # 需要集成PDFEnhancer
├── requirements.txt                 # 需要添加依赖
├── config/
│   └── sources.yaml                 # 配置文件
└── tests/                           # 测试文件
    └── test_pdf_enhancer.py         # 你需要创建
```

---

## 🔧 详细实现

### Step 1: 安装依赖

**修改 `requirements.txt`**:

```txt
# 在文件末尾添加:
# Phase 8: PDF深度解析
scipdf-parser==0.52  # 学术论文PDF解析 (基于GROBID)
```

**安装命令**:

```bash
uv pip install scipdf-parser==0.52
```

**验证安装**:

```bash
/mnt/d/VibeCoding_pgm/BenchScope/.venv/bin/python -c "from scipdf.pdf import parse_pdf_to_dict; print('✓ scipdf_parser安装成功')"
```

---

### Step 2: 创建PDF增强器模块

**创建文件 `src/enhancer/__init__.py`**:

```python
"""PDF内容增强模块"""

from src.enhancer.pdf_enhancer import PDFEnhancer, PDFContent

__all__ = ["PDFEnhancer", "PDFContent"]
```

**创建文件 `src/enhancer/pdf_enhancer.py`**:

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

from src.common import constants
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
    """arXiv PDF深度解析增强器

    使用场景:
    - arXiv来源的候选项 (source == "arxiv")
    - 通过预筛选的候选项 (减少不必要的PDF下载)

    不适用:
    - GitHub来源 (无PDF链接)
    - HELM来源 (无PDF链接)
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """初始化PDF增强器

        Args:
            cache_dir: PDF缓存目录，默认为 /tmp/arxiv_pdf_cache
        """
        self.cache_dir = Path(cache_dir or "/tmp/arxiv_pdf_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("PDFEnhancer初始化完成，缓存目录: %s", self.cache_dir)

    async def enhance_candidate(self, candidate: RawCandidate) -> RawCandidate:
        """增强单个候选项

        Args:
            candidate: 原始候选项

        Returns:
            增强后的候选项（如果失败则返回原候选项）
        """
        # 仅处理arXiv来源
        if candidate.source != "arxiv":
            return candidate

        # 提取arXiv ID
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
        """批量增强候选项

        Args:
            candidates: 候选项列表

        Returns:
            增强后的候选项列表
        """
        # 串行处理（避免触发arXiv限流）
        enhanced = []
        for candidate in candidates:
            result = await self.enhance_candidate(candidate)
            enhanced.append(result)
            # 添加短暂延迟，避免请求过快
            await asyncio.sleep(0.5)

        arxiv_count = sum(1 for c in candidates if c.source == "arxiv")
        logger.info(
            "批量增强完成: %d条候选项 (%d条arXiv)", len(enhanced), arxiv_count
        )
        return enhanced

    async def _download_pdf(self, arxiv_id: str) -> Optional[Path]:
        """下载arXiv PDF（带缓存）

        Args:
            arxiv_id: arXiv论文ID (如 "2401.12345")

        Returns:
            PDF文件路径，失败返回None
        """
        pdf_path = self.cache_dir / f"{arxiv_id}.pdf"

        # 缓存命中
        if pdf_path.exists():
            logger.debug("PDF缓存命中: %s", arxiv_id)
            return pdf_path

        # 下载PDF
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())

            # 下载PDF（arxiv库会自动处理）
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
        """使用scipdf_parser解析PDF

        Args:
            pdf_path: PDF文件路径

        Returns:
            PDFContent对象，失败返回None
        """
        try:
            # scipdf_parser调用GROBID服务（可能较慢）
            from scipdf.pdf import parse_pdf_to_dict

            article_dict = await asyncio.to_thread(parse_pdf_to_dict, str(pdf_path))

            # 提取章节内容
            sections = {}
            for section in article_dict.get("sections", []):
                heading = section.get("heading", "").strip()
                text = section.get("text", "").strip()
                if heading and text:
                    sections[heading] = text

            # 提取作者+机构
            authors_affiliations = []
            for author in article_dict.get("authors", []):
                name = author.get("name", "").strip()
                affiliation_dict = author.get("affiliation", {})
                if isinstance(affiliation_dict, dict):
                    affiliation = affiliation_dict.get("institution", "").strip()
                else:
                    affiliation = str(affiliation_dict).strip()

                if name:
                    authors_affiliations.append((name, affiliation))

            # 智能章节摘要提取
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
        """从章节中提取包含关键词的摘要

        Args:
            sections: 章节字典 {"Introduction": "...", "Methods": "..."}
            keywords: 关键词列表 ["evaluation", "experiments"]
            max_len: 最大摘要长度

        Returns:
            章节摘要文本，未找到返回None
        """
        for section_name, section_text in sections.items():
            # 检查章节标题是否包含关键词
            if any(kw.lower() in section_name.lower() for kw in keywords):
                # 截断到max_len字符
                summary = section_text[:max_len]
                logger.debug(
                    "提取章节摘要: %s (%d字)", section_name, len(summary)
                )
                return summary

        return None

    def _merge_pdf_content(
        self, candidate: RawCandidate, pdf_content: PDFContent
    ) -> RawCandidate:
        """合并PDF解析结果到候选项

        Args:
            candidate: 原始候选项
            pdf_content: PDF解析结果

        Returns:
            增强后的候选项
        """
        # 1. 更新摘要（使用更完整的版本）
        if pdf_content.abstract:
            current_len = len(candidate.abstract or "")
            pdf_len = len(pdf_content.abstract)
            if pdf_len > current_len:
                candidate.abstract = pdf_content.abstract
                logger.debug("摘要更新: %d字 → %d字", current_len, pdf_len)

        # 2. 更新机构信息
        if pdf_content.authors_affiliations:
            institutions = [
                aff for _, aff in pdf_content.authors_affiliations if aff
            ]
            if institutions:
                # 保留前3个机构
                candidate.raw_institutions = ", ".join(institutions[:3])
                logger.debug("机构信息提取: %d个", len(institutions))

        # 3. 保存增强元数据到raw_metadata
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
        """从URL中提取arXiv ID

        Args:
            url: arXiv URL (如 "https://arxiv.org/abs/2401.12345")

        Returns:
            arXiv ID (如 "2401.12345")，提取失败返回None
        """
        if not url:
            return None

        # 匹配arXiv ID格式: YYMM.NNNNN 或 YYMM.NNNNNV
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", url)
        if match:
            arxiv_id = match.group(1)
            # 移除版本号 (如 "2401.12345v2" → "2401.12345")
            return arxiv_id.split("v")[0]

        return None
```

---

### Step 3: 集成到主流程

**修改 `src/main.py`**:

在主函数中添加PDF增强步骤（在预筛选之后、LLM评分之前）：

```python
# 在文件头部添加import
from src.enhancer import PDFEnhancer

# 在main()函数中修改
async def main():
    """BenchScope主流程编排器"""

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

    # Step 3: PDF增强 (新增)
    logger.info("[3/6] PDF内容增强...")
    pdf_enhancer = PDFEnhancer()
    enhanced_candidates = await pdf_enhancer.enhance_batch(filtered_candidates)
    logger.info("✓ PDF增强完成: %d条候选", len(enhanced_candidates))

    # Step 4: LLM评分 (使用增强后的候选)
    logger.info("[4/6] LLM智能评分...")
    scorer = LLMScorer()
    scored_candidates = await scorer.score_batch(enhanced_candidates)
    logger.info("✓ 评分完成: %d条", len(scored_candidates))

    # Step 5-6: 存储+通知 (保持不变)
    logger.info("[5/6] 数据存储...")
    storage_manager = StorageManager()
    await storage_manager.save(scored_candidates)
    logger.info("✓ 存储完成: %d条", len(scored_candidates))

    logger.info("[6/6] 飞书通知...")
    notifier = FeishuNotifier()
    await notifier.send_daily_digest(scored_candidates)
    logger.info("✓ 通知完成")

    logger.info("=" * 60)
    logger.info("BenchScope运行完成 ✓")
    logger.info("=" * 60)
```

---

### Step 4: 优化LLM评分Prompt

**修改 `src/scorer/llm_scorer.py`**:

更新Prompt模板，包含PDF增强内容：

```python
# 在文件开头修改SCORING_PROMPT_TEMPLATE (约第25-78行)

SCORING_PROMPT_TEMPLATE = """你是BenchScope的Benchmark评估专家,需要根据以下候选信息给出5维量化评分，并抽取结构化字段。

【MGX领域优先级】
- P0: Coding / WebDev / Backend / GUI  —— 核心场景
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

【评分维度（必须全部返回，0-10分）】
1. 活跃度 activity_score —— GitHub stars、近期提交、社区讨论；可按提示阈值加减分。
2. 可复现性 reproducibility_score —— 数据/代码/评估脚本/指标/基准结果的公开程度。
3. 许可合规 license_score —— MIT/Apache=10，GPL≈7，CC≈4，未知/专有≤2。
4. 新颖性 novelty_score —— 任务或指标是否创新，是否2024+发布，是否补位 MGX 场景空白。
5. MGX适配度 relevance_score —— 明确候选归属的任务领域(P0/P1/P2/Other)，并结合评测指标/场景说明原因。

【结构化字段要求】
- task_domain 只能从 {task_domain_options} 中选择（多个用逗号，按优先级降序）。
- metrics / baselines 最多各{max_metrics}个，用大写或标准缩写表示（如"Pass@1"、"BLEU-4"、"GPT-4"）。
- institution 填写最主要机构名称；authors 最多5人，形如["Alice Zhang", "Bob Li"]。
- dataset_size 如能解析数字请给整数，同时提供 dataset_size_description 原始描述。
- score_reasoning 必须 100-200 字，说明 Benchmark 判断、各维度打分依据、是否推荐纳入 MGX（总分≥6.5且 relevance≥7 推荐）。

【输出 JSON（必须严格遵循，不能新增/缺失字段，命名全部为小写下划线）】
{{
  "activity_score": float,
  "reproducibility_score": float,
  "license_score": float,
  "novelty_score": float,
  "relevance_score": float,
  "score_reasoning": "100-200字中文说明",
  "task_domain": "Coding" | "Coding,ToolUse" | ... | "Other",
  "metrics": ["Pass@1", "BLEU-4"],
  "baselines": ["GPT-4", "Claude-3.5-Sonnet"],
  "institution": "Stanford University",
  "authors": ["Alice Zhang", "Bob Li"],
  "dataset_size": 1000,
  "dataset_size_description": "1000 coding problems"
}}
若某字段无可靠信息，请返回 null（不要删除键）。切勿输出 is_benchmark 等未定义字段，切勿在 JSON 前后附加文字。

URL: {url}
"""

# 修改_build_prompt方法 (约第200-230行)
def _build_prompt(self, candidate: RawCandidate) -> str:
    """构建LLM评分Prompt (Phase 8增强版)"""

    # 提取PDF增强内容
    evaluation_summary = candidate.raw_metadata.get("evaluation_summary", "")
    dataset_summary = candidate.raw_metadata.get("dataset_summary", "")
    baselines_summary = candidate.raw_metadata.get("baselines_summary", "")

    # 格式化为可读文本
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

### Step 5: 测试用例

**创建文件 `tests/test_pdf_enhancer.py`**:

```python
"""PDFEnhancer单元测试"""

import asyncio
from pathlib import Path

import pytest

from src.enhancer import PDFEnhancer
from src.models import RawCandidate


@pytest.fixture
def pdf_enhancer():
    """创建PDFEnhancer实例"""
    return PDFEnhancer(cache_dir="/tmp/test_arxiv_cache")


@pytest.mark.asyncio
async def test_extract_arxiv_id():
    """测试arXiv ID提取"""
    enhancer = PDFEnhancer()

    # 测试各种URL格式
    assert enhancer._extract_arxiv_id("https://arxiv.org/abs/2401.12345") == "2401.12345"
    assert enhancer._extract_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345"
    assert enhancer._extract_arxiv_id("https://arxiv.org/pdf/2401.12345.pdf") == "2401.12345"
    assert enhancer._extract_arxiv_id("invalid_url") is None


@pytest.mark.asyncio
async def test_download_pdf(pdf_enhancer):
    """测试PDF下载（使用真实arXiv论文）"""

    # 使用已知存在的arXiv论文
    arxiv_id = "2303.08774"  # GPT-4 Technical Report

    pdf_path = await pdf_enhancer._download_pdf(arxiv_id)

    assert pdf_path is not None
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"


@pytest.mark.asyncio
async def test_enhance_arxiv_candidate(pdf_enhancer):
    """测试arXiv候选项增强"""

    # 创建测试候选项
    candidate = RawCandidate(
        title="GPT-4 Technical Report",
        url="https://arxiv.org/abs/2303.08774",
        source="arxiv",
        abstract="Short abstract...",  # 短摘要
        paper_url="https://arxiv.org/abs/2303.08774",
        raw_metadata={},
    )

    # 增强候选项
    enhanced = await pdf_enhancer.enhance_candidate(candidate)

    # 验证增强效果
    assert len(enhanced.abstract) > len(candidate.abstract)  # 摘要变长
    assert "evaluation_summary" in enhanced.raw_metadata  # 包含Evaluation摘要
    assert enhanced.raw_institutions  # 机构信息已提取


@pytest.mark.asyncio
async def test_enhance_non_arxiv_candidate(pdf_enhancer):
    """测试非arXiv候选项（应直接返回）"""

    candidate = RawCandidate(
        title="Test GitHub Repo",
        url="https://github.com/test/repo",
        source="github",
        abstract="GitHub README",
        raw_metadata={},
    )

    enhanced = await pdf_enhancer.enhance_candidate(candidate)

    # 非arXiv候选项不应被修改
    assert enhanced == candidate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**运行测试**:

```bash
/mnt/d/VibeCoding_pgm/BenchScope/.venv/bin/python -m pytest tests/test_pdf_enhancer.py -v
```

---

### Step 6: 配置与部署

#### 6.1 GROBID服务配置

**选项A: 使用云端GROBID服务** (推荐，无需额外配置):

```python
# scipdf_parser默认使用云端GROBID服务
# 无需任何配置，开箱即用
```

**选项B: 本地Docker部署GROBID** (可选，更快速):

```bash
# 拉取GROBID镜像
docker pull lfoppiano/grobid:0.8.0

# 启动GROBID服务
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0

# 配置scipdf_parser使用本地服务
# 在pdf_enhancer.py中添加:
# parse_pdf_to_dict(str(pdf_path), grobid_url="http://localhost:8070")
```

#### 6.2 缓存目录配置

**默认缓存目录**: `/tmp/arxiv_pdf_cache`

**自定义缓存目录** (可选):

```python
# 在src/main.py中
pdf_enhancer = PDFEnhancer(cache_dir="/path/to/custom/cache")
```

**清理旧缓存** (可选):

```bash
# 删除7天前的PDF缓存
find /tmp/arxiv_pdf_cache -name "*.pdf" -mtime +7 -delete
```

---

## 📊 验收标准

### 功能验收

| 检查项 | 验收标准 | 测试方法 |
|--------|---------|---------|
| PDF下载 | ✅ 成功下载arXiv PDF到本地缓存 | 运行测试用例 `test_download_pdf` |
| PDF解析 | ✅ 提取完整摘要、章节、作者机构 | 检查 `PDFContent` 对象字段完整性 |
| 内容增强 | ✅ abstract长度 >500字，包含Evaluation/Dataset/Baselines摘要 | 手动检查增强后的候选项 |
| LLM评分 | ✅ Prompt包含PDF增强内容 | 查看LLM请求日志 |
| 集成流程 | ✅ main.py正常运行，无崩溃 | 运行完整流程 |

### 数据质量验收

运行 `scripts/analyze_data_quality.py` 验证字段覆盖率：

| 字段 | Phase 7当前 | Phase 8目标 | 验收标准 |
|------|------------|------------|---------|
| 摘要长度 | <100字 | ≥500字 | ✅ 90%候选项摘要 ≥500字 |
| 评估指标 | 18.7% | ≥60% | ✅ 覆盖率提升至60% |
| 基准模型 | 17.2% | ≥60% | ✅ 覆盖率提升至60% |
| 数据集规模 | 5.3% | ≥50% | ✅ 覆盖率提升至50% |
| 机构 | 0.5% | ≥70% | ✅ 覆盖率提升至70% |

### 性能验收

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| PDF下载速度 | <3秒/篇 | 测试10篇论文平均时间 |
| PDF解析速度 | <10秒/篇 | 测试10篇论文平均时间 |
| 完整流程耗时 | <30分钟 (50条) | 运行完整流程并记录时间 |
| 内存占用 | <1GB | 运行时监控内存使用 |

---

## 🚀 开发步骤总结

### Week 1: 核心开发

**Day 1-2: PDFEnhancer实现**
- [ ] 创建 `src/enhancer/` 目录和 `__init__.py`
- [ ] 实现 `pdf_enhancer.py` 核心逻辑
- [ ] 实现PDF下载功能 (带缓存)
- [ ] 实现PDF解析功能 (scipdf_parser)
- [ ] 实现智能章节摘要提取
- [ ] 实现作者机构提取

**Day 3: 集成到主流程**
- [ ] 修改 `src/main.py` 添加PDF增强步骤
- [ ] 修改 `src/scorer/llm_scorer.py` 更新Prompt
- [ ] 更新 `requirements.txt` 添加依赖
- [ ] 测试完整数据流

**Day 4: 测试验证**
- [ ] 编写单元测试 `tests/test_pdf_enhancer.py`
- [ ] 运行测试用例，确保100%通过
- [ ] 手动测试5-10篇arXiv论文
- [ ] 验证增强后的字段完整性

**Day 5: 文档与优化**
- [ ] 添加代码注释和文档字符串
- [ ] 优化错误处理和降级机制
- [ ] 添加日志输出
- [ ] 创建测试报告

### Week 2: 优化与上线

**Day 6-7: 性能优化**
- [ ] 实现PDF缓存清理机制
- [ ] 优化并发下载策略
- [ ] 添加超时和重试机制
- [ ] 性能基准测试

**Day 8: 成本优化**
- [ ] 分析LLM成本
- [ ] 优化Prompt长度
- [ ] 实现Redis缓存 (可选)

**Day 9: 生产测试**
- [ ] 在真实环境运行完整流程
- [ ] 分析数据质量提升
- [ ] 生成测试报告
- [ ] 修复发现的问题

**Day 10: 上线部署**
- [ ] 更新 `.claude/CLAUDE.md` 文档
- [ ] 提交代码到Git仓库
- [ ] GitHub Actions配置更新
- [ ] 生产环境部署

---

## ❓ 常见问题

### Q1: scipdf_parser安装失败？

**A**: 检查Python版本（需要3.8+），尝试：

```bash
uv pip install --upgrade pip
uv pip install scipdf-parser==0.52 --no-cache-dir
```

### Q2: PDF下载很慢？

**A**: arXiv有限流，建议：
1. 使用缓存（避免重复下载）
2. 串行下载（避免触发限流）
3. 添加重试机制

### Q3: GROBID服务连接失败？

**A**: 使用云端服务或本地Docker部署：

```bash
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0
```

### Q4: 内存占用过高？

**A**: 避免保存全文，只保留摘要：

```python
# 在PDFContent中
full_text: str = ""  # 不保存全文
```

### Q5: LLM成本过高？

**A**: 优化策略：
1. 仅对通过预筛选的候选项进行PDF增强
2. 使用Redis缓存LLM评分结果
3. 限制Evaluation/Dataset/Baselines摘要长度

---

## 📝 交付清单

完成后提交以下内容：

- [ ] `src/enhancer/__init__.py`
- [ ] `src/enhancer/pdf_enhancer.py`
- [ ] `src/main.py` (修改)
- [ ] `src/scorer/llm_scorer.py` (修改Prompt)
- [ ] `requirements.txt` (添加依赖)
- [ ] `tests/test_pdf_enhancer.py`
- [ ] 测试报告 (Markdown格式)
- [ ] 数据质量对比报告
- [ ] 性能基准报告

---

**Codex开发指令编写人**: Claude Code
**创建时间**: 2025-11-17
**版本**: v1.0

**开始开发吧！如有疑问随时向Claude Code咨询。**
