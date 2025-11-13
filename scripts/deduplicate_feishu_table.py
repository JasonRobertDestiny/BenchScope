"""去重飞书Bitable数据（保留每个URL的最新记录）

用法: python scripts/deduplicate_feishu_table.py
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.storage.feishu_storage import FeishuStorage


async def main():
    storage = FeishuStorage()
    await storage._ensure_access_token()

    # 1. 获取所有记录
    all_records = []
    page_token = None

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            url = f"{storage.base_url}/bitable/v1/apps/{storage.settings.feishu.bitable_app_token}/tables/{storage.settings.feishu.bitable_table_id}/records/search"
            payload = {"page_size": 500}
            if page_token:
                payload["page_token"] = page_token

            resp = await client.post(url, headers=storage._auth_header(), json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                print(f"❌ 查询失败: {data}")
                return

            items = data.get("data", {}).get("items", [])
            all_records.extend(items)

            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token")

    print(f"📊 飞书表格总记录数: {len(all_records)}")

    # 2. 按URL分组
    url_to_records = defaultdict(list)
    url_field_name = storage.FIELD_MAPPING["url"]

    for record in all_records:
        fields = record.get("fields", {})
        url_obj = fields.get(url_field_name)

        url_value = None
        if isinstance(url_obj, dict):
            url_value = url_obj.get("link")
        elif isinstance(url_obj, str):
            url_value = url_obj

        if url_value:
            url_to_records[url_value].append({
                "record_id": record.get("record_id"),
                "created_time": record.get("created_time", 0),
            })

    # 3. 找出重复记录
    to_delete = []

    for url, records in url_to_records.items():
        if len(records) > 1:
            print(f"\n⚠️  URL重复{len(records)}次: {url[:60]}...")
            records_sorted = sorted(records, key=lambda x: x["created_time"], reverse=True)
            for old_record in records_sorted[1:]:
                to_delete.append(old_record["record_id"])

    if not to_delete:
        print("\n✅ 无重复记录")
        return

    print(f"\n📋 将删除{len(to_delete)}条重复记录")
    confirm = input("确认删除吗？(输入 'yes' 确认): ")

    if confirm.lower() != "yes":
        print("❌ 操作已取消")
        return

    # 4. 批量删除
    async with httpx.AsyncClient(timeout=10) as client:
        delete_url = f"{storage.base_url}/bitable/v1/apps/{storage.settings.feishu.bitable_app_token}/tables/{storage.settings.feishu.bitable_table_id}/records/batch_delete"

        for i in range(0, len(to_delete), 500):
            batch = to_delete[i : i + 500]
            delete_resp = await client.post(delete_url, headers=storage._auth_header(), json={"records": batch})
            delete_resp.raise_for_status()

            if delete_resp.json().get("code") != 0:
                print(f"❌ 删除失败: {delete_resp.json()}")
                return

            print(f"✅ 已删除{len(batch)}条重复记录")

    print(f"\n🎉 去重完成！保留{len(url_to_records)}条唯一记录")


if __name__ == "__main__":
    asyncio.run(main())
