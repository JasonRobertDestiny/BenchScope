#!/usr/bin/env python
"""测试飞书卡片直接引用外部图片URL"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import ScoredCandidate
from src.notifier import FeishuNotifier


async def main():
    """测试飞书卡片外部图片显示"""
    print("\n🧪 测试飞书卡片外部图片引用\n")
    print("=" * 60)

    # 创建测试候选项（带外部图片URL）
    test_candidate = ScoredCandidate(
        title="AutoGen: 多智能体对话框架",
        source="GitHub",
        url="https://github.com/microsoft/autogen",
        abstract="微软开源的多智能体对话框架，支持复杂的Agent协作场景",
        github_url="https://github.com/microsoft/autogen",
        hero_image_url="https://opengraph.githubassets.com/1/microsoft/autogen",  # GitHub og:image
        activity_score=9.5,
        reproducibility_score=9.0,
        license_score=10.0,
        novelty_score=8.5,
        relevance_score=9.5,
        overall_reasoning="该项目是微软开源的多智能体框架，Star数>20K，活跃开发中，与MGX高度相关",
    )

    print(f"📝 测试候选项: {test_candidate.title}")
    print(f"🖼️  图片URL: {test_candidate.hero_image_url}")
    print(f"⭐ 总分: {test_candidate.total_score:.1f}/10\n")

    # 发送飞书通知
    notifier = FeishuNotifier()

    try:
        print("📤 正在发送飞书卡片通知...")
        await notifier.notify([test_candidate])
        print("\n✅ 飞书卡片发送成功！")
        print("\n请检查飞书群，确认：")
        print("  1. 卡片是否正常显示")
        print("  2. GitHub og:image 图片是否正常加载")
        print("  3. 图片尺寸和显示效果是否符合预期")
        return 0

    except Exception as exc:
        print(f"\n❌ 测试失败: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
