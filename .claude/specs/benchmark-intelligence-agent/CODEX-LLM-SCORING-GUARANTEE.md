# CODEX 开发指令：LLM 评分 100% 成功保障

**开发阶段**: LLM Scoring Guarantee Enhancement
**开发时间**: 2025-11-16
**开发者**: Codex
**验收者**: Claude Code

---

## 一、任务目标

保证每个候选都成功调用 LLM 评分，避免因为网络抖动、API 限流、JSON 解析失败等原因导致评分缺失。

**当前问题**:
- LLM 评分成功率 ~70-80%
- 批量评分时，个别候选失败可能影响整批
- JSON 解析失败直接降级到规则兜底（5/10 分）
- OpenAI API 限流时大量失败

**目标**:
- LLM 评分成功率 ≥95%
- 失败时智能重试（指数退避 + 严格 JSON 模式）
- 并发控制，避免 API 限流
- 失败隔离，保证其他评分不受影响

---

## 二、失败原因分析

### 1. API 限流（Rate Limit）

**现象**:
```
openai.RateLimitError: Rate limit reached for gpt-4o
```

**原因**:
- OpenAI API 限制: `gpt-4o` **10,000 TPM**
- 当前并发度: `SCORE_CONCURRENCY = 10`
- 50 个候选同时评分 → 触发限流

**解决**:
- 降低并发度: `10 → 5`
- 增加重试间隔

---

### 2. 网络超时（Timeout）

**现象**:
```
asyncio.TimeoutError: LLM调用超时
```

**原因**:
- 当前超时: `30s`
- OpenAI API 偶尔响应慢

**解决**:
- 增加超时: `30s → 60s`
- 重试时动态增加超时

---

### 3. JSON 解析失败（Parse Error）

**现象**:
```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**:
- LLM 输出包含代码块、额外文字
- 例如：`\`\`\`json\n{...}\n\`\`\``

**解决**:
- 增强 JSON 清理逻辑
- 失败时使用严格 JSON 模式重试

---

### 4. 字段校验失败（Validation Error）

**现象**:
```
ValidationError: activity_score: ensure this value is less than or equal to 10.0
```

**原因**:
- LLM 返回越界值（如 `11.0`）
- 必填字段缺失

**解决**:
- 自动修正越界值
- 补充缺失字段

---

## 三、实施方案

### Phase 1: 增强重试机制

#### 任务 1.1: 修改配置参数

**文件**: `src/common/constants.py`

```python
# 行 298-302（原值）
LLM_TIMEOUT_SECONDS: Final[int] = 30
LLM_CACHE_TTL_SECONDS: Final[int] = 7 * 24 * 3600
LLM_MAX_RETRIES: Final[int] = 3
LLM_COMPLETION_MAX_TOKENS: Final[int] = 2000
SCORE_CONCURRENCY: Final[int] = 10

# 修改为：
LLM_TIMEOUT_SECONDS: Final[int] = 60  # 增加超时时间
LLM_CACHE_TTL_SECONDS: Final[int] = 7 * 24 * 3600
LLM_MAX_RETRIES: Final[int] = 5  # 增加重试次数
LLM_COMPLETION_MAX_TOKENS: Final[int] = 2000
SCORE_CONCURRENCY: Final[int] = 5  # 降低并发度
```

---

#### 任务 1.2: 增强 `_call_llm` 方法

**文件**: `src/scorer/llm_scorer.py`

**修改点 1**: 添加 `attempt` 参数，支持动态超时

```python
# 行 165-192（原代码）
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

# 修改为：
@retry(
    # 只重试可恢复的错误
    retry=retry_if_exception_type((
        asyncio.TimeoutError,
        httpx.TimeoutException,
    )),
    stop=stop_after_attempt(constants.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _call_llm(
    self,
    candidate: RawCandidate,
    attempt: int = 1,
) -> BenchmarkExtraction:
    """调用 LLM 评分（带智能重试）

    Args:
        candidate: 候选项
        attempt: 当前重试次数（用于动态调整超时）

    Returns:
        评分结果

    Raises:
        RuntimeError: OpenAI 未配置
        json.JSONDecodeError: JSON 解析失败（会触发严格 JSON 重试）
        ValidationError: 字段校验失败（会尝试自动修正）
    """
    if not self.client:
        raise RuntimeError("未配置OpenAI接口,无法调用LLM")

    # 动态超时：首次 60s，第 2 次 90s，第 3 次 120s
    timeout = constants.LLM_TIMEOUT_SECONDS + (attempt - 1) * 30

    prompt = self._build_prompt(candidate)

    try:
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
            timeout=timeout,
        )

        content = response.choices[0].message.content or ""
        logger.debug("LLM原始响应(前500字符): %s", content[:500])

        extraction = self._parse_extraction(content)
        return extraction

    except json.JSONDecodeError as exc:
        # JSON 解析失败 → 使用严格 JSON 模式重试
        logger.warning(
            "LLM 返回非法 JSON (尝试 %d/%d): %s",
            attempt,
            constants.LLM_MAX_RETRIES,
            exc,
        )

        if attempt < constants.LLM_MAX_RETRIES:
            # 重新调用，强调 JSON 格式
            logger.info("使用严格 JSON 模式重试...")
            return await self._call_llm_strict_json(candidate, attempt + 1)
        else:
            # 最后一次也失败了，抛出异常
            raise

    except ValidationError as exc:
        # 字段校验失败 → 尝试自动修正
        logger.warning("LLM 返回字段校验失败: %s，尝试自动修正...", exc)
        return self._fix_validation_error(content, exc)
```

**关键修改**:
1. 添加 `attempt` 参数
2. 动态超时: `timeout = 60 + (attempt-1)*30`
3. 捕获 `json.JSONDecodeError` → 调用 `_call_llm_strict_json`
4. 捕获 `ValidationError` → 调用 `_fix_validation_error`

---

#### 任务 1.3: 新增 `_call_llm_strict_json` 方法

在 `LLMScorer` 类中添加新方法（插入到 `_call_llm` 之后）：

```python
async def _call_llm_strict_json(
    self,
    candidate: RawCandidate,
    attempt: int,
) -> BenchmarkExtraction:
    """调用 LLM（严格 JSON 模式）

    当普通模式返回非法 JSON 时，使用此方法重试。
    强调：不要代码块、不要额外文字、只返回纯 JSON。

    Args:
        candidate: 候选项
        attempt: 当前重试次数

    Returns:
        评分结果
    """
    if not self.client:
        raise RuntimeError("未配置OpenAI接口")

    timeout = constants.LLM_TIMEOUT_SECONDS + (attempt - 1) * 30

    # 强调 JSON 格式的 System Prompt
    system_prompt = """你是MGX BenchScope的Benchmark评估专家。

【关键要求】
1. 只能返回纯JSON，不能有任何其他文字
2. 不要用代码块包裹（不要 ```json ```）
3. 所有字段必须存在，不能缺失
4. 分数必须在 0-10 之间

如果返回格式错误，将导致评分失败！"""

    prompt = self._build_prompt(candidate)
    prompt += "\n\n【再次提醒】只返回纯JSON，不要任何解释或代码块！"

    response = await asyncio.wait_for(
        self.client.chat.completions.create(
            model=self.settings.openai.model or constants.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,  # 降低随机性
            max_tokens=constants.LLM_COMPLETION_MAX_TOKENS,
        ),
        timeout=timeout,
    )

    content = response.choices[0].message.content or ""
    logger.debug("严格JSON模式响应: %s", content[:500])

    return self._parse_extraction(content)
```

---

#### 任务 1.4: 新增 `_fix_validation_error` 方法

在 `LLMScorer` 类中添加新方法（插入到 `_call_llm_strict_json` 之后）：

```python
def _fix_validation_error(
    self,
    content: str,
    validation_error: ValidationError,
) -> BenchmarkExtraction:
    """自动修正 LLM 返回的字段错误

    修正策略:
    1. 越界分数 → 裁剪到 [0, 10]
    2. 缺失必填字段 → 补默认值

    Args:
        content: LLM 原始响应
        validation_error: Pydantic 校验错误

    Returns:
        修正后的评分结果

    Raises:
        ValidationError: 修正失败
    """
    try:
        payload = json.loads(self._strip_code_fence(content))

        # 修正越界分数（裁剪到 [0, 10]）
        score_fields = [
            "activity_score",
            "reproducibility_score",
            "license_score",
            "novelty_score",
            "relevance_score",
        ]

        for field in score_fields:
            if field in payload:
                value = payload[field]
                if isinstance(value, (int, float)):
                    original = value
                    payload[field] = max(0.0, min(10.0, float(value)))
                    if original != payload[field]:
                        logger.info(
                            "修正越界分数: %s %.1f → %.1f",
                            field,
                            original,
                            payload[field],
                        )

        # 补充缺失的必填字段
        if "score_reasoning" not in payload or not payload["score_reasoning"]:
            payload["score_reasoning"] = "LLM 未提供评分依据（已自动修正）"
            logger.info("补充缺失字段: score_reasoning")

        # 确保分数字段都存在
        for field in score_fields:
            if field not in payload:
                payload[field] = 5.0
                logger.warning("补充缺失分数字段: %s = 5.0", field)

        # 重新校验
        extraction = BenchmarkExtraction.parse_obj(payload)
        logger.info("字段自动修正成功")
        return extraction

    except Exception as exc:
        logger.error("字段自动修正失败: %s", exc, exc_info=True)
        raise validation_error  # 修正失败，抛出原始错误
```

---

### Phase 2: 并发控制

#### 任务 2.1: 添加信号量

**文件**: `src/scorer/llm_scorer.py`

**修改点**: 在 `__init__` 方法中添加信号量

```python
# 行 101-108（原代码）
def __init__(self) -> None:
    self.settings = get_settings()
    api_key = self.settings.openai.api_key
    base_url = self.settings.openai.base_url
    self.client: Optional[AsyncOpenAI] = None
    if api_key:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    self.redis_client: Optional[redis.Redis] = None

# 修改为：
def __init__(self) -> None:
    self.settings = get_settings()
    api_key = self.settings.openai.api_key
    base_url = self.settings.openai.base_url
    self.client: Optional[AsyncOpenAI] = None
    if api_key:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    self.redis_client: Optional[redis.Redis] = None

    # 并发控制：限制同时评分的数量
    self.semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)
```

---

#### 任务 2.2: 在 `score` 方法中使用信号量

**文件**: `src/scorer/llm_scorer.py`

**修改点**: 修改 `score` 方法

```python
# 行 245-260（原代码）
async def score(self, candidate: RawCandidate) -> ScoredCandidate:
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

# 修改为：
async def score(self, candidate: RawCandidate) -> ScoredCandidate:
    """评分单个候选（带并发控制）

    使用信号量限制并发度，避免触发 OpenAI API 限流。

    Args:
        candidate: 候选项

    Returns:
        评分后的候选项

    Raises:
        Exception: LLM 评分失败（会被 score_batch 捕获）
    """
    # 获取信号量（限制并发）
    async with self.semaphore:
        extraction = await self._get_cached_score(candidate)

        if not extraction:
            if not self.client:
                logger.warning("OpenAI未配置,使用规则兜底评分")
                extraction = self._fallback_extraction(candidate)
            else:
                # 不在这里捕获异常，交给 score_batch 统一处理
                extraction = await self._call_llm(candidate)
                await self._set_cached_score(candidate, extraction)

        return self._to_scored_candidate(candidate, extraction)
```

**关键修改**:
1. 添加 `async with self.semaphore`
2. 移除 `try-except`（让异常向上传播到 `score_batch`）

---

### Phase 3: 失败隔离

#### 任务 3.1: 增强 `score_batch` 方法

**文件**: `src/scorer/llm_scorer.py`

```python
# 行 339-354（原代码）
async def score_batch(
    self, candidates: List[RawCandidate]
) -> List[ScoredCandidate]:
    if not candidates:
        return []

    tasks = [self.score(candidate) for candidate in candidates]
    results = await asyncio.gather(*tasks)
    logger.info("批量评分完成: %d条", len(results))
    return list(results)

# 修改为：
async def score_batch(
    self, candidates: List[RawCandidate]
) -> List[ScoredCandidate]:
    """批量评分，保证每个候选都有评分（优先 LLM，失败后规则兜底）

    使用 return_exceptions=True 确保单个候选失败不影响其他候选。

    Args:
        candidates: 候选项列表

    Returns:
        评分后的候选项列表（长度与输入相同）
    """
    if not candidates:
        return []

    logger.info("开始批量评分: %d 个候选", len(candidates))

    tasks = [self.score(candidate) for candidate in candidates]

    # return_exceptions=True: 异常不会停止其他任务
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果
    scored = []
    llm_success = 0
    fallback_count = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # 这个候选 LLM 评分失败，使用规则兜底
            logger.error(
                "候选 #%d (%s) LLM 评分失败: %s，使用规则兜底",
                i + 1,
                candidates[i].title[:50],
                str(result),
            )

            # 强制使用规则兜底
            extraction = self._fallback_extraction(candidates[i])
            scored_candidate = self._to_scored_candidate(candidates[i], extraction)
            scored.append(scored_candidate)
            fallback_count += 1
        else:
            scored.append(result)
            llm_success += 1

    # 统计日志
    logger.info(
        "批量评分完成: LLM 成功 %d 条 (%.1f%%)，规则兜底 %d 条 (%.1f%%)",
        llm_success,
        100 * llm_success / len(scored) if scored else 0,
        fallback_count,
        100 * fallback_count / len(scored) if scored else 0,
    )

    # 如果兜底比例过高，发出警告
    if fallback_count > llm_success:
        logger.warning(
            "⚠️  LLM 评分成功率低于 50%%，请检查："
            "\n  1. OpenAI API 密钥是否有效"
            "\n  2. 是否触发限流（降低 SCORE_CONCURRENCY）"
            "\n  3. 网络是否稳定"
        )

    return scored
```

---

### Phase 4: 导入依赖

#### 任务 4.1: 添加 import

**文件**: `src/scorer/llm_scorer.py`

在文件开头添加缺失的 import：

```python
# 行 1-19（原 import）
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, List, Optional

import redis.asyncio as redis
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)

# 修改为：
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, List, Optional

import httpx  # 新增
import redis.asyncio as redis
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,  # 新增
    before_sleep_log,  # 新增
)

from src.common import constants
from src.config import get_settings
from src.models import RawCandidate, ScoredCandidate

logger = logging.getLogger(__name__)
```

---

## 四、验收标准

### 4.1 功能测试

**测试步骤**:

```bash
# 1. 运行完整流程
.venv/bin/python -m src.main

# 2. 检查日志中的评分成功率
tail -100 logs/$(ls -t logs/ | head -n1) | grep "批量评分完成"
```

**期望结果**:

```
批量评分完成: LLM 成功 48 条 (96.0%)，规则兜底 2 条 (4.0%)
```

**验收标准**:
- [ ] LLM 评分成功率 ≥90%
- [ ] 日志中有"使用严格 JSON 模式重试"（证明重试机制生效）
- [ ] 日志中有"修正越界分数"或"补充缺失字段"（证明自动修正生效）
- [ ] 无"整批失败"现象
- [ ] 飞书表格正常写入

---

### 4.2 压力测试

**测试步骤**:

```bash
# 模拟大量候选（修改 config/sources.yaml）
arxiv:
  max_results: 100  # 从 50 增加到 100

# 运行采集
.venv/bin/python -m src.main
```

**验收标准**:
- [ ] LLM 评分成功率 ≥90%（即使 100 个候选）
- [ ] 无 API 限流错误
- [ ] 评分时间 < 10 分钟

---

### 4.3 异常测试

**测试 1**: 模拟网络不稳定

```bash
# 在运行过程中手动断网几秒钟
# 观察是否有重试日志
```

**期望**:
- 日志中出现"LLM 返回非法 JSON (尝试 X/5)"
- 最终仍然完成评分

---

**测试 2**: 模拟 OpenAI API Key 错误

```bash
# 修改 .env.local
OPENAI_API_KEY=invalid_key

# 运行采集
.venv/bin/python -m src.main
```

**期望**:
- 所有候选使用规则兜底
- 日志中有"OpenAI未配置,使用规则兜底评分"

---

## 五、代码质量要求

### 5.1 PEP8 规范

- 使用 `black` 格式化
- 使用 `ruff` 检查
- 函数添加 Docstring
- 关键逻辑写中文注释

### 5.2 日志规范

```python
logger.info("开始批量评分: %d 个候选", len(candidates))
logger.warning("LLM 返回非法 JSON (尝试 %d/%d): %s", attempt, max_retries, exc)
logger.error("候选 #%d (%s) LLM 评分失败: %s", i, title, exc)
```

### 5.3 错误处理

- 所有网络请求必须有超时
- 所有异常必须记录日志
- 避免吞掉异常（除非明确需要兜底）

---

## 六、交付清单

- [ ] 修改后的 `src/common/constants.py`
- [ ] 修改后的 `src/scorer/llm_scorer.py`
- [ ] 运行日志（证明 LLM 评分成功率 ≥90%）
- [ ] 压力测试报告（100 个候选）
- [ ] 异常测试报告（网络不稳定、API Key 错误）

---

## 七、常见问题

### Q1: 重试次数太多，评分变慢怎么办？

**A**: 调整配置

```python
LLM_MAX_RETRIES: Final[int] = 3  # 从 5 降到 3
```

---

### Q2: 并发度太低，评分太慢怎么办？

**A**: 根据实际限流情况调整

```python
SCORE_CONCURRENCY: Final[int] = 8  # 从 5 增加到 8
```

---

### Q3: 严格 JSON 模式也失败怎么办？

**A**: 检查 LLM 输出，可能需要调整 Prompt

```python
# 在 _call_llm_strict_json 中加强 Prompt
prompt += "\n\n【严格要求】必须返回合法 JSON，格式：{\"activity_score\": 7.5, ...}"
```

---

## 八、验收流程

1. **Codex 提交代码** → 在开发文档中说明修改点
2. **Claude Code 审核代码** → 检查代码质量、错误处理、日志
3. **Claude Code 执行测试** → 运行功能测试、压力测试、异常测试
4. **Claude Code 编写测试报告** → `docs/llm-scoring-test-report.md`
5. **验收通过/打回修改**

---

**开始开发前，请确认已理解以上所有要求。**
