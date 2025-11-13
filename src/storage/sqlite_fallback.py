"""SQLite 降级存储"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Sequence

from src.common import constants
from src.config import Settings, get_settings
from src.models import BenchmarkScore, RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)


class SQLiteFallback:
    """在飞书不可用时将数据写入SQLite备份"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db_path = Path(self.settings.sqlite_path or constants.SQLITE_DB_PATH)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库结构"""

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fallback_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                score_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_to_feishu INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()
        conn.close()

    async def save(self, candidates: List[ScoredCandidate]) -> None:
        """写入SQLite,与飞书写入同构"""

        if not candidates:
            return

        await asyncio.to_thread(self._save_sync, candidates)
        logger.info("SQLite已备份%s条记录", len(candidates))

    def _save_sync(self, candidates: Sequence[ScoredCandidate]) -> None:
        conn = sqlite3.connect(self.db_path)
        for candidate in candidates:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO fallback_candidates
                    (title, source, url, score_json, raw_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.raw.title,
                        candidate.raw.source,
                        candidate.raw.url,
                        json.dumps(asdict(candidate.score)),
                        json.dumps(self._serialize_raw(candidate.raw)),
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("SQLite写入失败: %s", exc)
        conn.commit()
        conn.close()

    async def get_unsynced(self) -> List[ScoredCandidate]:
        """读取未同步到飞书的记录"""

        return await asyncio.to_thread(self._load_unsynced)

    def _load_unsynced(self) -> List[ScoredCandidate]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT score_json, raw_json FROM fallback_candidates WHERE synced_to_feishu = 0"
        )
        results: List[ScoredCandidate] = []
        for score_json, raw_json in cursor.fetchall():
            score_dict = json.loads(score_json)
            raw_dict = json.loads(raw_json)
            results.append(
                ScoredCandidate(
                    raw=self._deserialize_raw(raw_dict),
                    score=BenchmarkScore(**score_dict),
                )
            )
        conn.close()
        return results

    async def mark_synced(self, urls: List[str]) -> None:
        """同步成功后更新标记"""

        await asyncio.to_thread(self._mark_synced_sync, urls)

    def _mark_synced_sync(self, urls: Sequence[str]) -> None:
        conn = sqlite3.connect(self.db_path)
        for url in urls:
            conn.execute(
                "UPDATE fallback_candidates SET synced_to_feishu = 1 WHERE url = ?",
                (url,),
            )
        conn.commit()
        conn.close()

    async def cleanup_old_records(self, days: int = constants.SQLITE_RETENTION_DAYS) -> None:
        """清理已同步且超过指定天数的记录"""

        await asyncio.to_thread(self._cleanup_sync, days)

    def _cleanup_sync(self, days: int) -> None:
        cutoff = datetime.now() - timedelta(days=days)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM fallback_candidates WHERE synced_to_feishu = 1 AND created_at < ?",
            (cutoff,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _serialize_raw(raw: RawCandidate) -> dict:
        """转换RawCandidate为可JSON化结构"""

        payload = {
            "title": raw.title,
            "url": raw.url,
            "source": raw.source,
            "abstract": raw.abstract,
            "authors": raw.authors,
            "publish_date": raw.publish_date.isoformat() if raw.publish_date else None,
            "github_stars": raw.github_stars,
            "github_url": raw.github_url,
            "dataset_url": raw.dataset_url,
            "raw_metadata": raw.raw_metadata,
        }
        return payload

    @staticmethod
    def _deserialize_raw(data: dict) -> RawCandidate:
        """还原RawCandidate对象"""

        publish_date = data.get("publish_date")
        if publish_date:
            try:
                data["publish_date"] = datetime.fromisoformat(publish_date)
            except ValueError:
                data["publish_date"] = None
        return RawCandidate(**data)
