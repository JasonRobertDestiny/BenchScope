#!/usr/bin/env python3
"""测试分层推送策略

验证点:
1. 高优先级 (≥8.0) 发送交互式卡片
2. 中优先级 (6.0-7.9) 发送摘要文本 (Top 5)
3. 统计摘要包含高/中数量和平均分
4. 日志记录推送统计

用法:
    python scripts/test_layered_notification.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings
from src.models import ScoredCandidate
from src.notifier.feishu_notifier import FeishuNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_mock_candidates() -> list[ScoredCandidate]:
    """创建模拟候选数据

    Returns:
        - 2条高优先级 (8.2, 8.5)
        - 6条中优先级 (7.5, 7.2, 7.0, 6.8, 6.5, 6.2)
        - 1条低优先级 (5.5, 会被MIN_TOTAL_SCORE过滤)
    """
    candidates = [
        # 高优先级 (≥8.0)
        ScoredCandidate(
            title="WebArena: 真实环境下的Web Agent评测基准",
            url="https://github.com/web-arena-x/webarena",
            source="github",
            abstract="WebArena是第一个端到端的Web Agent评测基准，包含812个真实任务",
            github_stars=1200,
            github_url="https://github.com/web-arena-x/webarena",
            activity_score=9.0,
            reproducibility_score=9.0,
            license_score=8.0,
            novelty_score=8.5,
            relevance_score=9.0,
            reasoning="高活跃度(1200+ stars)、完整复现脚本、Apache-2.0许可、任务新颖且与MGX高度相关",
            publish_date=datetime(2024, 10, 15),
        ),
        ScoredCandidate(
            title="SWE-bench Verified: 2294个软件工程任务验证集",
            url="https://github.com/princeton-nlp/SWE-bench",
            source="github",
            abstract="SWE-bench Verified包含2294个经人工验证的真实GitHub Issue任务",
            github_stars=1500,
            github_url="https://github.com/princeton-nlp/SWE-bench",
            activity_score=9.5,
            reproducibility_score=9.0,
            license_score=8.0,
            novelty_score=7.5,
            relevance_score=8.0,
            reasoning="极高活跃度(1500+ stars)、完整数据集和评估脚本、MIT许可、Code Generation任务",
            publish_date=datetime(2024, 11, 1),
        ),

        # 中优先级 (6.0-7.9)
        ScoredCandidate(
            title="MiniWoB++: 100+网页交互任务的Benchmark",
            url="https://github.com/Farama-Foundation/miniwob-plusplus",
            source="github",
            abstract="MiniWoB++提供100+个模拟网页交互任务，用于Web Agent评测",
            github_stars=450,
            github_url="https://github.com/Farama-Foundation/miniwob-plusplus",
            activity_score=7.0,
            reproducibility_score=8.5,
            license_score=7.0,
            novelty_score=6.0,
            relevance_score=8.0,
            reasoning="中等活跃度、开源代码和环境、Apache许可、与WebAgent相关",
            publish_date=datetime(2024, 9, 20),
        ),
        ScoredCandidate(
            title="AgentBench: 多维度Agent评测框架",
            url="https://github.com/THUDM/AgentBench",
            source="github",
            abstract="AgentBench提供8个维度的Agent能力评测，覆盖编程、对话、工具使用等",
            github_stars=800,
            github_url="https://github.com/THUDM/AgentBench",
            activity_score=8.0,
            reproducibility_score=7.5,
            license_score=7.0,
            novelty_score=6.5,
            relevance_score=7.0,
            reasoning="高活跃度、部分任务可复现、Apache许可、综合Agent评测",
            publish_date=datetime(2024, 8, 10),
        ),
        ScoredCandidate(
            title="MATH-500: 数学推理能力测试集",
            url="https://github.com/openai/grade-school-math",
            source="github",
            abstract="MATH-500包含500道数学问题，测试LLM的推理和计算能力",
            github_stars=300,
            github_url="https://github.com/openai/grade-school-math",
            activity_score=6.0,
            reproducibility_score=8.0,
            license_score=7.0,
            novelty_score=6.0,
            relevance_score=7.5,
            reasoning="中等活跃度、完整数据集、MIT许可、推理任务",
            publish_date=datetime(2024, 7, 15),
        ),
        ScoredCandidate(
            title="HumanEval+: 扩展的代码生成评测",
            url="https://github.com/openai/human-eval",
            source="github",
            abstract="HumanEval+在原164题基础上增加了80+个测试用例",
            github_stars=500,
            github_url="https://github.com/openai/human-eval",
            activity_score=7.5,
            reproducibility_score=7.0,
            license_score=7.0,
            novelty_score=5.5,
            relevance_score=7.0,
            reasoning="较高活跃度、部分复现材料、MIT许可、Code Generation任务",
            publish_date=datetime(2024, 6, 20),
        ),
        ScoredCandidate(
            title="BrowserGym: Web浏览器自动化评测环境",
            url="https://github.com/ServiceNow/BrowserGym",
            source="github",
            abstract="BrowserGym提供真实浏览器环境下的Agent评测框架",
            github_stars=250,
            github_url="https://github.com/ServiceNow/BrowserGym",
            activity_score=6.5,
            reproducibility_score=7.0,
            license_score=6.0,
            novelty_score=7.0,
            relevance_score=6.5,
            reasoning="中等活跃度、环境可复现、GPL许可(扣分)、Web自动化任务",
            publish_date=datetime(2024, 10, 5),
        ),
        ScoredCandidate(
            title="Mind2Web: 真实网站的多步骤任务数据集",
            url="https://arxiv.org/abs/2306.06070",
            source="arxiv",
            abstract="Mind2Web包含2000+个真实网站的多步骤操作任务",
            github_stars=None,
            activity_score=6.0,
            reproducibility_score=6.5,
            license_score=6.0,
            novelty_score=7.0,
            relevance_score=6.5,
            reasoning="arXiv论文、数据集部分开源、任务与WebAgent相关",
            publish_date=datetime(2024, 9, 1),
        ),

        # 低优先级 (<6.0, 会被过滤)
        ScoredCandidate(
            title="Simple Code Benchmark: 入门级代码生成测试",
            url="https://github.com/example/simple-code",
            source="github",
            abstract="包含50个简单的Python函数生成任务",
            github_stars=50,
            github_url="https://github.com/example/simple-code",
            activity_score=4.0,
            reproducibility_score=5.0,
            license_score=6.0,
            novelty_score=4.0,
            relevance_score=5.0,
            reasoning="低活跃度、任务简单、与现有Benchmark重复度高",
            publish_date=datetime(2024, 5, 10),
        ),
    ]

    logger.info(f"创建了 {len(candidates)} 个模拟候选")
    logger.info(f"高优先级: {sum(1 for c in candidates if c.priority == 'high')} 条")
    logger.info(f"中优先级: {sum(1 for c in candidates if c.priority == 'medium')} 条")
    logger.info(f"低优先级: {sum(1 for c in candidates if c.priority == 'low')} 条")

    return candidates


async def main(dry_run: bool = False) -> None:
    """测试分层推送"""
    logger.info("=" * 60)
    logger.info("测试分层推送策略")
    logger.info("=" * 60)

    # 创建模拟候选
    candidates = create_mock_candidates()

    # 配置
    settings = get_settings()
    if not settings.feishu.webhook_url:
        logger.error("未配置FEISHU_WEBHOOK_URL，无法测试推送")
        logger.info("请在.env.local中配置FEISHU_WEBHOOK_URL")
        return

    if dry_run:
        logger.info("DRY-RUN模式：仅模拟推送逻辑，不实际发送")
        # 模拟推送逻辑
        qualified = [c for c in candidates if c.total_score >= 6.0]
        high = [c for c in qualified if c.priority == "high"]
        medium = [c for c in qualified if c.priority == "medium"]

        logger.info(f"预计推送: 高优先级{len(high)}条卡片, 中优先级{len(medium)}条摘要")
        for c in high:
            logger.info(f"  [高] {c.title[:50]}... ({c.total_score:.2f}分)")
        logger.info(f"  [中] Top 5摘要 (共{len(medium)}条)")
        for i, c in enumerate(sorted(medium, key=lambda x: x.total_score, reverse=True)[:5], 1):
            logger.info(f"    {i}. {c.title[:50]}... ({c.total_score:.2f}分)")
        return

    # 实际推送
    logger.info("准备推送到飞书群...")
    notifier = FeishuNotifier(settings=settings)

    try:
        await notifier.notify(candidates)
        logger.info("✅ 测试完成，请检查飞书群接收效果")
    except Exception as e:
        logger.error(f"❌ 推送失败: {e}", exc_info=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试分层推送策略")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅模拟推送逻辑，不实际发送",
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
