"""清空飞书Bitable所有记录

警告：此脚本会删除飞书多维表格中的所有记录！

用法: python scripts/clear_feishu_table.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.storage.feishu_storage import FeishuStorage


async def main():
    storage = FeishuStorage()
    await storage._ensure_access_token()

    print("⚠️  警告：此操作将删除飞书多维表格中的所有记录！")
    confirm = input("确定要继续吗？(输入 'yes' 确认): ")

    if confirm.lower() != "yes":
        print("❌ 操作已取消")
        return

    # 查询所有记录
    all_record_ids = []
    page_token = None

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            search_url = f"{storage.base_url}/bitable/v1/apps/{storage.settings.feishu.bitable_app_token}/tables/{storage.settings.feishu.bitable_table_id}/records/search"
            payload = {"page_size": 500}
            if page_token:
                payload["page_token"] = page_token

            resp = await client.post(
                search_url, headers=storage._auth_header(), json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                print(f"❌ 查询失败: {data}")
                return

            items = data.get("data", {}).get("items", [])
            all_record_ids.extend(
                [item["record_id"] for item in items if item.get("record_id")]
            )

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token")

    print(f"📊 找到{len(all_record_ids)}条记录")

    if not all_record_ids:
        print("✅ 表格已经是空的")
        return

    # 批量删除
    delete_url = f"{storage.base_url}/bitable/v1/apps/{storage.settings.feishu.bitable_app_token}/tables/{storage.settings.feishu.bitable_table_id}/records/batch_delete"

    async with httpx.AsyncClient(timeout=10) as client:
        for i in range(0, len(all_record_ids), 500):
            batch = all_record_ids[i : i + 500]
            delete_resp = await client.post(
                delete_url, headers=storage._auth_header(), json={"records": batch}
            )
            delete_resp.raise_for_status()

            if delete_resp.json().get("code") != 0:
                print(f"❌ 删除失败: {delete_resp.json()}")
                return

            print(f"✅ 已删除{len(batch)}条记录")

    print(f"\n🎉 成功清空飞书表格，共删除{len(all_record_ids)}条记录")


if __name__ == "__main__":
    asyncio.run(main())
