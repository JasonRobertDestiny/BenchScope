"""分析Phase 7评分结果"""
import asyncio
import logging
from collections import Counter

import httpx

from src.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def fetch_all_records():
    """从飞书表格获取所有记录"""
    settings = get_settings()

    # 获取access token
    async with httpx.AsyncClient(timeout=10) as client:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_resp = await client.post(
            token_url,
            json={
                "app_id": settings.feishu.app_id,
                "app_secret": settings.feishu.app_secret,
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["tenant_access_token"]

        # 分页获取所有记录
        all_records = []
        page_token = None

        while True:
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{settings.feishu.bitable_app_token}/tables/{settings.feishu.bitable_table_id}/records/search"
            payload = {"page_size": 500}
            if page_token:
                payload["page_token"] = page_token

            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise Exception(f"飞书查询失败: {data}")

            items = data.get("data", {}).get("items", [])
            all_records.extend(items)

            # 检查是否有下一页
            has_more = data.get("data", {}).get("has_more", False)
            if not has_more:
                break

            page_token = data.get("data", {}).get("page_token")

    return all_records


async def analyze_scores():
    """拉取飞书表格最新60条数据并分析评分"""

    # 拉取所有记录
    logger.info("正在从飞书表格拉取所有记录...")
    records = await fetch_all_records()
    logger.info(f"总记录数: {len(records)}")

    # 按创建时间排序，取最新60条
    records = sorted(
        records,
        key=lambda x: x.get("fields", {}).get("创建时间", 0),
        reverse=True,
    )[:60]

    logger.info(f"成功拉取{len(records)}条记录\n")

    # 提取关键字段
    candidates = []
    for record in records:
        fields = record.get("fields", {})
        candidate = {
            "title": fields.get("标题", [""])[0] if isinstance(fields.get("标题"), list) else fields.get("标题", ""),
            "source": fields.get("来源", [""])[0] if isinstance(fields.get("来源"), list) else fields.get("来源", ""),
            "total_score": fields.get("总分", 0),
            "priority": fields.get("优先级", [""])[0] if isinstance(fields.get("优先级"), list) else fields.get("优先级", ""),
            "activity_score": fields.get("活跃度", 0),
            "reproducibility_score": fields.get("可复现性", 0),
            "license_score": fields.get("许可合规", 0),
            "novelty_score": fields.get("新颖性", 0),
            "relevance_score": fields.get("MGX适配度", 0),
        }
        candidates.append(candidate)

    # 统计分析
    logger.info("=" * 80)
    logger.info("Phase 7 评分结果分析")
    logger.info("=" * 80)

    # 1. 总分分布
    scores = [c["total_score"] for c in candidates]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0

    logger.info(f"\n📊 总分统计:")
    logger.info(f"  平均分: {avg_score:.2f}/10")
    logger.info(f"  最高分: {max_score:.2f}/10")
    logger.info(f"  最低分: {min_score:.2f}/10")

    # 分数段分布
    score_ranges = {
        "8-10分": sum(1 for s in scores if 8 <= s <= 10),
        "6-8分": sum(1 for s in scores if 6 <= s < 8),
        "4-6分": sum(1 for s in scores if 4 <= s < 6),
        "0-4分": sum(1 for s in scores if s < 4),
    }
    logger.info(f"\n  分数段分布:")
    for range_name, count in score_ranges.items():
        percentage = (count / len(scores) * 100) if scores else 0
        logger.info(f"    {range_name}: {count}条 ({percentage:.1f}%)")

    # 2. 优先级分布
    priority_counter = Counter(c["priority"] for c in candidates)
    logger.info(f"\n📊 优先级分布:")
    for priority, count in priority_counter.most_common():
        percentage = (count / len(candidates) * 100) if candidates else 0
        logger.info(f"  {priority}: {count}条 ({percentage:.1f}%)")

    # 3. 来源分布
    source_counter = Counter(c["source"] for c in candidates)
    logger.info(f"\n📊 来源分布:")
    for source, count in source_counter.most_common():
        percentage = (count / len(candidates) * 100) if candidates else 0
        logger.info(f"  {source}: {count}条 ({percentage:.1f}%)")

    # 4. 5维评分平均值
    logger.info(f"\n📊 5维评分平均:")
    logger.info(f"  活跃度: {sum(c['activity_score'] for c in candidates) / len(candidates):.2f}/10")
    logger.info(f"  可复现性: {sum(c['reproducibility_score'] for c in candidates) / len(candidates):.2f}/10")
    logger.info(f"  许可合规: {sum(c['license_score'] for c in candidates) / len(candidates):.2f}/10")
    logger.info(f"  新颖性: {sum(c['novelty_score'] for c in candidates) / len(candidates):.2f}/10")
    logger.info(f"  MGX适配度: {sum(c['relevance_score'] for c in candidates) / len(candidates):.2f}/10")

    # 5. 低分案例（<6分）
    low_score_candidates = [c for c in candidates if c["total_score"] < 6]
    logger.info(f"\n📊 低分案例分析（<6分，共{len(low_score_candidates)}条）:")
    for i, c in enumerate(low_score_candidates[:10], 1):
        logger.info(f"\n{i}. {c['title'][:60]}")
        logger.info(f"   来源: {c['source']} | 总分: {c['total_score']:.1f}")
        logger.info(f"   活跃度{c['activity_score']:.1f} | 可复现{c['reproducibility_score']:.1f} | 许可{c['license_score']:.1f} | 新颖{c['novelty_score']:.1f} | 适配{c['relevance_score']:.1f}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_scores())
