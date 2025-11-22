#!/usr/bin/env python3
"""分析最近一次arXiv采集的发布时间分布"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.arxiv_collector import ArxivCollector


async def main():
    """分析arXiv采集的时间分布"""

    print("正在采集arXiv数据...")
    print()

    collector = ArxivCollector()
    candidates = await collector.collect()

    print(f"采集到 {len(candidates)} 条arXiv候选")
    print()

    # 统计发布时间分布
    now = datetime.now()
    time_buckets = Counter()

    for candidate in candidates:
        if not candidate.publish_date:
            time_buckets["无发布时间"] += 1
            continue

        days_ago = (now - candidate.publish_date).days

        if days_ago < 7:
            bucket = "7天内"
        elif days_ago < 14:
            bucket = "7-14天"
        elif days_ago < 30:
            bucket = "14-30天"
        elif days_ago < 60:
            bucket = "30-60天"
        else:
            bucket = "60天以上"

        time_buckets[bucket] += 1

    print("===== arXiv候选发布时间分布 =====")
    print()
    for bucket in ["7天内", "7-14天", "14-30天", "30-60天", "60天以上", "无发布时间"]:
        count = time_buckets.get(bucket, 0)
        pct = count / len(candidates) * 100 if candidates else 0
        print(f"  {bucket.ljust(12)}: {count:3d}条 ({pct:5.1f}%)")

    print()
    print("===== 分析 =====")
    recent_7d = time_buckets.get("7天内", 0)
    recent_14d = recent_7d + time_buckets.get("7-14天", 0)
    recent_30d = recent_14d + time_buckets.get("14-30天", 0)

    print(f"最近7天内发布: {recent_7d}条 ({recent_7d/len(candidates)*100:.1f}%)")
    print(f"最近14天内发布: {recent_14d}条 ({recent_14d/len(candidates)*100:.1f}%)")
    print(f"最近30天内发布: {recent_30d}条 ({recent_30d/len(candidates)*100:.1f}%)")
    print()

    if recent_7d < 10:
        print("⚠️  7天窗口内的论文数量较少 (<10条)")
        print("   建议：将时间窗口扩大到14-21天，增加新论文覆盖")

    if recent_14d > 80:
        print("✅  14天窗口可覆盖大部分论文")

    # 展示最新的5篇论文
    print()
    print("===== 最新的5篇arXiv论文 =====")
    sorted_candidates = sorted(
        [c for c in candidates if c.publish_date],
        key=lambda x: x.publish_date,
        reverse=True
    )[:5]

    for i, c in enumerate(sorted_candidates, 1):
        days_ago = (now - c.publish_date).days
        print(f"{i}. {c.title[:60]}")
        print(f"   发布时间: {c.publish_date.strftime('%Y-%m-%d')} ({days_ago}天前)")
        print()


if __name__ == "__main__":
    asyncio.run(main())
