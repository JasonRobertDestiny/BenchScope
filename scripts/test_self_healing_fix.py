"""测试Self-Healing总推理长度纠偏修复

验证修复后的Self-Healing能在总推理长度不足时触发第2次纠偏
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models import RawCandidate
from src.scorer import LLMScorer


async def test_self_healing_total_length():
    """测试总推理长度不足时的Self-Healing"""

    # 使用真实存在的小型项目测试（信息较少，容易触发推理长度不足）
    test_candidate = RawCandidate(
        title="Test Benchmark Repository",
        url="https://github.com/github/docs",
        source="github",
        abstract="A simple test repository with minimal information to trigger reasoning length issues",
        github_url="https://github.com/github/docs",
        github_stars=100,
        publish_date=datetime(2024, 11, 15),
    )

    print("=" * 80)
    print("测试：Self-Healing总推理长度修复")
    print("=" * 80)
    print(f"\n测试候选: {test_candidate.title}")
    print(f"GitHub URL: {test_candidate.github_url}")
    print(f"GitHub Stars: {test_candidate.github_stars}")

    print("\n" + "-" * 80)
    print("执行LLM评分（观察Self-Healing日志）...")
    print("-" * 80)

    async with LLMScorer() as scorer:
        try:
            scored = await scorer.score(test_candidate)

            print("\n✅ LLM评分完成\n")

            # 统计推理长度
            reasoning_fields = {
                "activity_reasoning": scored.activity_reasoning,
                "reproducibility_reasoning": scored.reproducibility_reasoning,
                "license_reasoning": scored.license_reasoning,
                "novelty_reasoning": scored.novelty_reasoning,
                "relevance_reasoning": scored.relevance_reasoning,
                "overall_reasoning": scored.overall_reasoning,
            }

            print("=" * 80)
            print("【推理长度统计】")
            print("=" * 80)

            for field_name, reasoning_text in reasoning_fields.items():
                length = len(reasoning_text)
                status = "✅" if length >= 150 else "⚠️"
                print(f"  {status} {field_name:30s}: {length:4d} chars")

            total_reasoning = sum(len(text) for text in reasoning_fields.values())
            print(f"\n总推理长度: {total_reasoning} chars")

            if total_reasoning >= 1200:
                print(f"✅ PASS - 总推理长度达标 ({total_reasoning} ≥ 1200)")
            else:
                print(f"⚠️  WARNING - 总推理长度不足 ({total_reasoning} < 1200)")

            # 评分结果
            print("\n" + "=" * 80)
            print("【评分结果】")
            print("=" * 80)
            print(f"\n  activity_score:        {scored.activity_score:.1f}/10")
            print(f"  reproducibility_score: {scored.reproducibility_score:.1f}/10")
            print(f"  license_score:         {scored.license_score:.1f}/10")
            print(f"  novelty_score:         {scored.novelty_score:.1f}/10")
            print(f"  relevance_score:       {scored.relevance_score:.1f}/10")

            avg_score = (
                scored.activity_score
                + scored.reproducibility_score
                + scored.license_score
                + scored.novelty_score
                + scored.relevance_score
            ) / 5
            print(f"\n  平均分: {avg_score:.2f}/10")

        except Exception as e:
            print(f"\n❌ LLM评分失败: {e}")
            import traceback

            traceback.print_exc()
            return

    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
    print("\n【关键观察点】")
    print("查看上方日志，应出现以下模式之一：")
    print("  1. [WARNING] 推理总字数不足（XXX < 1200），触发第N次纠偏")
    print("  2. [WARNING] 推理总字数不足: XXX < 1200（已达最大重试2次）")
    print("  3. 无WARNING（总长度直接≥1200）")


if __name__ == "__main__":
    asyncio.run(test_self_healing_total_length())
