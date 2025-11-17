#!/usr/bin/env python3
"""查找包含SWE相关的飞书记录"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import get_settings


async def check_swe():
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

        # 获取所有记录
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/search"
        headers = {"Authorization": f"Bearer {access_token}"}

        all_items = []
        page_token = None

        while True:
            payload = {"page_size": 500}
            if page_token:
                payload["page_token"] = page_token

            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                print(f'查询失败: {data.get("msg")}')
                return

            items = data.get("data", {}).get("items", [])
            all_items.extend(items)

            has_more = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token")

            if not has_more:
                break

        print(f'总记录数: {len(all_items)}\n')

        # 查找SWE相关记录（标题或摘要包含SWE）
        swe_records = []
        for item in all_items:
            fields = item.get("fields", {})

            def safe_get(field_name):
                field_data = fields.get(field_name)
                if not field_data or not isinstance(field_data, list) or len(field_data) == 0:
                    return ''
                return field_data[0].get('text', '')

            title = safe_get('标题')
            abstract = safe_get('摘要')

            if 'swe' in title.lower() or 'swe' in abstract.lower():
                swe_records.append((item, fields, title, abstract))

        print(f'找到 {len(swe_records)} 条包含SWE的记录:\n')

        for idx, (item, fields, title, abstract) in enumerate(swe_records, 1):
            print(f'{"="*80}')
            print(f'记录 {idx}')
            print(f'{"="*80}')
            print(f'标题: {title}')

            def safe_get_field(field_name, key='text'):
                field_data = fields.get(field_name)
                if not field_data or not isinstance(field_data, list) or len(field_data) == 0:
                    return 'N/A'
                return field_data[0].get(key, 'N/A')

            url_val = safe_get_field('URL', 'link')
            source = safe_get_field('来源')
            score = safe_get_field('总分')

            print(f'URL: {url_val}')
            print(f'来源: {source}')
            print(f'总分: {score}')
            print(f'\n【摘要前500字】:\n{abstract[:500]}...\n')


if __name__ == '__main__':
    asyncio.run(check_swe())
