"""存储管理器"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from src.common import constants
from src.models import ScoredCandidate
from src.storage.feishu_storage import FeishuAPIError, FeishuStorage
from src.storage.sqlite_fallback import SQLiteFallback

logger = logging.getLogger(__name__)


class StorageManager:
    """飞书主存储 + SQLite 降级"""

    def __init__(self, feishu: Optional[FeishuStorage] = None, sqlite: Optional[SQLiteFallback] = None) -> None:
        self.feishu = feishu or FeishuStorage()
        self.sqlite = sqlite or SQLiteFallback()

    async def save(self, candidates: List[ScoredCandidate]) -> bool:
        """优先写入飞书,失败则写入SQLite"""

        if not candidates:
            return True

        try:
            await self.feishu.save(candidates)
            await self.sqlite.cleanup_old_records(constants.SQLITE_RETENTION_DAYS)
            await self._sync_sqlite_backlog()
            return True
        except (FeishuAPIError, asyncio.TimeoutError) as exc:
            logger.error("飞书写入失败,降级SQLite: %s", exc)
            await self.sqlite.save(candidates)
            await self._send_alert("Feishu存储失败,已降级SQLite")
            return False

    async def _sync_sqlite_backlog(self) -> None:
        """尝试同步SQLite未写入记录"""

        pending = await self.sqlite.get_unsynced()
        if not pending:
            return

        try:
            await self.feishu.save(pending)
            await self.sqlite.mark_synced([item.raw.url for item in pending])
            logger.info("SQLite待同步记录已回写飞书:%s条", len(pending))
        except Exception as exc:  # noqa: BLE001
            logger.warning("SQLite回写失败,下次重试: %s", exc)

    async def _send_alert(self, message: str) -> None:
        """占位: 可接入飞书机器人实现异常告警"""

        logger.warning("[ALERT] %s", message)
