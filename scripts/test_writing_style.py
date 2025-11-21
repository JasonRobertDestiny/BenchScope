"""测试LLM评分的人性化写作风格

验证Codex Phase人性化优化的效果：
1. overall_reasoning ≥ 200字符（从50提升至200）
2. 写作风格：Markdown格式、✅/⚠️/💡符号、禁止【】符号
3. 推理结构：短段落、加粗关键数据、结尾给出"⭐ 是否纳入"结论
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models import RawCandidate
from src.scorer import LLMScorer


async def test_writing_style():
    """测试LLM评分的写作风格优化"""

    # 使用已知的高质量论文（SWE-bench）
    test_paper = RawCandidate(
        title="SWE-bench: Can Language Models Resolve Real-World GitHub Issues?",
        url="https://arxiv.org/abs/2310.06770",
        source="arxiv",
        abstract="We introduce SWE-bench, an evaluation framework consisting of 2,294 software engineering problems drawn from real GitHub issues and corresponding pull requests across 12 popular Python repositories.",
        paper_url="https://arxiv.org/abs/2310.06770",
        publish_date=datetime(2023, 10, 10),
        github_stars=1200,
        github_url="https://github.com/princeton-nlp/SWE-bench",
    )

    print("=" * 80)
    print("测试：LLM评分人性化写作风格")
    print("=" * 80)
    print(f"\n测试论文: {test_paper.title}")
    print(f"arXiv URL: {test_paper.paper_url}")

    # LLM评分
    print("\n" + "-" * 80)
    print("执行LLM评分...")
    print("-" * 80)

    async with LLMScorer() as scorer:
        try:
            scored = await scorer.score(test_paper)

            print("\n✅ LLM评分完成\n")

            # 验证1: overall_reasoning长度
            print("=" * 80)
            print("【验证1】overall_reasoning长度要求（≥200字符）")
            print("=" * 80)
            overall_len = len(scored.overall_reasoning)
            print(f"\n实际长度: {overall_len} 字符")
            print(f"要求阈值: 200 字符")
            if overall_len >= 200:
                print(f"✅ PASS - 长度达标 ({overall_len} ≥ 200)")
            else:
                print(f"❌ FAIL - 长度不足 ({overall_len} < 200)")

            # 验证2: 写作风格特征
            print("\n" + "=" * 80)
            print("【验证2】写作风格要求")
            print("=" * 80)

            # 检查禁止的【】符号
            has_brackets = "【" in scored.overall_reasoning or "】" in scored.overall_reasoning
            print(f"\n✅ 无【】符号: {not has_brackets}")
            if has_brackets:
                print("  ⚠️  WARNING - 发现禁止的【】符号")

            # 检查推荐的符号（✅/⚠️/💡/⭐）
            has_checkmark = "✅" in scored.overall_reasoning
            has_warning = "⚠️" in scored.overall_reasoning
            has_bulb = "💡" in scored.overall_reasoning
            has_star = "⭐" in scored.overall_reasoning
            emoji_count = sum([has_checkmark, has_warning, has_bulb, has_star])
            print(f"✅ 使用推荐符号: {emoji_count}/4 (✅:{has_checkmark} ⚠️:{has_warning} 💡:{has_bulb} ⭐:{has_star})")

            # 检查Markdown格式（列表、加粗）
            has_list = "-" in scored.overall_reasoning or "*" in scored.overall_reasoning
            has_bold = "**" in scored.overall_reasoning
            print(f"✅ Markdown列表: {has_list}")
            print(f"✅ 加粗关键数据: {has_bold}")

            # 验证3: 推理内容展示
            print("\n" + "=" * 80)
            print("【验证3】overall_reasoning完整内容")
            print("=" * 80)
            print(f"\n{scored.overall_reasoning}")

            # 验证4: 其他推理字段长度
            print("\n" + "=" * 80)
            print("【验证4】其他推理字段长度")
            print("=" * 80)
            reasoning_fields = {
                "activity_reasoning": scored.activity_reasoning,
                "reproducibility_reasoning": scored.reproducibility_reasoning,
                "license_reasoning": scored.license_reasoning,
                "novelty_reasoning": scored.novelty_reasoning,
                "relevance_reasoning": scored.relevance_reasoning,
            }

            print("\n各维度推理长度:")
            for field_name, reasoning_text in reasoning_fields.items():
                length = len(reasoning_text)
                status = "✅" if length >= 150 else "⚠️"
                print(f"  {status} {field_name:30s}: {length:4d} chars (≥150)")

            # 总推理长度
            total_reasoning = sum(len(text) for text in reasoning_fields.values()) + overall_len
            print(f"\n总推理长度: {total_reasoning} chars")
            if total_reasoning >= 1200:
                print(f"✅ PASS - 总推理长度达标 ({total_reasoning} ≥ 1200)")
            else:
                print(f"⚠️  WARNING - 总推理长度不足 ({total_reasoning} < 1200)")

            # 验证5: 评分结果
            print("\n" + "=" * 80)
            print("【验证5】评分结果")
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

            # 最终总结
            print("\n" + "=" * 80)
            print("【测试总结】")
            print("=" * 80)
            checks = [
                ("overall_reasoning长度≥200", overall_len >= 200),
                ("无禁止的【】符号", not has_brackets),
                ("使用推荐符号(≥1个)", emoji_count >= 1),
                ("Markdown格式", has_list and has_bold),
                ("总推理长度≥1200", total_reasoning >= 1200),
            ]

            pass_count = sum(1 for _, passed in checks if passed)
            print(f"\n通过检查: {pass_count}/{len(checks)}")
            for check_name, passed in checks:
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {status} - {check_name}")

            if pass_count == len(checks):
                print("\n🎉 所有检查通过！写作风格优化成功！")
            else:
                print(f"\n⚠️  部分检查未通过 ({pass_count}/{len(checks)})")

        except Exception as e:
            print(f"\n❌ LLM评分失败: {e}")
            import traceback

            traceback.print_exc()
            return

    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_writing_style())
