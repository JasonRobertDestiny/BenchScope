"""PDFEnhancer 单元测试。

覆盖范围：
1. arXiv ID 提取逻辑
2. PDF 下载功能（真实 arXiv 论文）
3. arXiv 候选项增强（摘要与元数据）
4. 非 arXiv 候选项的降级行为
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.enhancer import PDFEnhancer
from src.models import RawCandidate


@pytest.fixture
def pdf_enhancer() -> PDFEnhancer:
    """创建 PDFEnhancer 实例（使用单独的测试缓存目录）。"""

    cache_dir = "/tmp/test_arxiv_cache"
    return PDFEnhancer(cache_dir=cache_dir)


@pytest.mark.asyncio
async def test_extract_arxiv_id() -> None:
    """测试 arXiv ID 提取逻辑。"""

    enhancer = PDFEnhancer()

    # 标准 abs 链接
    assert enhancer._extract_arxiv_id("https://arxiv.org/abs/2401.12345") == "2401.12345"
    # 带版本号
    assert enhancer._extract_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345"
    # 直接 pdf 地址
    assert enhancer._extract_arxiv_id("https://arxiv.org/pdf/2401.12345.pdf") == "2401.12345"
    # 非法 URL
    assert enhancer._extract_arxiv_id("invalid_url") is None


@pytest.mark.asyncio
async def test_download_pdf(pdf_enhancer: PDFEnhancer) -> None:
    """测试 PDF 下载（使用真实 arXiv 论文）。

    说明：
    - 此用例依赖外网与 scipdf_parser 默认的 GROBID 服务
    - 如网络或服务不可用，建议在本地开发环境中运行验证
    """

    # 使用已知存在的 arXiv 论文（GPT-4 Technical Report）
    arxiv_id = "2303.08774"

    pdf_path = await pdf_enhancer._download_pdf(arxiv_id)

    assert pdf_path is not None
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"


@pytest.mark.asyncio
async def test_enhance_arxiv_candidate(pdf_enhancer: PDFEnhancer) -> None:
    """测试 arXiv 候选项增强行为。"""

    candidate = RawCandidate(
        title="GPT-4 Technical Report",
        url="https://arxiv.org/abs/2303.08774",
        source="arxiv",
        abstract="Short abstract...",  # 构造一个较短的摘要
        paper_url="https://arxiv.org/abs/2303.08774",
        raw_metadata={},
    )

    # 记录增强前摘要长度
    original_len = len(candidate.abstract or "")

    enhanced = await pdf_enhancer.enhance_candidate(candidate)

    # 摘要长度应该不短于原始长度（正常情况下会显著变长）
    assert len(enhanced.abstract or "") >= original_len

    # 验证增强后的元数据字段
    assert "evaluation_summary" in enhanced.raw_metadata
    assert "dataset_summary" in enhanced.raw_metadata
    assert "baselines_summary" in enhanced.raw_metadata

    # 机构信息应尽量被填充（具体值依赖论文元数据）
    assert enhanced.raw_institutions is None or isinstance(
        enhanced.raw_institutions,
        str,
    )


@pytest.mark.asyncio
async def test_enhance_non_arxiv_candidate(pdf_enhancer: PDFEnhancer) -> None:
    """测试非 arXiv 候选项（应直接返回，不做任何修改）。"""

    candidate = RawCandidate(
        title="Test GitHub Repo",
        url="https://github.com/test/repo",
        source="github",
        abstract="GitHub README",
        raw_metadata={},
    )

    enhanced = await pdf_enhancer.enhance_candidate(candidate)

    # 对于非 arXiv 来源，PDFEnhancer 不应做任何修改
    assert enhanced is candidate
    assert enhanced.raw_metadata == candidate.raw_metadata


if __name__ == "__main__":
    # 方便在本地直接运行单个测试文件
    asyncio.run(pytest.main([__file__, "-v"]))

