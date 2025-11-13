"""LLM评分模块"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

import redis.asyncio as redis
from openai import AsyncOpenAI
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from src.common import constants
from src.config import Settings, get_settings
from src.models import BenchmarkScore, RawCandidate
from src.scorer.rule_scorer import RuleScorer

logger = logging.getLogger(__name__)


class LLMScorer:
    """调用LLM获取5维度评分,失败时回落到规则评分"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.rule_scorer = RuleScorer()
        self.model = self.settings.openai.model
        self.timeout = constants.LLM_TIMEOUT_SECONDS
        self.cache_ttl = constants.LLM_CACHE_TTL_SECONDS
        self.client: Optional[AsyncOpenAI] = None
        if self.settings.openai.api_key:
            client_kwargs = {"api_key": self.settings.openai.api_key}
            if self.settings.openai.base_url:
                client_kwargs["base_url"] = self.settings.openai.base_url
            self.client = AsyncOpenAI(**client_kwargs)
        self.cache = redis.from_url(
            self.settings.redis.url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def score(self, candidate: RawCandidate) -> BenchmarkScore:
        """评分入口"""

        cache_key = self._cache_key(candidate)
        cached = await self._read_cache(cache_key)
        if cached:
            return BenchmarkScore(**cached)

        if not self.client:
            logger.warning("未配置OpenAI,使用规则评分")
            return self.rule_scorer.score(candidate)

        prompt = self._build_prompt(candidate)

        try:
            score_dict = await self._call_with_retry(prompt)
            score = BenchmarkScore(**score_dict)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM评分失败, fallback规则评分: %s", exc)
            score = self.rule_scorer.score(candidate)
            score_dict = asdict(score)

        await self._write_cache(cache_key, score_dict)
        return score

    async def _call_with_retry(self, prompt: str) -> Dict[str, int]:
        """带重试地调用LLM"""

        if not self.client:
            raise RuntimeError("LLM客户端未初始化")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        ):
            with attempt:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "你是AI Benchmark评估专家,负责对候选进行量化评分。",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,
                        max_tokens=200,
                    ),
                    timeout=self.timeout,
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM未返回内容")
                return self._parse_scores(content)

        raise RetryError("LLM多次调用失败")

    def _build_prompt(self, candidate: RawCandidate) -> str:
        """构建评分提示词"""

        return (
            "请为以下Benchmark候选在创新性/技术深度/影响力/数据质量/可复现性5个维度打分(0-10分)。\n"
            f"标题: {candidate.title}\n"
            f"来源: {candidate.source}\n"
            f"摘要: {candidate.abstract or 'N/A'}\n"
            f"GitHub Stars: {candidate.github_stars or 'N/A'}\n"
            f"发布时间: {candidate.publish_date or 'N/A'}\n"
            "输出JSON,示例:{\"innovation\":8,...}"
        )

    def _parse_scores(self, content: str) -> Dict[str, int]:
        """解析LLM返回的JSON字符串"""

        try:
            data: Dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("LLM返回非JSON: %s", content)
            raise ValueError("LLM输出非法") from exc

        required = [
            "innovation",
            "technical_depth",
            "impact",
            "data_quality",
            "reproducibility",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"LLM缺少字段: {missing}")

        return {key: int(data[key]) for key in required}

    def _cache_key(self, candidate: RawCandidate) -> str:
        """基于标题生成稳定缓存键"""

        digest = hashlib.md5(candidate.title.encode("utf-8"), usedforsecurity=False).hexdigest()  # noqa: S324
        return f"score:{digest}"

    async def _read_cache(self, key: str) -> Optional[Dict[str, int]]:
        """读取Redis缓存,异常时静默忽略"""

        try:
            value = await self.cache.get(key)
            if value:
                return json.loads(value)
        except Exception as exc:  # noqa: BLE001
            logger.debug("读取缓存失败: %s", exc)
        return None

    async def _write_cache(self, key: str, payload: Dict[str, int]) -> None:
        """写入缓存,容错即可"""

        try:
            await self.cache.setex(key, self.cache_ttl, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            logger.debug("写入缓存失败: %s", exc)
