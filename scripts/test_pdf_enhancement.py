"""测试 PDF 增强多章节提取"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.enhancer.pdf_enhancer import PDFEnhancer
from src.models import RawCandidate


async def main() -> None:
    print("🧪 PDF章节提取测试")
    print("=" * 60)

    # 示例arXiv ID，需提前运行一次采集以下载PDF
    arxiv_id = "2511.15168"
    pdf_path = Path("/tmp/arxiv_pdf_cache") / f"{arxiv_id}.pdf"
    if not pdf_path.exists():
        print(f"⚠️  PDF不存在，跳过: {pdf_path}")
        print("   请先运行采集流程下载对应PDF后再测试。")
        return

    candidate = RawCandidate(
        title="测试论文",
        url=f"https://arxiv.org/abs/{arxiv_id}",
        source="arxiv",
    )

    enhancer = PDFEnhancer()
    enhanced = await enhancer.enhance_candidate(candidate)

    required_fields = [
        "introduction_summary",
        "method_summary",
        "evaluation_summary",
        "dataset_summary",
        "baselines_summary",
        "conclusion_summary",
    ]

    missing = [k for k in required_fields if not enhanced.raw_metadata.get(k)]
    for key in required_fields:
        val = enhanced.raw_metadata.get(key, "")
        print(f"{key}: {len(val)} 字符")

    if missing:
        print(f"❌ 缺少字段或为空: {', '.join(missing)}")
    else:
        print("✅ 六个章节均已填充")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
