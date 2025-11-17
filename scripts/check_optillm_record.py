#!/usr/bin/env python3
"""临时脚本：查询OptiLLM记录的摘要内容"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import get_settings


async def check_optillm():
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

        # 获取所有记录（分页）
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/search"
        headers = {"Authorization": f"Bearer {access_token}"}

        all_items = []
        page_token = None

        # 获取所有记录
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

            # 检查是否还有更多数据
            has_more = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token")

            if not has_more:
                break

        print(f'总记录数: {len(all_items)}\n')

        # 查找optillm相关记录
        optillm_records = []
        for item in all_items:
            fields = item.get("fields", {})
            title = fields.get('标题', [{}])[0].get('text', '') if fields.get('标题') else ''

            if 'optillm' in title.lower():
                optillm_records.append((item, fields, title))

        print(f'找到 {len(optillm_records)} 条 OptiLLM 相关记录:\n')

        for idx, (item, fields, title) in enumerate(optillm_records, 1):
            print(f'{"="*80}')
            print(f'记录 {idx}')
            print(f'{"="*80}')
            print(f'标题: {title}')

            # 安全提取字段
            def safe_get(field_name, key='text'):
                field_data = fields.get(field_name)
                if not field_data or not isinstance(field_data, list) or len(field_data) == 0:
                    return 'N/A'
                return field_data[0].get(key, 'N/A')

            url_val = safe_get('URL', 'link')
            print(f'URL: {url_val}')

            source = safe_get('来源')
            print(f'来源: {source}')

            abstract = safe_get('摘要')
            print(f'\n【摘要】:\n{abstract}\n')

            score = safe_get('总分')
            print(f'总分: {score}')

            reasoning = safe_get('评分依据')
            print(f'\n【评分依据】:\n{reasoning}\n')

            priority = safe_get('优先级')
            publish_date = safe_get('发布日期')

            print(f'优先级: {priority}')
            print(f'发布日期: {publish_date}')
            print()


if __name__ == '__main__':
    asyncio.run(check_optillm())
