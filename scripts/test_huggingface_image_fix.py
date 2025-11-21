"""测试修复后的HuggingFace图片提取"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.image_extractor import ImageExtractor


async def main():
    print("🧪 测试修复后的HuggingFace图片提取\n")
    print("=" * 60)

    # 测试几个公开的HuggingFace数据集
    test_datasets = [
        "openai/gsm8k",  # 数学推理数据集
        "bigcode/the-stack",  # 代码数据集
        "mozilla-foundation/common_voice_11_0",  # 语音数据集
    ]

    for dataset_id in test_datasets:
        print(f"\n测试: {dataset_id}")
        print("-" * 60)

        # 正确的URL格式
        correct_url = f"https://huggingface.co/datasets/{dataset_id}"
        print(f"  URL: {correct_url}")

        try:
            image_url = await ImageExtractor.extract_huggingface_image(dataset_id)

            if image_url:
                print(f"  ✅ 图片提取成功")
                print(f"     {image_url[:80]}...")
            else:
                print(f"  ⚠️  未找到图片（可能该数据集没有配置og:image）")

        except Exception as e:
            print(f"  ❌ 提取失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
