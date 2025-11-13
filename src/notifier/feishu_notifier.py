"""飞书Webhook通知"""
from __future__ import annotations

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
        top_k = sorted(qualified, key=lambda c: c.total_score, reverse=True)[: constants.NOTIFY_TOP_K]

        if not top_k:
            logger.info("无高分候选,跳过通知")
            return

        card = self._build_card(top_k)
        await self._send_webhook(card)

    def _build_card(self, candidates: List[ScoredCandidate]) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        elements = []
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        for idx, candidate in enumerate(candidates, 1):
            emoji = priority_emoji.get(candidate.priority, "🟢")
            content = (
                f"**{idx}. {emoji} [{candidate.priority.upper()}] {candidate.title[:80]}**\n\n"  # 标题增加到80字符
                f"总分: **{candidate.total_score:.1f}/10**\n"
                f"来源: {candidate.source} | 活跃度: {candidate.activity_score:.1f} | 可复现性: {candidate.reproducibility_score:.1f}\n\n"
                f"📊 {candidate.reasoning}\n\n"  # 完整显示，不截断
                f"🔗 [查看详情]({candidate.url})\n---"
            )

            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🎯 BenchScope 每日推荐 ({today})",
                    },
                    "template": "blue",
                },
                "elements": elements,
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
            logger.info("✅ 飞书通知推送成功: %d条", len(payload["card"]["elements"]))

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
