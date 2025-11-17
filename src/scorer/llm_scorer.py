"""LLM评分引擎"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Awaitable, List, Optional, cast

import redis.asyncio as redis
from redis.asyncio import Redis as AsyncRedis
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate, ScoredCandidate
from src.scorer.backend_scorer import BackendBenchmarkScorer

logger = logging.getLogger(__name__)


SCORING_PROMPT_TEMPLATE = """你是BenchScope的Benchmark评估专家,需要根据以下候选信息给出5维量化评分，并抽取结构化字段。

【MGX领域优先级】
- P0: Coding / WebDev / Backend / GUI  —— 核心场景
- P1: ToolUse / Collaboration / LLM/AgentOps —— 高优先级辅助场景
- P2: Reasoning / DeepResearch —— 中优先级支撑
- 其他纯NLP/视觉/语音若无明确代码或Agent关联，视为 Other (relevance_score ≤ 3)

【评分维度（必须全部返回，0-10分）】
1. 活跃度 activity_score —— GitHub stars、近期提交、社区讨论；可按提示阈值加减分。
2. 可复现性 reproducibility_score —— 数据/代码/评估脚本/指标/基准结果的公开程度。
3. 许可合规 license_score —— MIT/Apache=10，GPL≈7，CC≈4，未知/专有≤2。
4. 新颖性 novelty_score —— 任务或指标是否创新，是否2024+发布，是否补位 MGX 场景空白。
5. MGX适配度 relevance_score —— 明确候选归属的任务领域(P0/P1/P2/Other)，并结合评测指标/场景说明原因。

【结构化字段要求】
- task_domain 只能从 {task_domain_options} 中选择（多个用逗号，按优先级降序）。
- metrics / baselines 最多各{max_metrics}个，用大写或标准缩写表示（如"Pass@1"、"BLEU-4"、"GPT-4"）。
- institution 填写最主要机构名称；authors 最多5人，形如["Alice Zhang", "Bob Li"]。
- dataset_size 如能解析数字请给整数，同时提供 dataset_size_description 原始描述。
- score_reasoning 必须 100-200 字，说明 Benchmark 判断、各维度打分依据、是否推荐纳入 MGX（总分≥6.5且 relevance≥7 推荐）。

【输出 JSON（必须严格遵循，不能新增/缺失字段，命名全部为小写下划线）】
{{
  "activity_score": float,
  "reproducibility_score": float,
  "license_score": float,
  "novelty_score": float,
  "relevance_score": float,
  "score_reasoning": "100-200字中文说明",
  "task_domain": "Coding" | "Coding,ToolUse" | ... | "Other",
  "metrics": ["Pass@1", "BLEU-4"],
  "baselines": ["GPT-4", "Claude-3.5-Sonnet"],
  "institution": "Stanford University",
  "authors": ["Alice Zhang", "Bob Li"],
  "dataset_size": 1000,
  "dataset_size_description": "1000 coding problems"
}}
若某字段无可靠信息，请返回 null（不要删除键）。切勿输出 is_benchmark 等未定义字段，切勿在 JSON 前后附加文字。

【候选基础信息】
- 标题: {title}
- 来源: {source}
- 摘要/README(截断): {abstract}
- GitHub Stars: {github_stars}
- 许可证: {license_type}
- 任务类型: {task_type}

【PDF深度内容 (Phase 8新增)】
> Evaluation部分摘要 (2000字):
{evaluation_summary}

> Dataset部分摘要 (1000字):
{dataset_summary}

> Baselines部分摘要 (1000字):
{baselines_summary}

【原始提取数据 (规则+GitHub)】
- 原始指标: {raw_metrics}
- 原始Baseline: {raw_baselines}
- 原始作者: {raw_authors}
- 原始机构: {raw_institutions}
- 原始数据规模: {raw_dataset_size}
- URL: {url}
"""


class BenchmarkExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    activity_score: float = Field(..., ge=0.0, le=10.0)
    reproducibility_score: float = Field(..., ge=0.0, le=10.0)
    license_score: float = Field(..., ge=0.0, le=10.0)
    novelty_score: float = Field(..., ge=0.0, le=10.0)
    relevance_score: float = Field(..., ge=0.0, le=10.0)
    score_reasoning: str = Field(..., min_length=10)
    task_domain: Optional[str] = None
    metrics: Optional[List[str]] = None
    baselines: Optional[List[str]] = None
    institution: Optional[str] = None
    authors: Optional[List[str]] = None
    dataset_size: Optional[int] = None
    dataset_size_description: Optional[str] = None



class LLMScorer:
    """使用LLM完成Phase 2评分的引擎"""

    def __init__(self) -> None:
        self.settings = get_settings()
        api_key = self.settings.openai.api_key
        base_url = self.settings.openai.base_url
        self.client: Optional[AsyncOpenAI] = None
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.redis_client: Optional[AsyncRedis] = None
        self.backend_scorer = BackendBenchmarkScorer()

    async def __aenter__(self) -> "LLMScorer":
        try:
            self.redis_client = redis.from_url(
                self.settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
            )
            ping_future = cast(Awaitable[bool], self.redis_client.ping())
            await ping_future
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis连接失败,将不使用缓存: %s", exc)
            self.redis_client = None
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None

    def _cache_key(self, candidate: RawCandidate) -> str:
        key_str = f"{candidate.title}:{candidate.url}"
        digest = hashlib.md5(
            key_str.encode(), usedforsecurity=False
        ).hexdigest()  # noqa: S324
        return f"{constants.REDIS_KEY_PREFIX}score:{digest}"

    async def _get_cached_score(
        self, candidate: RawCandidate
    ) -> Optional[BenchmarkExtraction]:
        if not self.redis_client:
            return None
        try:
            cached = await self.redis_client.get(self._cache_key(candidate))
            if cached:
                logger.debug("评分缓存命中: %s", candidate.title[:50])
                return BenchmarkExtraction.parse_raw(cached)
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取Redis失败: %s", exc)
        return None

    async def _set_cached_score(
        self, candidate: RawCandidate, payload: BenchmarkExtraction
    ) -> None:
        if not self.redis_client:
            return
        try:
            await self.redis_client.setex(
                self._cache_key(candidate),
                constants.REDIS_TTL_DAYS * 86400,
                payload.json(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("写入Redis失败: %s", exc)

    @retry(
        stop=stop_after_attempt(constants.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_llm(self, candidate: RawCandidate) -> BenchmarkExtraction:
        if not self.client:
            raise RuntimeError("未配置OpenAI接口,无法调用LLM")

        prompt = self._build_prompt(candidate)
        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.settings.openai.model or constants.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是MGX BenchScope的Benchmark评估专家,只能返回严格JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
            ),
            timeout=constants.LLM_TIMEOUT_SECONDS,
        )

        content = response.choices[0].message.content or ""
        logger.debug("LLM原始响应(前500字符): %s", content[:500])
        extraction = self._parse_extraction(content)
        return extraction

    def _build_prompt(self, candidate: RawCandidate) -> str:
        """构建 LLM 评分 Prompt（Phase 8 增强版）。"""

        abstract = (candidate.abstract or "无").strip()
        if len(abstract) > 1600:
            abstract = abstract[:1600] + "..."

        # 提取 PDF 增强内容（由 PDFEnhancer 写入 raw_metadata）
        raw_metadata = candidate.raw_metadata or {}
        evaluation_summary = raw_metadata.get("evaluation_summary", "")
        dataset_summary = raw_metadata.get("dataset_summary", "")
        baselines_summary = raw_metadata.get("baselines_summary", "")

        # 如果对应字段为空，提供兜底文案，方便 LLM 理解缺失原因
        if not evaluation_summary:
            evaluation_summary = "未提供（论文无Evaluation章节或PDF解析失败）"
        if not dataset_summary:
            dataset_summary = "未提供（论文无Dataset章节或PDF解析失败）"
        if not baselines_summary:
            baselines_summary = "未提供（论文无Baselines章节或PDF解析失败）"

        raw_metrics = ", ".join(candidate.raw_metrics or []) if candidate.raw_metrics else "未提取"
        raw_baselines = ", ".join(candidate.raw_baselines or []) if candidate.raw_baselines else "未提取"
        raw_authors = candidate.raw_authors or (", ".join(candidate.authors or []) if candidate.authors else "未提取")
        raw_institutions = candidate.raw_institutions or "未提取"
        raw_dataset = candidate.raw_dataset_size or "未提取"

        return SCORING_PROMPT_TEMPLATE.format(
            task_domain_options=", ".join(constants.TASK_DOMAIN_OPTIONS),
            max_metrics=constants.MAX_EXTRACTED_METRICS,
            title=candidate.title,
            source=candidate.source,
            abstract=abstract,
            github_stars=candidate.github_stars or "未提供",
            license_type=candidate.license_type or "未知",
            task_type=candidate.task_type or "未识别",
            evaluation_summary=evaluation_summary,
            dataset_summary=dataset_summary,
            baselines_summary=baselines_summary,
            raw_metrics=raw_metrics,
            raw_baselines=raw_baselines,
            raw_authors=raw_authors,
            raw_institutions=raw_institutions,
            raw_dataset_size=raw_dataset,
            url=candidate.url,
        )

    def _parse_extraction(self, content: str) -> BenchmarkExtraction:
        json_str = self._strip_code_fence(content)
        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("LLM响应解析失败(JSON): %s", exc)
            raise
        try:
            return BenchmarkExtraction.parse_obj(payload)
        except ValidationError as exc:
            logger.error("LLM响应字段校验失败: %s", exc)
            raise

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        text = content.strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.split("\n")
            lines = lines[1:-1]
            return "\n".join(lines).strip()
        if text.startswith("```"):
            return text.split("\n", 1)[-1].strip()
        return text

    async def score(self, candidate: RawCandidate) -> ScoredCandidate:
        if self._is_backend_benchmark(candidate):
            logger.info("使用后端专项评分: %s", candidate.title)
            return self.backend_scorer.score(candidate)

        extraction = await self._get_cached_score(candidate)
        if not extraction:
            if not self.client:
                logger.warning("OpenAI未配置,使用规则兜底评分")
                extraction = self._fallback_extraction(candidate)
            else:
                try:
                    extraction = await self._call_llm(candidate)
                except Exception as exc:  # noqa: BLE001
                    logger.error("LLM评分失败,使用兜底: %s", exc)
                    extraction = self._fallback_extraction(candidate)
                else:
                    await self._set_cached_score(candidate, extraction)

        return self._to_scored_candidate(candidate, extraction)

    def _to_scored_candidate(
        self, candidate: RawCandidate, extraction: BenchmarkExtraction
    ) -> ScoredCandidate:
        authors = extraction.authors or candidate.authors
        metrics = extraction.metrics or candidate.evaluation_metrics
        institution = extraction.institution or candidate.raw_institutions
        dataset_size_desc = (
            extraction.dataset_size_description or candidate.raw_dataset_size
        )

        return ScoredCandidate(
            title=candidate.title,
            url=candidate.url,
            source=candidate.source,
            abstract=candidate.abstract,
            authors=authors,
            publish_date=candidate.publish_date,
            github_stars=candidate.github_stars,
            github_url=candidate.github_url,
            dataset_url=candidate.dataset_url,
            raw_metadata=candidate.raw_metadata,
            raw_metrics=candidate.raw_metrics,
            raw_baselines=candidate.raw_baselines,
            raw_authors=candidate.raw_authors,
            raw_institutions=candidate.raw_institutions,
            raw_dataset_size=candidate.raw_dataset_size,
            paper_url=candidate.paper_url,
            task_type=candidate.task_type,
            license_type=candidate.license_type,
            evaluation_metrics=candidate.evaluation_metrics,
            reproduction_script_url=candidate.reproduction_script_url,
            activity_score=extraction.activity_score,
            reproducibility_score=extraction.reproducibility_score,
            license_score=extraction.license_score,
            novelty_score=extraction.novelty_score,
            relevance_score=extraction.relevance_score,
            score_reasoning=extraction.score_reasoning,
            task_domain=extraction.task_domain or constants.DEFAULT_TASK_DOMAIN,
            metrics=metrics,
            baselines=extraction.baselines,
            institution=institution,
            dataset_size=extraction.dataset_size,
            dataset_size_description=dataset_size_desc,
        )

    def _fallback_extraction(self, candidate: RawCandidate) -> BenchmarkExtraction:
        activity = 5.0
        stars = candidate.github_stars or 0
        if stars >= 1000:
            activity = 9.0
        elif stars >= 500:
            activity = 7.5
        elif stars >= 100:
            activity = 6.0

        reproducibility = 3.0
        if candidate.github_url:
            reproducibility += 3.0
        if candidate.dataset_url:
            reproducibility += 3.0

        return BenchmarkExtraction(
            activity_score=activity,
            reproducibility_score=min(10.0, reproducibility),
            license_score=5.0,
            novelty_score=5.0,
            relevance_score=5.0,
            score_reasoning="规则兜底评分(LLM不可用)",
            task_domain=None,
            metrics=candidate.evaluation_metrics,
            baselines=None,
            institution=candidate.raw_institutions,
            authors=candidate.authors,
            dataset_size=None,
            dataset_size_description=candidate.raw_dataset_size,
        )

    async def score_batch(
        self, candidates: List[RawCandidate]
    ) -> List[ScoredCandidate]:
        if not candidates:
            return []

        # 使用Semaphore控制并发数，避免触发OpenAI速率限制
        semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)

        async def score_with_semaphore(candidate: RawCandidate) -> ScoredCandidate:
            async with semaphore:
                return await self.score(candidate)

        tasks = [score_with_semaphore(candidate) for candidate in candidates]
        results = await asyncio.gather(*tasks)
        logger.info("批量评分完成: %d条 (并发限制: %d)", len(results), constants.SCORE_CONCURRENCY)
        return list(results)

    def _is_backend_benchmark(self, candidate: RawCandidate) -> bool:
        """基于来源与关键词识别后端Benchmark"""

        if candidate.source in {"techempower", "dbengines"}:
            return True

        signals = [
            "backend",
            "api",
            "database",
            "microservice",
            "rest",
            "graphql",
            "latency",
            "throughput",
            "qps",
            "rps",
            "scalability",
            "distributed",
            "server",
            "system design",
        ]

        text = (candidate.abstract or "") + " " + candidate.title
        text += " " + " ".join(candidate.raw_metadata.values())
        text_lower = text.lower()
        hits = sum(1 for signal in signals if signal in text_lower)
        return hits >= 2
