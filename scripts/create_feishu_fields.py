"""使用飞书API自动创建Phase 6缺失的9个字段"""
import asyncio

import httpx

from src.config import get_settings


# Phase 6字段定义
PHASE6_FIELDS = [
    {
        "field_name": "论文 URL",
        "type": 15,  # URL类型
        "description": "论文原文链接(arXiv/Semantic Scholar)",
    },
    {
        "field_name": "GitHub Stars",
        "type": 2,  # 数字类型
        "description": "GitHub星标数",
    },
    {
        "field_name": "作者信息",
        "type": 1,  # 文本类型
        "description": "作者列表(逗号分隔,最多200字)",
    },
    {
        "field_name": "开源时间",
        "type": 5,  # 日期类型
        "description": "首次发布或最后更新日期",
    },
    {
        "field_name": "复现脚本链接",
        "type": 15,  # URL类型
        "description": "评估/复现脚本仓库链接",
    },
    {
        "field_name": "评价指标摘要",
        "type": 1,  # 文本类型
        "description": "如'Accuracy, F1, BLEU'(最多200字)",
    },
    {
        "field_name": "数据集 URL",
        "type": 15,  # URL类型
        "description": "数据集下载/查看链接",
    },
    {
        "field_name": "任务类型",
        "type": 1,  # 文本类型
        "description": "Code Generation/QA/Reasoning等",
    },
    {
        "field_name": "License类型",
        "type": 1,  # 文本类型
        "description": "MIT/Apache-2.0/GPL等",
    },
]


async def create_field(client: httpx.AsyncClient, access_token: str, field_def: dict) -> bool:
    """创建单个字段"""
    settings = get_settings()

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/fields"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "field_name": field_def["field_name"],
        "type": field_def["type"],
        "description": field_def["description"],
    }

    try:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 0:
            print(f"  ✅ 创建成功: {field_def['field_name']}")
            return True
        else:
            error_msg = data.get("msg", "未知错误")
            # 字段已存在不算错误
            if "already exists" in error_msg.lower() or "已存在" in error_msg:
                print(f"  ⚠️  字段已存在: {field_def['field_name']}")
                return True
            else:
                print(f"  ❌ 创建失败: {field_def['field_name']} - {error_msg}")
                return False

    except Exception as exc:
        print(f"  ❌ 请求异常: {field_def['field_name']} - {exc}")
        return False


async def main():
    settings = get_settings()

    print("开始创建Phase 6字段...")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=30) as client:
        # 获取access token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
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

        # 逐个创建字段
        results = []
        for field_def in PHASE6_FIELDS:
            success = await create_field(client, access_token, field_def)
            results.append((field_def["field_name"], success))
            await asyncio.sleep(0.5)  # 避免API限流

    print("=" * 80)
    print("创建结果汇总:")
    success_count = sum(1 for _, success in results if success)
    print(f"  成功: {success_count}/{len(results)}")
    print(f"  失败: {len(results) - success_count}/{len(results)}")

    if success_count == len(results):
        print("\n✅ 所有字段创建成功!")
        print("\n下一步:")
        print("  1. 运行 'PYTHONPATH=. uv run python scripts/verify_feishu_write.py' 验证字段")
        print("  2. 清空飞书表格旧数据")
        print("  3. 运行 'PYTHONPATH=. uv run python src/main.py' 重新写入")
        print("  4. 运行 'PYTHONPATH=. uv run python scripts/check_feishu_fields.py' 检查完整性")
    else:
        print("\n⚠️  部分字段创建失败,请检查:")
        for field_name, success in results:
            if not success:
                print(f"  - {field_name}")


if __name__ == "__main__":
    asyncio.run(main())
