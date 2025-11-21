#!/usr/bin/env python
"""测试图片提取功能"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.image_extractor import ImageExtractor
from src.storage.feishu_image_uploader import FeishuImageUploader
from src.config import get_settings


async def test_github_image():
    """测试GitHub图片提取"""
    print("\n" + "=" * 60)
    print("测试 GitHub 图片提取")
    print("=" * 60)

    test_repos = [
        "https://github.com/microsoft/autogen",
        "https://github.com/anthropics/anthropic-sdk-python",
        "https://github.com/openai/openai-python",
    ]

    for repo_url in test_repos:
        print(f"\n🔍 提取: {repo_url}")
        image_url = await ImageExtractor.extract_github_image(repo_url)
        if image_url:
            print(f"  ✅ 找到图片: {image_url[:80]}...")
        else:
            print(f"  ❌ 未找到图片")


async def test_huggingface_image():
    """测试HuggingFace图片提取"""
    print("\n" + "=" * 60)
    print("测试 HuggingFace 图片提取")
    print("=" * 60)

    test_models = [
        "bert-base-uncased",
        "gpt2",
        "facebook/bart-large",
    ]

    for model_id in test_models:
        print(f"\n🔍 提取: {model_id}")
        image_url = await ImageExtractor.extract_huggingface_image(model_id)
        if image_url:
            print(f"  ✅ 找到图片: {image_url[:80]}...")
        else:
            print(f"  ❌ 未找到图片")


async def test_image_upload():
    """测试飞书图片上传"""
    print("\n" + "=" * 60)
    print("测试 飞书图片上传")
    print("=" * 60)

    settings = get_settings()
    uploader = FeishuImageUploader(settings)

    # 测试一个GitHub项目的og:image
    test_url = "https://opengraph.githubassets.com/1/microsoft/autogen"
    print(f"\n📤 上传测试图片: {test_url[:60]}...")

    image_key = await uploader.upload_image(test_url)
    if image_key:
        print(f"  ✅ 上传成功，image_key: {image_key}")
    else:
        print(f"  ❌ 上传失败")

    return image_key


async def main():
    """运行所有测试"""
    print("\n🧪 开始图片提取功能测试")

    try:
        await test_github_image()
        await test_huggingface_image()
        image_key = await test_image_upload()

        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        if image_key:
            print("✅ 所有测试通过！图片提取和上传功能正常")
            print(f"\n可以在飞书卡片中使用此image_key测试显示: {image_key}")
        else:
            print("⚠️  图片上传失败，请检查飞书配置")

    except Exception as exc:
        print(f"\n❌ 测试失败: {exc}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
