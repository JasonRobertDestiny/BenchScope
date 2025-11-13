"""飞书多维表格存储实现"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from src.common import constants
from src.config import Settings, get_settings
from src.models import ScoredCandidate

logger = logging.getLogger(__name__)


class FeishuAPIError(Exception):
    """飞书API异常"""


class FeishuStorage:
    """负责与飞书多维表格交互"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = "https://open.feishu.cn/open-apis"
        self.batch_size = constants.FEISHU_BATCH_SIZE
        self.rate_interval = constants.FEISHU_RATE_LIMIT_SECONDS
        self.access_token: Optional[str] = None
        self.token_expire_at: Optional[datetime] = None

    async def save(self, candidates: List[ScoredCandidate]) -> bool:
        """批量写入飞书,失败时抛异常"""

        if not candidates:
            return True

        await self._ensure_access_token()
        records = [self._build_record(candidate) for candidate in candidates]
        url = (
            f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/"
            f"tables/{self.settings.feishu.bitable_table_id}/records/batch_create"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            for start in range(0, len(records), self.batch_size):
                chunk = records[start : start + self.batch_size]
                payload = {"records": chunk}
                try:
                    resp = await client.post(url, headers=self._auth_header(), json=payload)
                    resp.raise_for_status()
                    logger.info(
                        "飞书批次写入成功(batch=%s,size=%s)",
                        start // self.batch_size + 1,
                        len(chunk),
                    )
                except httpx.HTTPStatusError as exc:  # noqa: BLE001
                    logger.error("飞书写入失败: %s - %s", exc.response.status_code, exc.response.text)
                    raise FeishuAPIError("批量写入失败") from exc

                await asyncio.sleep(self.rate_interval)

        return True

    async def _ensure_access_token(self) -> None:
        """确保token存在且未过期"""

        now = datetime.now()
        if self.access_token and self.token_expire_at and now < self.token_expire_at:
            return

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.settings.feishu.app_id,
            "app_secret": self.settings.feishu.app_secret,
        }
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data.get("tenant_access_token")
            expire_seconds = int(data.get("expire", 7200)) - 300
            self.token_expire_at = now + timedelta(seconds=max(expire_seconds, 600))
            logger.info("飞书access_token刷新成功")

    def _auth_header(self) -> dict[str, str]:
        """构造认证头"""

        if not self.access_token:
            raise FeishuAPIError("access_token不存在")
        return {"Authorization": f"Bearer {self.access_token}"}

    def _build_record(self, candidate: ScoredCandidate) -> dict[str, dict]:
        """将候选转换为飞书字段映射"""

        return {
            "fields": {
                "标题": candidate.raw.title,
                "来源": candidate.raw.source,
                "URL": candidate.raw.url,
                "摘要": candidate.raw.abstract or "",
                "创新性": candidate.score.innovation,
                "技术深度": candidate.score.technical_depth,
                "影响力": candidate.score.impact,
                "数据质量": candidate.score.data_quality,
                "可复现性": candidate.score.reproducibility,
                "总分": candidate.score.total_score,
                "优先级": candidate.score.priority,
                "状态": "待审阅",
                "发现时间": datetime.now().isoformat(),
                "GitHub Stars": candidate.raw.github_stars or 0,
                "GitHub URL": candidate.raw.github_url or "",
                "数据集URL": candidate.raw.dataset_url or "",
            }
        }
