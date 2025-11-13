"""飞书Webhook通知"""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from src.common import constants
from src.config import Settings, get_settings
from src.models import ScoredCandidate

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """将高分候选推送到飞书群"""

    def __init__(self, webhook_url: Optional[str] = None, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.webhook_url = webhook_url or self.settings.feishu.webhook_url

    async def notify(self, candidates: List[ScoredCandidate], top_k: int = constants.NOTIFY_TOP_K) -> None:
        """推送Top K候选"""

        if not self.webhook_url:
            logger.warning("未配置飞书Webhook,跳过通知")
            return

        if not candidates:
            logger.info("无候选需要通知")
            return

        message = self._build_message(candidates[:top_k])
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.post(
                    self.webhook_url,
                    json={"msg_type": "text", "content": {"text": message}},
                )
                resp.raise_for_status()
                logger.info("飞书通知已发送,候选数:%s", min(len(candidates), top_k))
            except httpx.HTTPError as exc:  # noqa: BLE001
                logger.error("飞书通知失败: %s", exc)

    def _build_message(self, candidates: List[ScoredCandidate]) -> str:
        """格式化文本内容"""

        lines = ["BenchScope 今日Top候选:"]
        for idx, candidate in enumerate(candidates, start=1):
            lines.append(
                f"{idx}. {candidate.raw.title} | 总分 {candidate.score.total_score} | 优先级 {candidate.score.priority}\n"
                f"{candidate.raw.url}"
            )
        return "\n".join(lines)
