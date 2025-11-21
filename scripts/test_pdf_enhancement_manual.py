"""手动测试PDF Enhancement功能"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.enhancer import PDFEnhancer
from src.models import RawCandidate
from src.scorer import LLMScorer


async def test_single_arxiv_paper():
    """测试单篇arXiv论文的PDF Enhancement功能"""

    # 使用已知的MGX相关论文（SWE-bench）
    test_paper = RawCandidate(
        title="SWE-bench: Can Language Models Resolve Real-World GitHub Issues?",
        url="https://arxiv.org/abs/2310.06770",
        source="arxiv",
        abstract="We introduce SWE-bench, an evaluation framework consisting of 2,294 software engineering problems drawn from real GitHub issues and corresponding pull requests across 12 popular Python repositories.",
        paper_url="https://arxiv.org/abs/2310.06770",
        publish_date=datetime(2023, 10, 10),
    )

    print("=" * 60)
    print("测试：PDF Enhancement功能验证")
    print("=" * 60)
    print(f"\n测试论文: {test_paper.title}")
    print(f"arXiv URL: {test_paper.paper_url}")

    # Step 1: PDF Enhancement
    print("\n" + "-" * 60)
    print("Step 1: PDF Enhancement（提取6个章节）")
    print("-" * 60)

    enhancer = PDFEnhancer()
    try:
        enhanced = await enhancer.enhance_candidate(test_paper)

        print("\n📄 PDF Enhancement结果:")
        print(f"  - 原始摘要长度: {len(test_paper.abstract or '')} chars")

        if enhanced.raw_metadata:
            print(f"  - raw_metadata keys: {list(enhanced.raw_metadata.keys())}")

            # 提取6个章节摘要
            introduction = enhanced.raw_metadata.get('introduction_summary', '')
            method = enhanced.raw_metadata.get('method_summary', '')
            evaluation = enhanced.raw_metadata.get('evaluation_summary', '')
            dataset = enhanced.raw_metadata.get('dataset_summary', '')
            baselines = enhanced.raw_metadata.get('baselines_summary', '')
            conclusion = enhanced.raw_metadata.get('conclusion_summary', '')

            print(f"\n  章节提取结果:")
            print(f"    - introduction_summary: {len(introduction)} chars")
            print(f"    - method_summary: {len(method)} chars")
            print(f"    - evaluation_summary: {len(evaluation)} chars")
            print(f"    - dataset_summary: {len(dataset)} chars")
            print(f"    - baselines_summary: {len(baselines)} chars")
            print(f"    - conclusion_summary: {len(conclusion)} chars")

            total_pdf_content = sum([
                len(introduction),
                len(method),
                len(evaluation),
                len(dataset),
                len(baselines),
                len(conclusion),
            ])
            print(f"\n  - PDF总内容长度: {total_pdf_content} chars")

            # 验证P1核心章节数量
            p1_sections = [introduction, method, evaluation, dataset]
            p1_count = sum(1 for s in p1_sections if s and not s.startswith("未提供"))
            print(f"  - P1核心章节数量: {p1_count}/4")

            # 验证P2辅助章节数量
            p2_sections = [baselines, conclusion]
            p2_count = sum(1 for s in p2_sections if s and not s.startswith("未提供"))
            print(f"  - P2辅助章节数量: {p2_count}/2")

            # 质量评估
            if p1_count >= 2:
                print(f"\n  ✅ PDF Enhancement质量达标（P1≥2）")
            else:
                print(f"\n  ⚠️ PDF Enhancement质量不足（P1<2）")

        else:
            print("  ❌ raw_metadata为空，PDF Enhancement失败")
            return

    except Exception as e:
        print(f"\n  ❌ PDF Enhancement失败: {e}")
        return

    # Step 2: LLM评分
    print("\n" + "-" * 60)
    print("Step 2: LLM评分（验证推理长度提升）")
    print("-" * 60)

    async with LLMScorer() as scorer:
        try:
            scored = await scorer.score(enhanced)

            print("\n🎯 LLM评分结果:")

            # 统计推理字段长度
            reasoning_fields = {
                'activity_reasoning': scored.activity_reasoning,
                'reproducibility_reasoning': scored.reproducibility_reasoning,
                'license_reasoning': scored.license_reasoning,
                'novelty_reasoning': scored.novelty_reasoning,
                'relevance_reasoning': scored.relevance_reasoning,
                'overall_reasoning': scored.overall_reasoning,
            }

            for field_name, reasoning_text in reasoning_fields.items():
                print(f"  - {field_name}: {len(reasoning_text)} chars")

            # 计算总推理长度
            total_reasoning = sum(len(text) for text in reasoning_fields.values())
            print(f"\n  - 推理总字数: {total_reasoning} chars")

            # 验证是否达标
            if total_reasoning >= 1200:
                print(f"  ✅ 推理总字数达标（≥1200）")
            else:
                print(f"  ❌ 推理总字数不足（{total_reasoning} < 1200）")

            # 显示评分
            print(f"\n  评分结果:")
            print(f"    - activity_score: {scored.activity_score}/10")
            print(f"    - reproducibility_score: {scored.reproducibility_score}/10")
            print(f"    - license_score: {scored.license_score}/10")
            print(f"    - novelty_score: {scored.novelty_score}/10")
            print(f"    - relevance_score: {scored.relevance_score}/10")

        except Exception as e:
            print(f"\n  ❌ LLM评分失败: {e}")
            import traceback
            traceback.print_exc()
            return

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_single_arxiv_paper())
