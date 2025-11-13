"""采集器模块导出"""

from src.collectors.arxiv_collector import ArxivCollector
from src.collectors.github_collector import GitHubCollector
from src.collectors.huggingface_collector import HuggingFaceCollector
from src.collectors.pwc_collector import PwCCollector

__all__ = [
    "ArxivCollector",
    "GitHubCollector",
    "HuggingFaceCollector",
    "PwCCollector",
]
