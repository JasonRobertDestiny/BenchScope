"""飞书Webhook通知"""
from __future__ import annotations

import asyncio
import base64
import hmac
import hashlib
import logging
import time
from datetime import datetime
from typing import List, Optional

import httpx

from src.common import constants
from src.config import Settings, get_settings
from src.models import ScoredCandidate

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书Webhook卡片通知"""

    def __init__(self, webhook_url: Optional[str] = None, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.webhook_url = webhook_url or self.settings.feishu.webhook_url

    async def notify(self, candidates: List[ScoredCandidate]) -> None:
        if not self.webhook_url:
            logger.warning("未配置飞书Webhook,跳过通知")
            return

        if not candidates:
            logger.info("无候选需要通知")
            return

        qualified = [c for c in candidates if c.total_score >= constants.MIN_TOTAL_SCORE]
        if not qualified:
            logger.info("无高分候选,跳过通知")
            return

        high_priority = [c for c in qualified if c.priority == "high"]
        # 发送所有high优先级候选（移除[:3]限制）
        for candidate in high_priority:
            await self.send_card("🔥 发现高质量Benchmark候选", candidate)
            await asyncio.sleep(0.5)

        summary = self._build_summary_text(qualified)
        await self.send_text(summary)

    async def send_card(self, title: str, candidate: ScoredCandidate) -> None:
        """发送单条候选的卡片消息"""

        card = self._build_card(title, candidate)
        await self._send_webhook(card)

    async def send_text(self, message: str) -> None:
        """发送纯文本消息"""

        if not self.webhook_url:
            logger.warning("未配置飞书Webhook,跳过通知")
            return

        payload = {"msg_type": "text", "content": {"text": message}}
        await self._send_webhook(payload)

    def _build_summary_text(self, candidates: List[ScoredCandidate]) -> str:
        high = sum(1 for c in candidates if c.priority == "high")
        medium = sum(1 for c in candidates if c.priority == "medium")
        avg_score = sum(c.total_score for c in candidates) / len(candidates)
        return (
            "本次采集完成:\n"
            f"- 高优先级: {high} 条\n"
            f"- 中优先级: {medium} 条\n"
            f"- 平均分: {avg_score:.2f}/10\n"
            "请查看卡片了解详细候选信息。"
        )

    def _build_card(self, title: str, candidate: ScoredCandidate) -> dict:
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(candidate.priority, "🟢")
        content = (
            f"**标题**: {candidate.title[:100]}\n"
            f"**来源**: {candidate.source}\n"
            f"**总分**: {candidate.total_score:.2f}/10 ({emoji} {candidate.priority})\n"
            f"**活跃度**: {candidate.activity_score:.1f} | **可复现性**: {candidate.reproducibility_score:.1f}\n\n"
            f"📊 **评分依据**:\n{candidate.reasoning[:400]}"
        )

        actions = [
            {
                "tag": "button",
                "text": {"content": "查看详情", "tag": "plain_text"},
                "url": candidate.url,
                "type": "default",
            },
            {
                "tag": "button",
                "text": {"content": "📊 查看完整表格", "tag": "plain_text"},
                "url": "https://jcnqgpxcjdms.feishu.cn/base/WgI0bpHRVacs43skW24cR6JznWg?table=tblv2kzbzt4S2NSk&view=vewiJRxzFs",
                "type": "default",
            },
        ]

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue" if candidate.priority == "high" else "green",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                    {"tag": "action", "actions": actions},
                ],
            },
        }

    async def _send_webhook(self, payload: dict) -> None:
        """发送Webhook，支持签名验证

        飞书Webhook签名算法:
        1. 拼接字符串: timestamp + "\\n" + secret
        2. 使用HMAC-SHA256计算签名
        3. Base64编码签名结果

        文档: https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
        """
        # 如果配置了webhook_secret，添加签名
        if self.settings.feishu.webhook_secret:
            timestamp = int(time.time())
            sign = self._generate_signature(timestamp, self.settings.feishu.webhook_secret)
            payload["timestamp"] = str(timestamp)
            payload["sign"] = sign
            logger.debug("Webhook签名已添加: timestamp=%s", timestamp)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self.webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"飞书Webhook返回错误: {data}")
            if payload.get("msg_type") == "interactive":
                logger.info("✅ 飞书卡片推送成功")
            else:
                logger.info("✅ 飞书文本推送成功")

    def _generate_signature(self, timestamp: int, secret: str) -> str:
        """生成飞书Webhook签名

        Args:
            timestamp: Unix时间戳（秒）
            secret: Webhook签名密钥

        Returns:
            Base64编码的HMAC-SHA256签名
        """
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode('utf-8')
