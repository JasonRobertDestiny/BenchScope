"""全局配置加载逻辑"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.common import constants

load_dotenv()


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


@dataclass(slots=True)
class LoggingSettings:
    level: str
    directory: Path
    file_name: str = constants.LOG_FILE_NAME


@dataclass(slots=True)
class Settings:
    openai: OpenAISettings
    redis: RedisSettings
    feishu: FeishuSettings
    logging: LoggingSettings
    sqlite_path: Path


def _get_env(key: str, default: Optional[str] = None) -> str:
    """读取环境变量并确保非空"""

    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"缺少必要环境变量: {key}")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """构建全局配置实例,使用缓存避免重复解析"""

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    sqlite_path_str = os.getenv("SQLITE_DB_PATH", constants.SQLITE_DB_PATH)

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
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            directory=log_dir,
        ),
        sqlite_path=Path(sqlite_path_str),
    )


__all__ = ["get_settings", "Settings"]
