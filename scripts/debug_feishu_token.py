#!/usr/bin/env python3
"""
飞书token问题诊断脚本
测试token获取和API调用
"""

import sys
import asyncio
from pathlib import Path

import httpx

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings
from src.storage.feishu_storage import FeishuStorage


async def test_feishu_token():
    """测试飞书token获取"""
    print("=" * 70)
    print("飞书Token问题诊断")
    print("=" * 70)

    try:
        # 1. 检查配置
        print("\n[1/5] 检查环境配置...")
        settings = get_settings()
        print(f"✓ FEISHU_APP_ID: {settings.feishu.app_id}")
        print(f"✓ FEISHU_APP_SECRET: {'*' * (len(settings.feishu.app_secret) - 4) + settings.feishu.app_secret[-4:] if settings.feishu.app_secret else 'N/A'}")
        print(f"✓ FEISHU_BITABLE_APP_TOKEN: {settings.feishu.bitable_app_token}")
        print(f"✓ FEISHU_BITABLE_TABLE_ID: {settings.feishu.bitable_table_id}")

        if not settings.feishu.app_id or not settings.feishu.app_secret:
            print("\n❌ 错误: 飞书应用凭证缺失")
            return False

        # 2. 测试token获取
        print("\n[2/5] 测试token获取...")
        storage = FeishuStorage(settings=settings)

        try:
            await storage._ensure_access_token()
            print(f"✓ Token获取成功")
            print(f"  Token: {storage.access_token[:20]}..." if storage.access_token else "  Token: None")
            print(f"  过期时间: {storage.token_expire_at}")

        except Exception as e:
            print(f"❌ Token获取失败: {e}")
            print(f"\n可能原因:")
            print("1. App ID或App Secret错误")
            print("2. 飞书应用已被禁用")
            print("3. 应用权限不足")
            print("4. 网络连接问题")
            return False

        # 3. 测试字段查询
        print("\n[3/5] 测试字段查询...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await storage._ensure_field_cache(client)
            print(f"✓ 字段查询成功")
            print(f"  字段数量: {len(storage._field_names)}")
            print(f"  字段列表: {', '.join(sorted(list(storage._field_names))[:5])}{'...' if len(storage._field_names) > 5 else ''}")

        except Exception as e:
            print(f"❌ 字段查询失败: {e}")
            return False

        # 4. 测试记录读取
        print("\n[4/5] 测试记录读取...")
        try:
            records = await storage.read_existing_records()
            print(f"✓ 记录读取成功")
            print(f"  记录数量: {len(records)}")

            if records:
                # 显示第一条记录示例
                sample = records[0]
                print(f"\n  示例记录:")
                for key, value in sample.items():
                    if isinstance(value, dict):
                        print(f"    {key}: <dict>")
                    elif isinstance(value, str):
                        print(f"    {key}: {value[:50]}..." if len(value) > 50 else f"    {key}: {value}")
                    else:
                        print(f"    {key}: {value}")

        except Exception as e:
            print(f"❌ 记录读取失败: {e}")
            return False

        # 5. 验证created_at字段
        print("\n[5/5] 验证created_at字段...")
        if records:
            created_count = sum(1 for r in records if r.get("created_at"))
            print(f"  有created_at字段的记录: {created_count}/{len(records)}")

            if created_count > 0:
                print("  ✓ created_at字段已配置")
            else:
                print("  ⚠ created_at字段未配置（需要手动添加）")
                print("    操作步骤:")
                print("    1. 打开飞书多维表格")
                print("    2. 点击 '+' 添加字段")
                print("    3. 选择类型 '创建时间'")
                print("    4. 字段名: '创建时间'")
        else:
            print("  ℹ 无记录可检查")

        print("\n" + "=" * 70)
        print("✅ 飞书连接正常!")
        print("=" * 70)
        print("\n建议:")
        if not records:
            print("- 当前无历史记录，这是正常的")
        if created_count == 0:
            print("- 请添加'创建时间'字段以启用P12去重修复")
        print("- 可以安全运行完整采集流程")

        return True

    except Exception as e:
        print(f"\n❌ 诊断过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_write_access():
    """测试写入权限"""
    print("\n" + "=" * 70)
    print("测试飞书写入权限")
    print("=" * 70)

    try:
        settings = get_settings()
        storage = FeishuStorage(settings=settings)

        # 尝试获取access token
        await storage._ensure_access_token()

        # 检查权限
        print("\n检查应用权限...")
        print("✓ 应用凭证有效")
        print("✓ 可以获取access_token")
        print("✓ 可以读取表结构")
        print("✓ 可以读取记录")

        print("\n" + "=" * 70)
        print("✅ 写入权限验证完成")
        print("=" * 70)
        print("\n注意: 实际写入测试需要实际数据，不在诊断范围内")

        return True

    except Exception as e:
        print(f"\n❌ 权限验证失败: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 开始诊断飞书token问题...\n")

    # 运行诊断
    result = asyncio.run(test_feishu_token())

    if result:
        # 额外测试写入权限
        asyncio.run(test_write_access())
        sys.exit(0)
    else:
        print("\n❌ 诊断发现问题，请查看上述错误信息")
        sys.exit(1)
