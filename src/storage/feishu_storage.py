"""飞书多维表格存储实现"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from src.common import constants
from src.config import Settings, get_settings
from src.models import ScoredCandidate

logger = logging.getLogger(__name__)


class FeishuAPIError(Exception):
    """飞书API异常"""


class FeishuStorage:
    """负责与飞书多维表格交互"""

    FIELD_MAPPING: Dict[str, str] = {
        # 基础信息组 (5个字段)
        "title": "标题",
        "source": "来源",
        "url": "URL",
        "abstract": "摘要",
        "publish_date": "发布日期",  # 修复: "开源时间" → "发布日期"
        # 评分信息组 (8个字段)
        "activity_score": "活跃度",
        "reproducibility_score": "可复现性",
        "license_score": "许可合规",  # 修复: "许可合规性" → "许可合规"
        "novelty_score": "新颖性",  # 修复: "任务新颖性" → "新颖性"
        "relevance_score": "MGX适配度",
        "total_score": "总分",
        "priority": "优先级",
        "reasoning": "评分依据",
        # Benchmark特征组 (8个字段)
        "task_domain": "任务领域",
        "metrics": "评估指标",  # 修复: "评估指标（结构化）" → "评估指标"
        "baselines": "基准模型",
        "institution": "机构",
        "authors": "作者",
        "dataset_size": "数据集规模",
        "dataset_size_description": "数据集规模描述",
        "dataset_url": "数据集URL",  # 新增：数据集下载链接
        # GitHub信息组 (3个字段)
        "github_stars": "GitHub Stars",
        "github_url": "GitHub URL",
        "license_type": "许可证",  # 修复: "License类型" → "许可证"
    }

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = "https://open.feishu.cn/open-apis"
        self.batch_size = constants.FEISHU_BATCH_SIZE
        self.rate_interval = constants.FEISHU_RATE_LIMIT_DELAY
        self.access_token: Optional[str] = None
        self.token_expire_at: Optional[datetime] = None

    async def save(self, candidates: List[ScoredCandidate]) -> None:
        """批量写入飞书多维表格"""

        if not candidates:
            return

        await self._ensure_access_token()

        async with httpx.AsyncClient(timeout=10) as client:
            for start in range(0, len(candidates), self.batch_size):
                chunk = candidates[start : start + self.batch_size]
                records = [self._to_feishu_record(c) for c in chunk]
                await self._batch_create_records(client, records)

                if start + self.batch_size < len(candidates):
                    await asyncio.sleep(self.rate_interval)

    async def _batch_create_records(
        self, client: httpx.AsyncClient, records: List[dict]
    ) -> None:
        url = (
            f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/"
            f"tables/{self.settings.feishu.bitable_table_id}/records/batch_create"
        )
        try:
            resp = await client.post(
                url, headers=self._auth_header(), json={"records": records}
            )
            resp.raise_for_status()

            # 检查飞书API业务错误码
            data = resp.json()
            code = data.get("code")
            msg = data.get("msg", "")

            if code != 0:
                # 飞书API业务层面错误
                logger.error("飞书API业务错误: code=%s, msg=%s", code, msg)
                logger.error("请求payload前3条记录: %s", records[:3])
                raise FeishuAPIError(f"飞书API返回错误: {code} - {msg}")

            # 检查实际写入的记录数
            created_records = data.get("data", {}).get("records", [])
            actual_count = len(created_records)
            expected_count = len(records)

            if actual_count != expected_count:
                logger.warning(
                    "飞书写入数量不匹配: 预期%s条,实际%s条",
                    expected_count,
                    actual_count,
                )

            logger.info(
                "飞书批次写入成功: %s条 (实际创建%s条)", len(records), actual_count
            )

        except httpx.HTTPStatusError as exc:
            logger.error(
                "飞书写入HTTP错误: %s - %s", exc.response.status_code, exc.response.text
            )
            raise FeishuAPIError("批量写入失败") from exc

    async def _ensure_access_token(self) -> None:
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
        if not self.access_token:
            raise FeishuAPIError("access_token不存在")
        return {"Authorization": f"Bearer {self.access_token}"}

    @staticmethod
    def _clean_abstract(text: str | None, max_length: int = 300) -> str:
        """清理摘要文本，优化飞书表格显示

        - 移除换行符，用空格替代
        - 清理多余空格
        - 限制长度
        - 移除markdown格式符号
        """
        if not text:
            return ""

        # 移除换行符和tab，用空格替代
        cleaned = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        # 清理多余空格
        cleaned = " ".join(cleaned.split())

        # 移除常见markdown符号
        for char in ["**", "__", "##", "```"]:
            cleaned = cleaned.replace(char, "")

        # 限制长度（保留完整单词）
        if len(cleaned) > max_length:
            # 截断到max_length-3为...留出空间，然后在最后一个空格处断开
            truncated = cleaned[: max_length - 3]
            last_space = truncated.rfind(" ")
            if last_space > max_length * 0.8:  # 如果最后空格位置合理（不是太靠前）
                cleaned = truncated[:last_space] + "..."
            else:  # 否则直接截断
                cleaned = truncated + "..."

        return cleaned

    def _to_feishu_record(self, candidate: ScoredCandidate) -> dict:
        """转换ScoredCandidate为飞书记录格式

        注意事项:
        - URL字段需要对象格式: {"link": "..."}
        - 日期字段转换为字符串格式: "YYYY-MM-DD"
        - 数组字段转换为逗号分隔的字符串
        - 空值使用空字符串或0代替
        - 摘要字段清理换行符和长度，优化表格显示
        """
        fields = {
            # 基础信息
            self.FIELD_MAPPING["title"]: candidate.title,
            self.FIELD_MAPPING["source"]: candidate.source,
            self.FIELD_MAPPING["url"]: {"link": candidate.url},
            self.FIELD_MAPPING["abstract"]: self._clean_abstract(candidate.abstract),
            # 评分维度
            self.FIELD_MAPPING["activity_score"]: candidate.activity_score,
            self.FIELD_MAPPING[
                "reproducibility_score"
            ]: candidate.reproducibility_score,
            self.FIELD_MAPPING["license_score"]: candidate.license_score,
            self.FIELD_MAPPING["novelty_score"]: candidate.novelty_score,
            self.FIELD_MAPPING["relevance_score"]: candidate.relevance_score,
            self.FIELD_MAPPING["total_score"]: round(candidate.total_score, 2),
            self.FIELD_MAPPING["priority"]: candidate.priority,
            self.FIELD_MAPPING["reasoning"]: (candidate.reasoning or "")[
                : constants.FEISHU_REASONING_PREVIEW_LENGTH
            ],
        }

        # Phase 8新增字段 - 谨慎处理空值
        if hasattr(candidate, "github_stars") and candidate.github_stars is not None:
            fields[self.FIELD_MAPPING["github_stars"]] = candidate.github_stars

        if hasattr(candidate, "github_url") and candidate.github_url:
            fields[self.FIELD_MAPPING["github_url"]] = {"link": candidate.github_url}

        if hasattr(candidate, "authors") and candidate.authors:
            # 作者列表转换为逗号分隔字符串，限制长度
            authors_str = ", ".join(candidate.authors)[:200]
            fields[self.FIELD_MAPPING["authors"]] = authors_str

        if hasattr(candidate, "publish_date") and candidate.publish_date:
            # 飞书日期字段需要Unix时间戳(毫秒)
            timestamp_ms = int(candidate.publish_date.timestamp() * 1000)
            fields[self.FIELD_MAPPING["publish_date"]] = timestamp_ms

        if getattr(candidate, "task_domain", None):
            # 飞书多选字段需要数组格式
            task_domain = candidate.task_domain
            if isinstance(task_domain, str):
                # 如果是字符串,按逗号分割为数组
                task_domain_list = [d.strip() for d in task_domain.split(",")]
                fields[self.FIELD_MAPPING["task_domain"]] = task_domain_list
            elif isinstance(task_domain, list):
                # 如果已经是列表,直接使用
                fields[self.FIELD_MAPPING["task_domain"]] = task_domain

        if getattr(candidate, "metrics", None):
            metrics_str = ", ".join(candidate.metrics)[:200]
            fields[self.FIELD_MAPPING["metrics"]] = metrics_str

        if getattr(candidate, "baselines", None):
            baselines_str = ", ".join(candidate.baselines)[:200]
            fields[self.FIELD_MAPPING["baselines"]] = baselines_str

        if getattr(candidate, "institution", None):
            fields[self.FIELD_MAPPING["institution"]] = candidate.institution[:200]

        if getattr(candidate, "dataset_size", None) is not None:
            fields[self.FIELD_MAPPING["dataset_size"]] = candidate.dataset_size

        if getattr(candidate, "dataset_size_description", None):
            desc = candidate.dataset_size_description[:200]
            fields[self.FIELD_MAPPING["dataset_size_description"]] = desc

        if hasattr(candidate, "license_type") and candidate.license_type:
            fields[self.FIELD_MAPPING["license_type"]] = candidate.license_type

        if hasattr(candidate, "dataset_url") and candidate.dataset_url:
            fields[self.FIELD_MAPPING["dataset_url"]] = {"link": candidate.dataset_url}

        return {"fields": fields}

    async def get_existing_urls(self) -> set[str]:
        """查询飞书Bitable已存在的所有URL（用于去重）"""
        await self._ensure_access_token()

        existing_urls: set[str] = set()
        page_token = None

        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                url = f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/tables/{self.settings.feishu.bitable_table_id}/records/search"

                # 分页查询所有记录
                payload = {"page_size": 500}
                if page_token:
                    payload["page_token"] = page_token

                resp = await client.post(url, headers=self._auth_header(), json=payload)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    raise FeishuAPIError(f"飞书查询失败: {data}")

                # 提取URL字段
                items = data.get("data", {}).get("items", [])
                url_field_name = self.FIELD_MAPPING["url"]

                for item in items:
                    fields = item.get("fields", {})
                    url_obj = fields.get(url_field_name)

                    # 飞书URL字段是对象格式: {"link": "url", "text": "display text"}
                    if isinstance(url_obj, dict):
                        url_value = url_obj.get("link")
                        if url_value:
                            existing_urls.add(url_value)
                    # 兼容旧数据可能是字符串格式
                    elif isinstance(url_obj, str):
                        existing_urls.add(url_obj)

                # 检查是否还有下一页
                has_more = data.get("data", {}).get("has_more", False)
                if not has_more:
                    break

                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    break

        logger.info("飞书已存在URL数量: %d", len(existing_urls))
        return existing_urls
