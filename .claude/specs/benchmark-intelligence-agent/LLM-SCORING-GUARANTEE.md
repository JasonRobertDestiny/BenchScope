# LLM 评分 100% 成功保障方案

**目标**: 保证每个候选都成功调用 LLM 评分，避免降级到规则兜底

**当前问题**: 虽然有重试机制，但仍可能因为并发限流、网络抖动、JSON 解析失败等原因导致 LLM 评分失败

---

## 一、失败原因分析

### 1. API 限流（Rate Limit）

**问题**:
- OpenAI API 限制: `gpt-4o` **10,000 TPM** (Tokens Per Minute)
- 当前并发度: `SCORE_CONCURRENCY = 10`
- 如果 50 个候选同时评分 → **可能触发限流**

**表现**:
```
openai.RateLimitError: Rate limit reached for gpt-4o
```

**解决**:
- 降低并发度: `10 → 5`
- 增加重试间隔: 指数退避 + Jitter（随机抖动）

---

### 2. 网络超时（Timeout）

**问题**:
- 当前超时: `30s`
- OpenAI API 偶尔响应慢（尤其是 `gpt-4o` 长输出）

**表现**:
```
asyncio.TimeoutError: LLM调用超时
```

**解决**:
- 增加超时: `30s → 60s`
- 重试时翻倍超时: 第1次 60s → 第2次 90s → 第3次 120s

---

### 3. JSON 解析失败（Parse Error）

**问题**:
- LLM 输出不符合 JSON 格式
- 包含代码块、额外文字

**表现**:
```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**解决**:
- 增强 JSON 清理逻辑
- 失败时重新调用 LLM（明确要求纯 JSON）

---

### 4. 字段校验失败（Validation Error）

**问题**:
- LLM 返回的字段不符合 Pydantic 模型
- 例如：`activity_score = 11.0` (超出 0-10 范围)

**表现**:
```
ValidationError: 1 validation error for BenchmarkExtraction
activity_score: ensure this value is less than or equal to 10.0
```

**解决**:
- 自动修正越界值: `11.0 → 10.0`
- 必填字段缺失时补默认值

---

## 二、增强方案

### 方案1: 智能重试（失败时调整策略）

#### 1.1 分层重试策略

```python
# src/scorer/llm_scorer.py

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

class LLMScorer:
    @retry(
        # 重试条件：只重试可恢复的错误
        retry=retry_if_exception_type((
            asyncio.TimeoutError,
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
        )),
        # 最多重试 5 次（从 3 次增加到 5 次）
        stop=stop_after_attempt(5),
        # 指数退避 + 随机抖动（避免同时重试）
        wait=wait_exponential(
            multiplier=2,  # 2s → 4s → 8s → 16s → 32s
            min=2,
            max=60,
        ),
        # 重试前记录日志
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _call_llm(
        self,
        candidate: RawCandidate,
        attempt: int = 1,  # 新增：当前重试次数
    ) -> BenchmarkExtraction:
        """调用 LLM 评分（带智能重试）"""

        if not self.client:
            raise RuntimeError("未配置OpenAI接口")

        # 根据重试次数调整超时（首次 60s，后续逐渐增加）
        timeout = constants.LLM_TIMEOUT_SECONDS * attempt

        prompt = self._build_prompt(candidate, attempt=attempt)

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
            # JSON 解析失败 → 明确提示 LLM
            logger.warning(
                "LLM 返回非法 JSON (尝试 %d/%d): %s",
                attempt,
                constants.LLM_MAX_RETRIES,
                exc,
            )

            if attempt < constants.LLM_MAX_RETRIES:
                # 重新调用，强调 JSON 格式
                return await self._call_llm_strict_json(candidate, attempt + 1)
            else:
                raise

        except ValidationError as exc:
            # 字段校验失败 → 尝试自动修正
            logger.warning("LLM 返回字段校验失败: %s", exc)
            return self._fix_validation_error(content, exc)
```

#### 1.2 严格 JSON 模式（重试时使用）

```python
async def _call_llm_strict_json(
    self,
    candidate: RawCandidate,
    attempt: int,
) -> BenchmarkExtraction:
    """调用 LLM（严格 JSON 模式）"""

    timeout = constants.LLM_TIMEOUT_SECONDS * attempt

    # 强调 JSON 格式的 Prompt
    system_prompt = """你是MGX BenchScope的Benchmark评估专家。

【关键要求】
1. 只能返回纯JSON，不能有任何其他文字
2. 不要用代码块包裹（不要 ```json ```）
3. 所有字段必须存在，不能缺失
4. 分数必须在 0-10 之间

如果返回格式错误，将导致评分失败！"""

    prompt = self._build_prompt(candidate, attempt=attempt)
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
    return self._parse_extraction(content)
```

---

### 方案2: 并发控制（避免限流）

#### 2.1 使用信号量限制并发

```python
# src/scorer/llm_scorer.py

import asyncio

class LLMScorer:
    def __init__(self):
        # 现有代码...
        self.semaphore = asyncio.Semaphore(constants.SCORE_CONCURRENCY)

    async def score(self, candidate: RawCandidate) -> ScoredCandidate:
        """评分单个候选（带并发控制）"""

        # 获取信号量（限制并发）
        async with self.semaphore:
            extraction = await self._get_cached_score(candidate)

            if not extraction:
                if not self.client:
                    logger.warning("OpenAI未配置,使用规则兜底评分")
                    extraction = self._fallback_extraction(candidate)
                else:
                    try:
                        extraction = await self._call_llm(candidate)
                    except Exception as exc:
                        logger.error("LLM评分失败: %s", exc, exc_info=True)
                        raise  # 抛出异常，由 score_batch 处理
                    else:
                        await self._set_cached_score(candidate, extraction)

            return self._to_scored_candidate(candidate, extraction)
```

#### 2.2 调整并发度

```python
# src/common/constants.py

SCORE_CONCURRENCY: Final[int] = 5  # 从 10 降到 5，避免限流
```

---

### 方案3: 失败隔离（保证不影响其他评分）

#### 3.1 批量评分增强版

```python
async def score_batch(
    self, candidates: List[RawCandidate]
) -> List[ScoredCandidate]:
    """批量评分，保证每个候选都有评分（优先使用 LLM，失败后兜底）"""

    if not candidates:
        return []

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
                result,
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
            "⚠️  LLM 评分成功率低于 50%%，请检查 OpenAI API 配置或限流情况！"
        )

    return scored
```

---

### 方案4: 字段自动修正

#### 4.1 越界值修正

```python
def _fix_validation_error(
    self,
    content: str,
    validation_error: ValidationError,
) -> BenchmarkExtraction:
    """自动修正 LLM 返回的字段错误"""

    try:
        payload = json.loads(self._strip_code_fence(content))

        # 修正越界分数
        for field in ["activity_score", "reproducibility_score", "license_score", "novelty_score", "relevance_score"]:
            if field in payload:
                value = payload[field]
                if isinstance(value, (int, float)):
                    payload[field] = max(0.0, min(10.0, float(value)))

        # 补充缺失的必填字段
        if "score_reasoning" not in payload or not payload["score_reasoning"]:
            payload["score_reasoning"] = "LLM 未提供评分依据（已自动修正）"

        # 重新校验
        return BenchmarkExtraction.parse_obj(payload)

    except Exception as exc:
        logger.error("字段自动修正失败: %s", exc)
        raise
```

---

## 三、配置调整

### 3.1 增加超时和重试次数

```python
# src/common/constants.py

LLM_TIMEOUT_SECONDS: Final[int] = 60  # 从 30s 增加到 60s
LLM_MAX_RETRIES: Final[int] = 5  # 从 3 次增加到 5 次
SCORE_CONCURRENCY: Final[int] = 5  # 从 10 降到 5（避免限流）
```

---

## 四、监控与告警

### 4.1 评分成功率监控

在日志中记录：

```python
logger.info(
    "批量评分完成: LLM 成功 %d 条 (%.1f%%)，规则兜底 %d 条 (%.1f%%)",
    llm_success,
    100 * llm_success / len(scored),
    fallback_count,
    100 * fallback_count / len(scored),
)
```

### 4.2 失败告警

当 LLM 评分成功率 < 50% 时：

```python
if fallback_count > llm_success:
    logger.warning(
        "⚠️  LLM 评分成功率低于 50%%，请检查："
        "\n1. OpenAI API 密钥是否有效"
        "\n2. 是否触发限流（降低 SCORE_CONCURRENCY）"
        "\n3. 网络是否稳定"
    )
```

---

## 五、预期效果

| 场景 | 现有机制 | 增强后 |
|------|----------|--------|
| LLM 正常 | ✅ 100% 成功 | ✅ 100% 成功 |
| 偶发超时 | ⚠️ 50% 失败 | ✅ 95% 成功（重试） |
| API 限流 | ❌ 90% 失败 | ✅ 80% 成功（降低并发 + 重试） |
| JSON 解析失败 | ❌ 100% 失败 | ✅ 90% 成功（严格 JSON 模式） |
| 字段校验失败 | ❌ 100% 失败 | ✅ 95% 成功（自动修正） |

**总体 LLM 评分成功率**:
- 现有: **~70-80%**
- 增强后: **≥95%**

---

## 六、实施步骤

### Step 1: 修改 `src/common/constants.py`

```python
LLM_TIMEOUT_SECONDS: Final[int] = 60  # 增加超时
LLM_MAX_RETRIES: Final[int] = 5  # 增加重试次数
SCORE_CONCURRENCY: Final[int] = 5  # 降低并发度
```

### Step 2: 增强 `src/scorer/llm_scorer.py`

1. 添加 `_call_llm_strict_json` 方法
2. 添加 `_fix_validation_error` 方法
3. 修改 `_call_llm` 支持动态超时
4. 修改 `score` 添加信号量
5. 修改 `score_batch` 支持失败隔离

### Step 3: 测试验收

```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志中的评分成功率
tail -100 logs/$(ls -t logs/ | head -n1) | grep "批量评分完成"

# 期望输出：
# 批量评分完成: LLM 成功 48 条 (96.0%)，规则兜底 2 条 (4.0%)
```

---

## 七、回退方案

如果增强后反而导致问题（例如超时过长影响性能），可以：

1. **回退超时**: `60s → 45s`
2. **回退重试次数**: `5 → 3`
3. **回退并发度**: `5 → 8`

---

**总结**: 通过智能重试、并发控制、失败隔离、字段自动修正，可以将 LLM 评分成功率从 ~70% 提升到 ≥95%，基本保证每个候选都成功调用 LLM 评分。
