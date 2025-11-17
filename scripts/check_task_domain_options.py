#!/usr/bin/env python3
"""检查飞书表格'任务领域'字段的选项配置是否与代码一致"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import get_settings
from src.common import constants


async def check_task_domain_options():
    settings = get_settings()

    async with httpx.AsyncClient(timeout=30) as client:
        # 获取access token
        token_url = (
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        )
        token_resp = await client.post(
            token_url,
            json={
                "app_id": settings.feishu.app_id,
                "app_secret": settings.feishu.app_secret,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data["tenant_access_token"]

        # 获取表格字段配置
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/fields"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print(f'❌ 查询失败: {data.get("msg")}')
            return

        fields = data.get("data", {}).get("items", [])

        # 查找"任务领域"字段
        task_domain_field = None
        for field in fields:
            field_name = field.get("field_name")
            if field_name == "任务领域" or "domain" in field_name.lower():
                task_domain_field = field
                break

        if not task_domain_field:
            print("❌ 未找到'任务领域'字段")
            print("\n所有字段:")
            for field in fields:
                print(f"  - {field.get('field_name')} ({field.get('type')})")
            return

        print("=" * 80)
        print("飞书表格'任务领域'字段配置检查")
        print("=" * 80)
        print(f"字段名称: {task_domain_field.get('field_name')}")
        print(f"字段类型: {task_domain_field.get('type')} (3=多选)")
        print()

        # 获取选项配置
        property_data = task_domain_field.get("property", {})
        options = property_data.get("options", [])

        if not options:
            print("⚠️  未找到选项配置")
            return

        feishu_domains = sorted([opt.get("name") for opt in options])
        code_domains = sorted(constants.TASK_DOMAIN_OPTIONS)

        print("【飞书表格当前选项】(共{}个):".format(len(feishu_domains)))
        for idx, domain in enumerate(feishu_domains, 1):
            print(f"  {idx:2d}. {domain}")

        print()
        print("=" * 80)
        print("【代码配置】(constants.py - TASK_DOMAIN_OPTIONS)")
        print("=" * 80)
        print(f"共{len(code_domains)}个:")
        for idx, domain in enumerate(code_domains, 1):
            priority = "P0" if domain in ["Coding", "WebDev", "Backend", "GUI"] else \
                       "P1" if domain in ["ToolUse", "Collaboration", "LLM/AgentOps"] else \
                       "P2" if domain in ["Reasoning", "DeepResearch"] else "Low"
            print(f"  {idx:2d}. {domain:20s} ({priority})")

        print()
        print("=" * 80)
        print("【差异分析】")
        print("=" * 80)

        # 飞书有但代码没有 - 需要删除
        feishu_only = set(feishu_domains) - set(code_domains)
        # 代码有但飞书没有 - 需要添加
        code_only = set(code_domains) - set(feishu_domains)

        if feishu_only:
            print(f"\n❌ 飞书表格有，但代码中没有 ({len(feishu_only)}个) - 建议删除:")
            for domain in sorted(feishu_only):
                print(f"     ✗ {domain}")

        if code_only:
            print(f"\n⚠️  代码中有，但飞书表格没有 ({len(code_only)}个) - 建议添加:")
            for domain in sorted(code_only):
                priority = "P0" if domain in ["Coding", "WebDev", "Backend", "GUI"] else \
                           "P1" if domain in ["ToolUse", "Collaboration", "LLM/AgentOps"] else \
                           "P2" if domain in ["Reasoning", "DeepResearch"] else "Low"
                print(f"     + {domain} ({priority})")

        if not feishu_only and not code_only:
            print("\n✅ 配置完全一致！飞书表格与代码配置同步。")
            return

        print(f"\n总计差异: {len(feishu_only) + len(code_only)}个")

        # 生成飞书操作指令
        print()
        print("=" * 80)
        print("【飞书AI修复指令】")
        print("=" * 80)
        print("\n请在飞书多维表格中执行以下操作：\n")

        if feishu_only:
            print("删除以下选项:")
            for domain in sorted(feishu_only):
                print(f'  - "{domain}"')
            print()

        if code_only:
            print("添加以下选项:")
            for domain in sorted(code_only):
                print(f'  + "{domain}"')
            print()

        print("修复后的完整选项列表 (共{}个):".format(len(code_domains)))
        for idx, domain in enumerate(code_domains, 1):
            print(f"  {idx:2d}. {domain}")

        print()
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_task_domain_options())
