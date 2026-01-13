"""日期时间工具函数"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """确保datetime有UTC时区信息，naive datetime会被添加UTC时区

    Args:
        dt: 可能是None、naive或aware的datetime

    Returns:
        带UTC时区的datetime，或None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_age_days(publish_date: Optional[datetime]) -> Optional[int]:
    """计算发布距今天数

    Args:
        publish_date: 发布日期，可能是None或naive datetime

    Returns:
        距今天数，或None（如果publish_date为None）
    """
    if publish_date is None:
        return None

    publish_dt = ensure_utc(publish_date)
    if publish_dt is None:
        return None
    now = datetime.now(tz=timezone.utc)
    return (now - publish_dt).days


def get_retry_delay(attempt: int, delays: tuple[int, ...]) -> int:
    """获取重试延迟时间

    Args:
        attempt: 当前尝试次数（从1开始）
        delays: 延迟时间序列

    Returns:
        对应的延迟秒数
    """
    idx = min(attempt - 1, len(delays) - 1)
    return delays[idx]
