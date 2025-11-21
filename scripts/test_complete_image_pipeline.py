#!/usr/bin/env python
"""测试完整的图片处理流程：提取 → 上传 → 显示"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.image_extractor import ImageExtractor
from src.storage.feishu_image_uploader import FeishuImageUploader
from src.models import ScoredCandidate
from src.notifier import FeishuNotifier


async def main():
    """测试完整图片处理流程"""
    print("\n🧪 测试完整图片处理流程\n")
    print("=" * 60)

    # Step 1: 提取图片URL
    print("\n[1/3] 提取 GitHub 图片 URL...")
    repo_url = "https://github.com/microsoft/autogen"
    image_url = await ImageExtractor.extract_github_image(repo_url)

    if not image_url:
        print("❌ 图片提取失败")
        return 1

    print(f"✅ 提取成功: {image_url[:80]}...")

    # Step 2: 上传图片到飞书
    print("\n[2/3] 上传图片到飞书...")
    uploader = FeishuImageUploader()
    image_key = await uploader.upload_image(image_url)

    if not image_key:
        print("❌ 图片上传失败")
        return 1

    print(f"✅ 上传成功: {image_key}")

    # Step 3: 发送飞书卡片（带图片）
    print("\n[3/3] 发送飞书卡片...")
    test_candidate = ScoredCandidate(
        title="AutoGen: 多智能体对话框架 (测试图片显示)",
        source="GitHub",
        url=repo_url,
        abstract="微软开源的多智能体对话框架，支持复杂的Agent协作场景",
        github_url=repo_url,
        hero_image_url=image_url,  # 原始图片URL
        hero_image_key=image_key,  # 飞书image_key
        activity_score=9.5,
        reproducibility_score=9.0,
        license_score=10.0,
        novelty_score=8.5,
        relevance_score=9.5,
        overall_reasoning="该项目是微软开源的多智能体框架，Star数>20K，活跃开发中，与MGX高度相关",
    )

    notifier = FeishuNotifier()
    await notifier.notify([test_candidate])

    print("✅ 飞书卡片发送成功！")

    # 测试总结
    print("\n" + "=" * 60)
    print("✅ 完整流程测试通过！")
    print("\n请检查飞书群，确认：")
    print("  1. 卡片是否正常显示")
    print("  2. 图片是否正常加载并显示在卡片顶部")
    print("  3. 图片尺寸和显示效果是否符合预期")
    print(f"\n图片信息：")
    print(f"  - 原始URL: {image_url[:80]}...")
    print(f"  - 飞书Key: {image_key}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
