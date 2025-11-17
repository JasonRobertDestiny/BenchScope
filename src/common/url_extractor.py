"""URL提取工具 - 从文本中提取数据集、论文等相关URL"""

from __future__ import annotations

import re
from typing import List, Optional


class URLExtractor:
    """从文本中提取特定类型的URL"""

    DATASET_SECTION_SCAN_LENGTH = 1000  # 限制Dataset章节的扫描长度

    # 数据集URL模式（优先级从高到低）
    DATASET_URL_PATTERNS = [
        # HuggingFace Datasets
        r"https?://huggingface\.co/datasets/[\w\-./]+",
        # GitHub仓库（包含data/dataset关键词的路径）
        r"https?://github\.com/[\w\-]+/[\w\-]+(?:/(?:tree|blob)/[\w\-/]+)?(?:data|dataset)",
        # Zenodo
        r"https?://(?:www\.)?zenodo\.org/record(?:s)?/\d+",
        r"https?://(?:www\.)?zenodo\.org/doi/[\w\-.]+",
        # Kaggle
        r"https?://(?:www\.)?kaggle\.com/datasets/[\w\-/]+",
        # Papers with Code datasets
        r"https?://paperswithcode\.com/dataset/[\w\-]+",
        # Google Drive (文件/文件夹分享链接)
        r"https?://drive\.google\.com/(?:file/d/|drive/folders/|open\?id=)[\w\-]+",
        # Dropbox
        r"https?://(?:www\.)?dropbox\.com/(?:s|sh)/[\w\-/]+",
        # 学术机构数据集 (.edu域名)
        r"https?://[\w\-.]+\.edu/[\w\-/]*(?:data|dataset|corpus)[\w\-/]*",
        # 通用的data/dataset链接
        r"https?://[\w\-.]+/[\w\-/]*(?:data|dataset|corpus)[\w\-/]*\.(?:zip|tar\.gz|tgz|tar)",
    ]

    # 论文URL模式
    PAPER_URL_PATTERNS = [
        # arXiv
        r"https?://arxiv\.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?",
        # ACL Anthology
        r"https?://aclanthology\.org/[\w\-.]+",
        # OpenReview
        r"https?://openreview\.net/(?:forum\?id=|pdf\?id=)[\w\-]+",
        # PMLR
        r"https?://proceedings\.mlr\.press/v\d+/[\w\-]+\.html",
        # NeurIPS
        r"https?://papers\.nips\.cc/paper/[\w\-/]+",
        # DOI链接
        r"https?://(?:dx\.)?doi\.org/[\w\-.]+/[\w\-.]+",
    ]

    # README中常见的数据集章节标题
    DATASET_SECTION_MARKERS = [
        r"##?\s*dataset",
        r"##?\s*data",
        r"##?\s*download",
        r"##?\s*getting\s+the\s+data",
        r"##?\s*corpus",
    ]

    @classmethod
    def extract_dataset_url(cls, text: str) -> Optional[str]:
        """从文本中提取第一个数据集URL

        优先级策略：
        1. HuggingFace Datasets (最高优先级)
        2. Zenodo/Kaggle等专业数据仓库
        3. GitHub带data/dataset路径
        4. 学术机构链接
        5. 通用下载链接

        Args:
            text: 待提取的文本（README、摘要等）

        Returns:
            第一个匹配的数据集URL，未找到返回None
        """
        if not text:
            return None

        text_lower = text.lower()

        # 先检查是否在"Dataset"章节附近
        dataset_section_start = cls._find_dataset_section(text_lower)

        # 如果找到Dataset章节，优先从该章节提取
        if dataset_section_start is not None:
            section_end = dataset_section_start + cls.DATASET_SECTION_SCAN_LENGTH
            section_text = text[dataset_section_start:section_end]
            url = cls._extract_from_patterns(section_text)
            if url:
                return url

        # 否则从整个文本提取
        return cls._extract_from_patterns(text)

    @classmethod
    def extract_paper_url(cls, text: str) -> Optional[str]:
        """从文本中提取第一个论文URL

        Args:
            text: 待提取的文本

        Returns:
            第一个匹配的论文URL，未找到返回None
        """
        if not text:
            return None

        for pattern in cls.PAPER_URL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    @classmethod
    def extract_all_dataset_urls(cls, text: str) -> List[str]:
        """从文本中提取所有数据集URL

        Args:
            text: 待提取的文本

        Returns:
            所有匹配的数据集URL列表（去重）
        """
        if not text:
            return []

        urls = set()
        for pattern in cls.DATASET_URL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.update(matches)

        return list(urls)

    @classmethod
    def _find_dataset_section(cls, text_lower: str) -> Optional[int]:
        """查找README中的Dataset章节起始位置

        Args:
            text_lower: 小写文本

        Returns:
            章节起始位置索引，未找到返回None
        """
        for marker_pattern in cls.DATASET_SECTION_MARKERS:
            match = re.search(marker_pattern, text_lower)
            if match:
                return match.start()
        return None

    @classmethod
    def _extract_from_patterns(cls, text: str) -> Optional[str]:
        """按优先级从文本中提取URL

        Args:
            text: 待提取的文本

        Returns:
            第一个匹配的URL
        """
        for pattern in cls.DATASET_URL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    @classmethod
    def is_valid_dataset_url(cls, url: str) -> bool:
        """验证URL是否为有效的数据集URL

        Args:
            url: 待验证的URL

        Returns:
            True if valid dataset URL
        """
        if not url:
            return False

        url_lower = url.lower()

        # 排除明显不是数据集的URL
        excluded_keywords = [
            "/issues/",
            "/pull/",
            "/releases/",
            "/wiki/",
            "/discussions/",
            "/actions/",
        ]

        for keyword in excluded_keywords:
            if keyword in url_lower:
                return False

        # 检查是否匹配任何数据集模式
        for pattern in cls.DATASET_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False
