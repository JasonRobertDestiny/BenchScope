"""飞书多维表格去重脚本（慎用：会删除记录）

策略：
- 以 (title, source, publish_date) 为键去重，保留最新创建的记录，其余删除。
- publish_date 为空的视为 "unknown"，键为 (title, source, "unknown")。

使用前确认：
- 已配置飞书 app_id/app_secret/bitable_app_token/table_id。
- 先用 analyze_bitable.py 观察重复情况。

运行方式：
    python scripts/dedupe_bitable.py --dry-run   # 只打印将删除的记录ID
    python scripts/dedupe_bitable.py             # 实际删除
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import httpx

# 将项目根目录加入路径
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.storage.feishu_storage import FeishuAPIError

# 去重前的最小标题长度，允许更宽以覆盖空格标题
MIN_TITLE_LEN = 1
# 允许参与去重的来源白名单，避免误删其他实验性来源
ALLOWED_SOURCES = {
    "arxiv",
    "github",
    "huggingface",
    "helm",
    "dbengines",
    "techempower",
}

# 兼容飞书多维表字段名（中英文）
TITLE_KEYS = ["title", "标题"]
SOURCE_KEYS = ["source", "来源"]
PUBLISH_DATE_KEYS = ["publish_date", "发布日期"]


def _extract_text_field(fields: dict[str, Any], keys: list[str]) -> str:
    """优先按 keys 提取文本字段，兼容 list/dict 结构。"""
    for k in keys:
        if k not in fields or fields[k] is None:
            continue
        val = fields[k]
        if isinstance(val, str):
            return val
        # 飞书多维表常见结构: [{'text': 'xxx', 'type': 'text'}]
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict) and "text" in first:
                return str(first.get("text") or "")
            if isinstance(first, str):
                return first
    return ""


def _extract_publish_date(fields: dict[str, Any]) -> datetime | None:
    """提取发布日期，支持毫秒时间戳或 ISO 字符串。"""
    for k in PUBLISH_DATE_KEYS:
        if k not in fields or fields[k] is None:
            continue
        pub = fields[k]
        if isinstance(pub, (int, float)):
            try:
                return datetime.fromtimestamp(pub / 1000)
            except Exception:
                continue
        if isinstance(pub, str) and pub:
            try:
                return datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
        if isinstance(pub, datetime):
            return pub
    return None


def build_dedupe_key(fields: dict[str, Any]) -> tuple[str, str, str] | None:
    title = _extract_text_field(fields, TITLE_KEYS).strip().lower()
    source = _extract_text_field(fields, SOURCE_KEYS).strip().lower()
    # 标题过短或来源缺失/不在白名单时跳过，减少误删
    if len(title) < MIN_TITLE_LEN or not source or source not in ALLOWED_SOURCES:
        return None
    pub_dt = _extract_publish_date(fields)
    pub_key = pub_dt.strftime("%Y-%m-%d") if pub_dt else "unknown"
    return (title, source, pub_key)


async def fetch_all_records(settings, page_size=500, max_pages=50, view_id: str | None = None):
    base_url = "https://open.feishu.cn/open-apis"
    token_url = f"{base_url}/auth/v3/tenant_access_token/internal"
    payload = {"app_id": settings.feishu.app_id, "app_secret": settings.feishu.app_secret}
    async with httpx.AsyncClient(timeout=10) as client:
        tok_resp = await client.post(token_url, json=payload)
        tok_resp.raise_for_status()
        tok = tok_resp.json().get("tenant_access_token")
        if not tok:
            raise RuntimeError("获取tenant_access_token失败")

    headers = {"Authorization": f"Bearer {tok}"}
    records = []
    page_token = None
    for _ in range(max_pages):
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"{base_url}/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/search"
            payload: dict[str, Any] = {"page_size": page_size}  # 允许后续注入字符串 view_id
            if view_id:
                payload["view_id"] = view_id
            if page_token:
                payload["page_token"] = page_token
            for attempt in range(5):
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                break
            data = resp.json()
            if data.get("code") != 0:
                raise FeishuAPIError(data)
            items = data.get("data", {}).get("items", [])
            records.extend(items)
            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break
    return records, headers


async def delete_records(settings, headers, record_ids):
    base_url = "https://open.feishu.cn/open-apis"
    async with httpx.AsyncClient(timeout=10) as client:
        url = f"{base_url}/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/batch_delete"
        resp = await client.post(url, headers=headers, json={"record_ids": record_ids})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAPIError(data)
    return len(record_ids)


async def main(dry_run: bool, page_size: int, max_pages: int, view_id: str | None):
    settings = get_settings()
    records, headers = await fetch_all_records(settings, page_size=page_size, max_pages=max_pages, view_id=view_id)
    record_ids = [r.get("record_id") for r in records if r.get("record_id")]
    unique_ids = len(set(record_ids))
    print(f"共拉取记录 {len(records)} 条，唯一ID {unique_ids} 条（page_size={page_size}, max_pages={max_pages}, view_id={view_id or '默认'})")
    buckets = defaultdict(list)

    skipped = 0
    for item in records:
        fields = item.get("fields", {})
        key = build_dedupe_key(fields)
        if key is None:
            skipped += 1
            continue
        buckets[key].append(item)

    to_delete = []
    for items in buckets.values():
        if len(items) <= 1:
            continue
        # 保留创建时间最新的
        items_sorted = sorted(items, key=lambda x: x.get("created_time", 0), reverse=True)
        keep = items_sorted[0]
        drop = items_sorted[1:]
        to_delete.extend([d.get("record_id") for d in drop if d.get("record_id")])

    dup_groups = sum(1 for v in buckets.values() if len(v) > 1)
    print(f"发现重复组 {dup_groups} 组，将删除 {len(to_delete)} 条，跳过无效记录 {skipped} 条")

    # 列出前5个重复组，便于确认（仅dry-run打印）
    if dry_run and dup_groups:
        print("\n前5个重复组预览（title | source | date | 条数）:")
        shown = 0
        for key, items in buckets.items():
            if len(items) <= 1:
                continue
            title, source, pub = key
            print(f"- {title[:80]} | {source} | {pub} | {len(items)}")
            shown += 1
            if shown >= 5:
                break

    # 安全阈值，避免误删过多记录
    MAX_DELETE = 2000
    if not dry_run and len(to_delete) > MAX_DELETE:
        print(f"⚠️ 计划删除 {len(to_delete)} 条，超过安全阈值 {MAX_DELETE}，已停止。请检查数据后重试或调整阈值。")
        return

    if dry_run or not to_delete:
        return

    # 分批删除，避免超限
    batch = 200
    deleted = 0
    for i in range(0, len(to_delete), batch):
        ids = to_delete[i : i + batch]
        deleted += await delete_records(settings, headers, ids)
        print(f"已删除 {deleted}/{len(to_delete)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="飞书多维表去重（按title+source+date）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将删除的条数，不实际删除")
    parser.add_argument("--page-size", type=int, default=500, help="分页大小（默认500，飞书上限500）")
    parser.add_argument("--max-pages", type=int, default=50, help="最多拉取分页数，避免请求过多")
    parser.add_argument("--view-id", type=str, default=None, help="指定view_id，仅对该视图的数据去重")
    args = parser.parse_args()

    asyncio.run(main(args.dry_run, args.page_size, args.max_pages, args.view_id))
