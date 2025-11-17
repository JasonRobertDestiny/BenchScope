"""GitHub Release 版本跟踪任务"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# 将项目根目录加入sys.path以便脚本直接运行
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.notifier.feishu_notifier import FeishuNotifier
from src.storage.storage_manager import StorageManager
from src.tracker.github_tracker import GitHubReleaseTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    storage = StorageManager()

    logger.info("从飞书Bitable读取URL列表...")
    existing_urls = await storage.get_existing_urls()
    github_urls = sorted(url for url in existing_urls if "github.com" in url)
    logger.info("发现 %d 个GitHub仓库", len(github_urls))

    if not github_urls:
        logger.info("无GitHub仓库需要跟踪")
        return

    github_token = os.getenv("GITHUB_TOKEN")
    tracker = GitHubReleaseTracker(
        db_path=str(settings.sqlite_path), github_token=github_token
    )
    new_releases = await tracker.check_updates(github_urls)

    if not new_releases:
        logger.info("无新Release")
        return

    notifier = FeishuNotifier(settings=settings)
    for release in new_releases:
        message = (
            f"**GitHub Release 更新**\n\n"
            f"仓库: {release.repo_url}\n"
            f"版本: {release.tag_name}\n"
            f"发布时间: {release.published_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"**更新说明**:\n{release.release_notes[:500]}\n\n"
            f"🔗 查看详情: {release.html_url}"
        )
        await notifier.send_text(message)
        await asyncio.sleep(0.5)

    logger.info("GitHub Release 跟踪完成 -> 新版本 %d 条", len(new_releases))


if __name__ == "__main__":
    asyncio.run(main())
