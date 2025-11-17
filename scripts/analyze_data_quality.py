#!/usr/bin/env python3
"""分析飞书表格数据质量，识别字段缺失率和问题"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import get_settings


async def fetch_feishu_records() -> List[Dict[str, Any]]:
    """获取飞书表格的所有记录"""
    settings = get_settings()

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

        # 获取所有记录
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/search"

        all_records = []
        page_token = None

        while True:
            payload = {"page_size": 500}
            if page_token:
                payload["page_token"] = page_token

            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f'查询失败: {data.get("msg")}')

            items = data.get("data", {}).get("items", [])
            all_records.extend(items)

            has_more = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token")

            if not has_more:
                break

        return all_records


def analyze_field_quality(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析字段数据质量"""

    total = len(records)
    if total == 0:
        return {}

    # 统计各字段的填充率
    field_stats = {
        "发布日期": {"filled": 0, "empty": 0, "invalid": 0},
        "摘要": {"filled": 0, "empty": 0, "too_short": 0},
        "评估指标": {"filled": 0, "empty": 0},
        "基准模型": {"filled": 0, "empty": 0},
        "数据集规模": {"filled": 0, "empty": 0},
        "机构": {"filled": 0, "empty": 0},
        "作者": {"filled": 0, "empty": 0},
        "任务领域": {"filled": 0, "empty": 0},
        "数据集URL": {"filled": 0, "empty": 0},
        "GitHub URL": {"filled": 0, "empty": 0},
    }

    date_issues = []
    abstract_issues = []

    for idx, record in enumerate(records, 1):
        fields = record.get("fields", {})

        # 检查发布日期
        publish_date = fields.get("发布日期")
        if publish_date:
            field_stats["发布日期"]["filled"] += 1
            # 检查日期是否合理（Unix时间戳毫秒）
            try:
                dt = datetime.fromtimestamp(publish_date / 1000)
                # 2020年之前或2026年之后视为异常
                if dt.year < 2020 or dt.year > 2026:
                    field_stats["发布日期"]["invalid"] += 1
                    date_issues.append({
                        "record": idx,
                        "title": fields.get("标题", ""),
                        "date": dt.strftime("%Y-%m-%d"),
                        "source": fields.get("来源", ""),
                    })
            except:
                field_stats["发布日期"]["invalid"] += 1
        else:
            field_stats["发布日期"]["empty"] += 1

        # 检查摘要
        abstract = fields.get("摘要", "")
        if abstract:
            field_stats["摘要"]["filled"] += 1
            if len(abstract) < 100:
                field_stats["摘要"]["too_short"] += 1
                abstract_issues.append({
                    "record": idx,
                    "title": fields.get("标题", ""),
                    "abstract_len": len(abstract),
                    "source": fields.get("来源", ""),
                })
        else:
            field_stats["摘要"]["empty"] += 1

        # 其他字段
        for field_name, field_key in [
            ("评估指标", "评估指标"),
            ("基准模型", "基准模型"),
            ("数据集规模", "数据集规模"),
            ("机构", "机构"),
            ("作者", "作者"),
            ("任务领域", "任务领域"),
            ("数据集URL", "数据集URL"),
            ("GitHub URL", "GitHub URL"),
        ]:
            value = fields.get(field_key)
            if value:
                field_stats[field_name]["filled"] += 1
            else:
                field_stats[field_name]["empty"] += 1

    return {
        "total_records": total,
        "field_stats": field_stats,
        "date_issues": date_issues[:10],  # 前10个问题
        "abstract_issues": abstract_issues[:10],
    }


async def main():
    print("=" * 80)
    print("BenchScope 数据质量分析报告")
    print("=" * 80)
    print()

    print("正在获取飞书表格数据...")
    records = await fetch_feishu_records()
    print(f"✓ 获取到 {len(records)} 条记录")
    print()

    print("=" * 80)
    print("字段填充率分析")
    print("=" * 80)

    analysis = analyze_field_quality(records)
    total = analysis["total_records"]
    field_stats = analysis["field_stats"]

    for field_name, stats in field_stats.items():
        filled = stats["filled"]
        empty = stats["empty"]
        fill_rate = (filled / total * 100) if total > 0 else 0

        status = "✓" if fill_rate >= 70 else "⚠" if fill_rate >= 40 else "✗"
        print(f"{status} {field_name:15s} {fill_rate:5.1f}% ({filled:3d}/{total:3d})", end="")

        if field_name == "发布日期" and stats.get("invalid", 0) > 0:
            print(f"  [异常: {stats['invalid']}条]", end="")
        if field_name == "摘要" and stats.get("too_short", 0) > 0:
            print(f"  [过短(<100字): {stats['too_short']}条]", end="")

        print()

    # 发布日期问题
    if analysis["date_issues"]:
        print()
        print("=" * 80)
        print("发布日期异常记录（前10条）")
        print("=" * 80)
        for issue in analysis["date_issues"]:
            print(f"  - {issue['title'][:60]:60s} | {issue['date']:10s} | {issue['source']}")

    # 摘要问题
    if analysis["abstract_issues"]:
        print()
        print("=" * 80)
        print("摘要过短记录（前10条）")
        print("=" * 80)
        for issue in analysis["abstract_issues"]:
            print(f"  - {issue['title'][:60]:60s} | {issue['abstract_len']:3d}字 | {issue['source']}")

    # 总体评估
    print()
    print("=" * 80)
    print("总体评估")
    print("=" * 80)

    high_quality = sum(1 for s in field_stats.values() if (s["filled"] / total * 100) >= 70)
    medium_quality = sum(1 for s in field_stats.values() if 40 <= (s["filled"] / total * 100) < 70)
    low_quality = sum(1 for s in field_stats.values() if (s["filled"] / total * 100) < 40)

    print(f"高质量字段 (≥70%): {high_quality}/{len(field_stats)}")
    print(f"中等质量字段 (40-70%): {medium_quality}/{len(field_stats)}")
    print(f"低质量字段 (<40%): {low_quality}/{len(field_stats)}")

    if low_quality > 3:
        print("\n⚠️  数据质量需要优化！")
    elif medium_quality > 3:
        print("\n⚠️  数据完整性可以提升")
    else:
        print("\n✓ 数据质量良好")


if __name__ == "__main__":
    asyncio.run(main())
