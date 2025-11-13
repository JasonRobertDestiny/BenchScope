"""全局配置加载逻辑"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import yaml

from src.common import constants

# 明确加载.env.local文件（覆盖.env）
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.local", override=True)


@dataclass(slots=True)
class OpenAISettings:
    api_key: str
    model: str = constants.LLM_DEFAULT_MODEL
    base_url: Optional[str] = None


@dataclass(slots=True)
class RedisSettings:
    url: str = constants.REDIS_DEFAULT_URL


@dataclass(slots=True)
class FeishuSettings:
    app_id: str
    app_secret: str
    bitable_app_token: str
    bitable_table_id: str
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None  # Webhook签名密钥（可选）


@dataclass(slots=True)
class LoggingSettings:
    level: str
    directory: Path
    file_name: str = constants.LOG_FILE_NAME


@dataclass(slots=True)
class HuggingFaceSourceSettings:
    keywords: list[str] = field(default_factory=lambda: constants.HUGGINGFACE_KEYWORDS.copy())
    task_categories: list[str] = field(
        default_factory=lambda: constants.HUGGINGFACE_TASK_CATEGORIES.copy()
    )
    min_downloads: int = constants.HUGGINGFACE_MIN_DOWNLOADS
    limit: int = constants.HUGGINGFACE_MAX_RESULTS


@dataclass(slots=True)
class SourcesSettings:
    huggingface: HuggingFaceSourceSettings = field(
        default_factory=HuggingFaceSourceSettings
    )


@dataclass(slots=True)
class Settings:
    openai: OpenAISettings
    redis: RedisSettings
    feishu: FeishuSettings
    logging: LoggingSettings
    sqlite_path: Path
    sources: SourcesSettings


def _get_env(key: str, default: Optional[str] = None) -> str:
    """读取环境变量并确保非空"""

    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"缺少必要环境变量: {key}")
    return value


# @lru_cache(maxsize=1)  # 临时禁用缓存，避免环境变量更新后读取旧值
def get_settings() -> Settings:
    """构建全局配置实例,使用缓存避免重复解析"""

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    sqlite_path_str = os.getenv("SQLITE_DB_PATH", constants.SQLITE_DB_PATH)
    sources_path = Path("config/sources.yaml")

    return Settings(
        openai=OpenAISettings(
            api_key=_get_env("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", constants.LLM_DEFAULT_MODEL),
            base_url=os.getenv("OPENAI_BASE_URL"),
        ),
        redis=RedisSettings(url=os.getenv("REDIS_URL", constants.REDIS_DEFAULT_URL)),
        feishu=FeishuSettings(
            app_id=_get_env("FEISHU_APP_ID", ""),
            app_secret=_get_env("FEISHU_APP_SECRET", ""),
            bitable_app_token=_get_env("FEISHU_BITABLE_APP_TOKEN", ""),
            bitable_table_id=_get_env("FEISHU_BITABLE_TABLE_ID", ""),
            webhook_url=os.getenv("FEISHU_WEBHOOK_URL"),
            webhook_secret=os.getenv("FEISHU_WEBHOOK_SECRET"),  # 可选：Webhook签名密钥
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            directory=log_dir,
        ),
        sqlite_path=Path(sqlite_path_str),
        sources=_load_sources_settings(sources_path),
    )


def _load_sources_settings(path: Path) -> SourcesSettings:
    """从YAML加载数据源配置,异常时使用默认值"""

    if not path.exists():
        return SourcesSettings()

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("加载sources.yaml失败: %s", exc)
        return SourcesSettings()

    huggingface_cfg = data.get("huggingface", {})
    return SourcesSettings(
        huggingface=HuggingFaceSourceSettings(
            keywords=huggingface_cfg.get("keywords")
            or constants.HUGGINGFACE_KEYWORDS.copy(),
            task_categories=huggingface_cfg.get("task_categories")
            or constants.HUGGINGFACE_TASK_CATEGORIES.copy(),
            min_downloads=int(
                huggingface_cfg.get("min_downloads", constants.HUGGINGFACE_MIN_DOWNLOADS)
            ),
            limit=int(huggingface_cfg.get("limit", constants.HUGGINGFACE_MAX_RESULTS)),
        )
    )


__all__ = ["get_settings", "Settings"]
