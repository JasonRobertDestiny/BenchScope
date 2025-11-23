"""飞书多维表格数据分析脚本"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.storage.feishu_storage import FeishuStorage


def format_percentage(count: int, total: int) -> str:
    """格式化百分比"""
    if total == 0:
        return "0.0%"
    return f"{count / total * 100:.1f}%"


def normalize_field(value: Any) -> str:
    """标准化单值字段（字符串/列表/对象）返回字符串。"""
    if value is None:
        return "Unknown"
    if isinstance(value, dict):
        return str(value.get("text") or value.get("link") or "Unknown")
    if isinstance(value, list):
        if not value:
            return "Unknown"
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("text") or first.get("link") or "Unknown")
        return str(first)
    return str(value)


def normalize_domains(value: Any) -> list[str]:
    """标准化任务领域，返回列表便于统计。"""
    if value is None:
        return ["Unknown"]
    if isinstance(value, list):
        vals = [normalize_field(v) for v in value if v]
        return vals or ["Unknown"]
    return [normalize_field(value)]


def analyze_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """分析飞书记录"""

    total = len(records)
    if total == 0:
        return {"error": "无记录"}

    # 1. 按来源统计
    source_counts = Counter(r.get("source") or "Unknown" for r in records)

    # 2. 按任务领域统计（展开多值）
    task_domain_counts = Counter()
    for r in records:
        domains = normalize_domains(r.get("task_domain"))
        task_domain_counts.update(domains)

    # 3. 评分分布
    score_buckets = {"优秀(≥8)": 0, "良好(7-8)": 0, "合格(6-7)": 0, "低分(<6)": 0, "缺失": 0}
    scores = []
    for r in records:
        score = r.get("total_score")
        if score is None:
            score_buckets["缺失"] += 1
        elif score >= 8:
            score_buckets["优秀(≥8)"] += 1
            scores.append(score)
        elif score >= 7:
            score_buckets["良好(7-8)"] += 1
            scores.append(score)
        elif score >= 6:
            score_buckets["合格(6-7)"] += 1
            scores.append(score)
        else:
            score_buckets["低分(<6)"] += 1
            scores.append(score)

    avg_score = sum(scores) / len(scores) if scores else 0
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0

    # 4. 发布时间分布
    now = datetime.now()
    time_buckets = {
        "最近7天": 0,
        "8-30天": 0,
        "31-90天": 0,
        "91-180天": 0,
        "180天以上": 0,
        "缺失": 0,
    }
    for r in records:
        pub_date_raw = r.get("publish_date")
        if not pub_date_raw:
            time_buckets["缺失"] += 1
        else:
            # 解析日期字符串
            try:
                if isinstance(pub_date_raw, str):
                    pub_date = datetime.fromisoformat(pub_date_raw.replace("Z", "+00:00"))
                elif isinstance(pub_date_raw, datetime):
                    pub_date = pub_date_raw
                else:
                    time_buckets["缺失"] += 1
                    continue
                
                days_ago = (now - pub_date).days
                if days_ago <= 7:
                    time_buckets["最近7天"] += 1
                elif days_ago <= 30:
                    time_buckets["8-30天"] += 1
                elif days_ago <= 90:
                    time_buckets["31-90天"] += 1
                elif days_ago <= 180:
                    time_buckets["91-180天"] += 1
                else:
                    time_buckets["180天以上"] += 1
            except Exception:
                time_buckets["缺失"] += 1

    # 5. 缺失字段统计
    missing_fields = defaultdict(int)
    for r in records:
        # title
        title_val = normalize_field(r.get("title"))
        if title_val == "Unknown":
            missing_fields["title"] += 1
        # source
        if not r.get("source"):
            missing_fields["source"] += 1
        # task_domain
        task_val = normalize_field(r.get("task_domain"))
        if task_val == "Unknown":
            missing_fields["task_domain"] += 1
        # total_score
        if r.get("total_score") is None:
            missing_fields["total_score"] += 1
        # publish_date
        if not r.get("publish_date"):
            missing_fields["publish_date"] += 1

    # 6. 重复标题检测
    titles = [normalize_field(r.get("title")) for r in records]
    title_counts = Counter(t for t in titles if t != "Unknown")
    duplicates = {title: count for title, count in title_counts.items() if count > 1}

    # 7. 来源 × 任务领域交叉分析
    source_task_matrix = defaultdict(lambda: defaultdict(int))
    for r in records:
        source = r.get("source") or "Unknown"
        task = normalize_field(r.get("task_domain"))
        source_task_matrix[source][task] += 1

    return {
        "total": total,
        "source_counts": dict(source_counts),
        "task_domain_counts": dict(task_domain_counts),
        "score_buckets": score_buckets,
        "score_stats": {
            "avg": avg_score,
            "min": min_score,
            "max": max_score,
            "有评分数量": len(scores),
        },
        "time_buckets": time_buckets,
        "missing_fields": dict(missing_fields),
        "duplicates": duplicates,
        "source_task_matrix": {k: dict(v) for k, v in source_task_matrix.items()},
    }


def print_report(stats: dict[str, Any]) -> None:
    """打印分析报告"""

    print("\n" + "=" * 80)
    print("飞书多维表格数据分析报告")
    print("=" * 80)

    total = stats["total"]
    print(f"\n📊 总记录数: {total}")

    # 1. 来源分布
    print(f"\n{'=' * 80}")
    print("1️⃣ 按来源分布")
    print("-" * 80)
    for source, count in sorted(stats["source_counts"].items(), key=lambda x: x[1], reverse=True):
        pct = format_percentage(count, total)
        print(f"   {source:20s}: {count:4d} 条 ({pct})")

    # 2. 任务领域分布
    print(f"\n{'=' * 80}")
    print("2️⃣ 按任务领域分布")
    print("-" * 80)
    for task, count in sorted(stats["task_domain_counts"].items(), key=lambda x: x[1], reverse=True):
        pct = format_percentage(count, total)
        print(f"   {task:20s}: {count:4d} 条 ({pct})")

    # 3. 评分分布
    print(f"\n{'=' * 80}")
    print("3️⃣ 评分质量分布")
    print("-" * 80)
    for bucket, count in stats["score_buckets"].items():
        pct = format_percentage(count, total)
        print(f"   {bucket:15s}: {count:4d} 条 ({pct})")

    score_stats = stats["score_stats"]
    print(f"\n   评分统计:")
    print(f"   - 平均分: {score_stats['avg']:.2f}")
    print(f"   - 最高分: {score_stats['max']:.2f}")
    print(f"   - 最低分: {score_stats['min']:.2f}")
    print(f"   - 有评分数量: {score_stats['有评分数量']}/{total}")

    # 4. 发布时间分布
    print(f"\n{'=' * 80}")
    print("4️⃣ 发布时间新鲜度")
    print("-" * 80)
    for bucket, count in stats["time_buckets"].items():
        pct = format_percentage(count, total)
        print(f"   {bucket:15s}: {count:4d} 条 ({pct})")

    # 5. 数据质量问题
    print(f"\n{'=' * 80}")
    print("5️⃣ 数据质量问题")
    print("-" * 80)
    missing = stats["missing_fields"]
    if missing:
        print("   缺失字段统计:")
        for field, count in sorted(missing.items(), key=lambda x: x[1], reverse=True):
            pct = format_percentage(count, total)
            print(f"   - {field:20s}: {count:4d} 条缺失 ({pct})")
    else:
        print("   ✅ 无缺失字段")

    duplicates = stats["duplicates"]
    if duplicates:
        print(f"\n   ⚠️ 重复标题: {len(duplicates)} 个")
        print(f"   前5个重复最多的:")
        for title, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - {title[:60]}...: {count} 次")
    else:
        print("\n   ✅ 无重复标题")

    # 6. 来源 × 任务领域交叉分析
    print(f"\n{'=' * 80}")
    print("6️⃣ 来源 × 任务领域交叉分析（Top 5来源）")
    print("-" * 80)
    source_task = stats["source_task_matrix"]
    top_sources = sorted(stats["source_counts"].items(), key=lambda x: x[1], reverse=True)[:5]

    for source, _ in top_sources:
        tasks = source_task.get(source, {})
        if tasks:
            print(f"\n   {source}:")
            for task, count in sorted(tasks.items(), key=lambda x: x[1], reverse=True):
                print(f"      - {task:20s}: {count:3d} 条")

    print(f"\n{'=' * 80}")


async def main() -> None:
    print("正在读取飞书多维表格数据...")
    settings = get_settings()
    storage = FeishuStorage(settings)
    records = await storage.read_brief_records()

    if not records:
        print("⚠️ 未读取到任何记录")
        return

    print(f"✅ 成功读取 {len(records)} 条记录\n")
    stats = analyze_records(records)
    print_report(stats)
    print("\n分析完成！\n")


if __name__ == "__main__":
    asyncio.run(main())
