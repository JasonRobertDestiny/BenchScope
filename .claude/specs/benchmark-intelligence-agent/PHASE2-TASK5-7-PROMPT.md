# Phase 2 Task 5-7 开发指令

## 当前状态

**已完成** (由Claude Code验收通过):
- ✅ Task 1: 规则预筛选引擎 (5条规则 + 7个单元测试)
- ✅ Task 2: LLM评分引擎 (async with + Redis缓存 + 兜底评分)
- ✅ Task 3-4: SQLite存储层改造 (序列化/反序列化Phase 2字段)

**测试结果**:
- ✅ 11/11单元测试通过
- ✅ 真实数据完整流程测试通过 (采集 → 预筛选 → LLM评分 → SQLite存储)
- ✅ LLM评分成功 (总分6.80/10, 优先级medium)

## 待实现 Task

### Task 5: 飞书存储 + 存储管理器 (预计40分钟)

**目标**: 实现飞书多维表格写入 + 主备存储管理器

#### 5.1 飞书多维表格存储 (`src/storage/feishu_storage.py`)

**必须实现的功能**:

1. **表格字段映射** (Phase 2 → 飞书字段):
```python
class FeishuStorage:
    """飞书多维表格存储"""

    FIELD_MAPPING = {
        "title": "标题",          # 文本
        "source": "来源",         # 单选 (arxiv/github/pwc/huggingface)
        "url": "URL",            # 超链接
        "abstract": "摘要",       # 多行文本
        "activity_score": "活跃度",          # 数字 (0-10)
        "reproducibility_score": "可复现性",  # 数字 (0-10)
        "license_score": "许可合规",         # 数字 (0-10)
        "novelty_score": "新颖性",          # 数字 (0-10)
        "relevance_score": "MGX适配度",     # 数字 (0-10)
        "total_score": "总分",              # 数字 (0-10)
        "priority": "优先级",               # 单选 (high/medium/low)
        "reasoning": "评分依据",            # 多行文本
        "status": "状态",                   # 单选 (pending/reviewing/approved/rejected)
    }
```

2. **批量写入** (飞书API限制: 20条/请求):
```python
async def save(self, candidates: List[ScoredCandidate]) -> None:
    """批量写入飞书多维表格

    API限制:
    - 最多20条/请求
    - 100请求/分钟
    - 需要0.6秒间隔避免限流
    """
    if not candidates:
        return

    # 分批处理 (每批20条)
    batch_size = constants.FEISHU_BATCH_SIZE  # 20
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        records = [self._to_feishu_record(c) for c in batch]

        try:
            await self._batch_create_records(records)
            logger.info(f"飞书写入成功: {len(batch)}条")
        except Exception as exc:
            logger.error(f"飞书写入失败: {exc}")
            raise  # 抛出异常让StorageManager降级

        # 避免限流
        if i + batch_size < len(candidates):
            await asyncio.sleep(constants.FEISHU_RATE_LIMIT_DELAY)
```

3. **记录格式转换**:
```python
def _to_feishu_record(self, candidate: ScoredCandidate) -> dict:
    """转换为飞书记录格式

    返回格式: {"fields": {"字段ID": {"type": "xxx", "value": ...}}}
    """
    return {
        "fields": {
            self.FIELD_MAPPING["title"]: candidate.title,
            self.FIELD_MAPPING["source"]: candidate.source,
            self.FIELD_MAPPING["url"]: candidate.url,
            self.FIELD_MAPPING["abstract"]: candidate.abstract or "",
            self.FIELD_MAPPING["activity_score"]: candidate.activity_score,
            self.FIELD_MAPPING["reproducibility_score"]: candidate.reproducibility_score,
            self.FIELD_MAPPING["license_score"]: candidate.license_score,
            self.FIELD_MAPPING["novelty_score"]: candidate.novelty_score,
            self.FIELD_MAPPING["relevance_score"]: candidate.relevance_score,
            self.FIELD_MAPPING["total_score"]: candidate.total_score,
            self.FIELD_MAPPING["priority"]: candidate.priority,
            self.FIELD_MAPPING["reasoning"]: candidate.reasoning,
            self.FIELD_MAPPING["status"]: "pending",  # 默认待审核
        }
    }
```

**关键依赖**:
```python
from lark_oapi.api.bitable.v1 import CreateAppTableRecordRequest, CreateAppTableRecordRequestBody
from src.config import get_settings
from src.models import ScoredCandidate
```

**错误处理**:
- API调用失败 → 抛出异常 (让StorageManager降级到SQLite)
- 限流错误 → 自动等待后重试 (最多3次)
- 字段验证失败 → 记录日志并跳过该条记录

#### 5.2 存储管理器 (`src/storage/storage_manager.py`)

**必须实现的功能**:

1. **主备存储切换**:
```python
class StorageManager:
    """统一存储管理器 (飞书主存储 + SQLite备份)"""

    def __init__(self):
        self.feishu = FeishuStorage()
        self.sqlite = SQLiteFallback()

    async def save(self, candidates: List[ScoredCandidate]) -> None:
        """主备存储策略

        1. 优先写入飞书多维表格
        2. 飞书失败 → 降级到SQLite备份
        3. SQLite轮询同步未同步记录
        """
        if not candidates:
            return

        # 尝试写入飞书
        try:
            await self.feishu.save(candidates)
            logger.info(f"✅ 飞书存储成功: {len(candidates)}条")
        except Exception as exc:
            logger.warning(f"⚠️  飞书存储失败,降级到SQLite: {exc}")
            await self.sqlite.save(candidates)
            logger.info(f"✅ SQLite备份成功: {len(candidates)}条")
```

2. **后台同步任务**:
```python
async def sync_from_sqlite(self) -> None:
    """将SQLite未同步记录回写到飞书

    调用时机:
    - 每日定时任务 (GitHub Actions)
    - 或手动执行 python -m src.storage.storage_manager
    """
    unsynced = await self.sqlite.get_unsynced()
    if not unsynced:
        logger.info("无未同步记录")
        return

    logger.info(f"发现{len(unsynced)}条未同步记录")

    try:
        await self.feishu.save(unsynced)
        urls = [c.url for c in unsynced]
        await self.sqlite.mark_synced(urls)
        logger.info(f"✅ 同步完成: {len(unsynced)}条")
    except Exception as exc:
        logger.error(f"❌ 同步失败: {exc}")
```

3. **定期清理**:
```python
async def cleanup(self) -> None:
    """清理已同步且过期的SQLite记录

    清理策略:
    - 保留7天 (constants.SQLITE_RETENTION_DAYS)
    - 仅清理已同步 (synced_to_feishu = 1)
    """
    await self.sqlite.cleanup_old_records()
    logger.info("SQLite已清理过期记录")
```

### Task 6: 飞书通知推送 (预计30分钟)

**目标**: 实现飞书Webhook卡片消息推送

#### 6.1 飞书通知器 (`src/notifier/feishu_notifier.py`)

**必须实现的功能**:

1. **卡片消息格式**:
```python
class FeishuNotifier:
    """飞书Webhook通知推送"""

    async def notify(self, candidates: List[ScoredCandidate]) -> None:
        """推送Top K高分候选到飞书群

        推送策略:
        - 仅推送总分 >= 6.0 的候选
        - 按总分降序排序
        - 取Top 5 (constants.NOTIFY_TOP_K)
        """
        if not candidates:
            return

        # 筛选 + 排序
        qualified = [c for c in candidates if c.total_score >= constants.MIN_TOTAL_SCORE]
        top_k = sorted(qualified, key=lambda x: x.total_score, reverse=True)[:constants.NOTIFY_TOP_K]

        if not top_k:
            logger.info("无高分候选,跳过通知")
            return

        card = self._build_card(top_k)
        await self._send_webhook(card)
```

2. **卡片内容设计**:
```python
def _build_card(self, candidates: List[ScoredCandidate]) -> dict:
    """构建飞书卡片消息

    格式:
    【标题】🎯 BenchScope 每日推荐 (2025-11-13)

    【内容】
    1. [High] Where Do LLMs Still Struggle?... (总分: 8.5/10)
       来源: arXiv | 活跃度: 7.0 | 可复现性: 9.0
       📊 评分依据: ...
       🔗 查看详情: http://arxiv.org/...

    2. [Medium] AgentBench v2... (总分: 7.2/10)
       ...
    """
    elements = []

    for i, candidate in enumerate(candidates, 1):
        priority_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }[candidate.priority]

        element = {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"""**{i}. {priority_emoji} [{candidate.priority.upper()}] {candidate.title[:60]}...**

总分: **{candidate.total_score:.1f}/10**
来源: {candidate.source} | 活跃度: {candidate.activity_score:.1f} | 可复现性: {candidate.reproducibility_score:.1f}

📊 评分依据: {candidate.reasoning[:100]}...

🔗 [查看详情]({candidate.url})
---
"""
            }
        }
        elements.append(element)

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🎯 BenchScope 每日推荐 ({datetime.now().strftime('%Y-%m-%d')})"
                },
                "template": "blue"
            },
            "elements": elements
        }
    }
```

3. **Webhook发送**:
```python
async def _send_webhook(self, card: dict) -> None:
    """发送飞书Webhook"""
    webhook_url = self.settings.feishu.webhook_url

    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=card, timeout=10)

        if response.status_code != 200:
            raise RuntimeError(f"飞书Webhook失败: {response.status_code} {response.text}")

        result = response.json()
        if result.get("code") != 0:
            raise RuntimeError(f"飞书Webhook返回错误: {result}")

        logger.info(f"✅ 飞书通知推送成功: {len(card['card']['elements'])}条")
```

### Task 7: 主流程集成 (预计20分钟)

**目标**: 集成所有模块到主流程 + 更新GitHub Actions

#### 7.1 主流程更新 (`src/main.py`)

**必须实现的完整流程**:

```python
async def main() -> None:
    """Phase 2 主流程

    流程:
    1. 数据采集 (arxiv/github/pwc/huggingface)
    2. 规则预筛选 (过滤50%低质量候选)
    3. LLM评分 (async批量评分)
    4. 存储入库 (飞书主 + SQLite备)
    5. 飞书通知 (推送Top 5)
    """
    logger.info("=" * 60)
    logger.info("BenchScope Phase 2 启动")
    logger.info("=" * 60)

    # Step 1: 数据采集
    logger.info("\n[1/5] 数据采集...")
    collectors = [
        ArxivCollector(),
        GitHubCollector(),
        PwCCollector(),
        HuggingFaceCollector()
    ]

    all_candidates = []
    for collector in collectors:
        try:
            candidates = await collector.collect()
            all_candidates.extend(candidates)
            logger.info(f"  ✓ {collector.__class__.__name__}: {len(candidates)}条")
        except Exception as exc:
            logger.error(f"  ✗ {collector.__class__.__name__}失败: {exc}")

    logger.info(f"采集完成: 共{len(all_candidates)}条原始候选\n")

    if not all_candidates:
        logger.warning("无采集数据,流程终止")
        return

    # Step 2: 规则预筛选
    logger.info("[2/5] 规则预筛选...")
    from src.prefilter.rule_filter import prefilter_batch
    filtered = prefilter_batch(all_candidates)
    logger.info(f"预筛选完成: 保留{len(filtered)}条 (过滤率{100*(1-len(filtered)/len(all_candidates)):.1f}%)\n")

    if not filtered:
        logger.warning("预筛选后无候选,流程终止")
        return

    # Step 3: LLM评分
    logger.info("[3/5] LLM评分...")
    from src.scorer.llm_scorer import LLMScorer
    async with LLMScorer() as scorer:
        scored = await scorer.score_batch(filtered)
    logger.info(f"评分完成: {len(scored)}条\n")

    # Step 4: 存储入库
    logger.info("[4/5] 存储入库...")
    from src.storage.storage_manager import StorageManager
    manager = StorageManager()
    await manager.save(scored)
    await manager.sync_from_sqlite()  # 同步未同步记录
    logger.info("存储完成\n")

    # Step 5: 飞书通知
    logger.info("[5/5] 飞书通知...")
    from src.notifier.feishu_notifier import FeishuNotifier
    notifier = FeishuNotifier()
    await notifier.notify(scored)
    logger.info("通知完成\n")

    # 统计信息
    high_priority = [c for c in scored if c.priority == "high"]
    medium_priority = [c for c in scored if c.priority == "medium"]
    avg_score = sum(c.total_score for c in scored) / len(scored) if scored else 0

    logger.info("=" * 60)
    logger.info("BenchScope Phase 2 完成")
    logger.info(f"  采集: {len(all_candidates)}条")
    logger.info(f"  预筛选: {len(filtered)}条")
    logger.info(f"  评分: {len(scored)}条")
    logger.info(f"  高优先级: {len(high_priority)}条")
    logger.info(f"  中优先级: {len(medium_priority)}条")
    logger.info(f"  平均分: {avg_score:.2f}/10")
    logger.info("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

#### 7.2 GitHub Actions工作流 (`.github/workflows/daily_collect.yml`)

**必须更新的配置**:

```yaml
name: BenchScope Daily Collection

on:
  schedule:
    - cron: '0 2 * * *'  # 每日UTC 2:00 (北京时间10:00)
  workflow_dispatch:      # 支持手动触发

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv venv
          source .venv/bin/activate
          uv pip install -r requirements.txt

      - name: Run BenchScope
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
          FEISHU_BITABLE_TABLE_ID: ${{ secrets.FEISHU_BITABLE_TABLE_ID }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          REDIS_URL: redis://localhost:6379/0
        run: |
          source .venv/bin/activate
          PYTHONPATH=. python -m src.main

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: collection-logs
          path: logs/
          retention-days: 7
```

## 单元测试要求

### Task 5 测试 (`tests/unit/test_storage.py` - 新增)

```python
import pytest
from src.models import ScoredCandidate
from src.storage.feishu_storage import FeishuStorage
from src.storage.storage_manager import StorageManager

@pytest.mark.asyncio
async def test_feishu_storage_record_format():
    """测试飞书记录格式转换"""
    storage = FeishuStorage()

    candidate = ScoredCandidate(
        title="Test Benchmark",
        url="https://example.com",
        source="arxiv",
        abstract="Test abstract",
        activity_score=7.0,
        reproducibility_score=8.0,
        license_score=9.0,
        novelty_score=6.0,
        relevance_score=7.5,
        reasoning="Test reasoning"
    )

    record = storage._to_feishu_record(candidate)

    assert "fields" in record
    assert record["fields"]["标题"] == "Test Benchmark"
    assert record["fields"]["总分"] == candidate.total_score
    assert record["fields"]["优先级"] == candidate.priority

@pytest.mark.asyncio
async def test_storage_manager_fallback():
    """测试存储管理器降级机制"""
    manager = StorageManager()

    # 模拟飞书失败,应降级到SQLite
    # (需要mock FeishuStorage.save抛出异常)
    ...
```

### Task 6 测试 (`tests/unit/test_notifier.py` - 新增)

```python
import pytest
from src.notifier.feishu_notifier import FeishuNotifier
from src.models import ScoredCandidate

@pytest.mark.asyncio
async def test_notifier_card_format():
    """测试飞书卡片格式"""
    notifier = FeishuNotifier()

    candidates = [
        ScoredCandidate(
            title="High Priority Benchmark",
            url="https://example.com/1",
            source="arxiv",
            activity_score=9.0,
            reproducibility_score=9.0,
            license_score=9.0,
            novelty_score=8.0,
            relevance_score=8.5,
            reasoning="Excellent benchmark"
        )
    ]

    card = notifier._build_card(candidates)

    assert card["msg_type"] == "interactive"
    assert "🎯 BenchScope" in card["card"]["header"]["title"]["content"]
    assert len(card["card"]["elements"]) == 1
```

## 验收标准

**Task 5: 飞书存储 + 存储管理器**
- [ ] `src/storage/feishu_storage.py` 实现批量写入(20条/批)
- [ ] `src/storage/storage_manager.py` 实现主备切换
- [ ] 飞书记录格式包含所有Phase 2字段
- [ ] 飞书写入失败自动降级到SQLite
- [ ] SQLite未同步记录可回写到飞书

**Task 6: 飞书通知推送**
- [ ] `src/notifier/feishu_notifier.py` 实现卡片消息
- [ ] 仅推送总分 >= 6.0的候选
- [ ] 按总分降序推送Top 5
- [ ] 卡片包含优先级、评分、来源等信息

**Task 7: 主流程集成**
- [ ] `src/main.py` 集成5个步骤 (采集→预筛选→评分→存储→通知)
- [ ] `.github/workflows/daily_collect.yml` 配置正确
- [ ] 所有环境变量通过GitHub Secrets配置
- [ ] 日志上传到Artifacts (保留7天)

**整体验收**:
- [ ] 运行 `PYTHONPATH=. python -m src.main` 完整流程成功
- [ ] 飞书多维表格有新数据写入
- [ ] 飞书群收到通知消息
- [ ] GitHub Actions手动触发成功
- [ ] 单元测试通过: `pytest tests/unit -v`

## 关键注意事项

1. **飞书API限制**:
   - 批量写入最多20条/请求
   - 限流: 100请求/分钟
   - 需要0.6秒间隔 (`constants.FEISHU_RATE_LIMIT_DELAY`)

2. **错误处理**:
   - 飞书API失败 → 自动降级到SQLite
   - SQLite轮询同步 → 每日定时任务
   - 所有异常必须记录详细日志

3. **配置管理**:
   - 所有敏感信息通过环境变量配置
   - 使用 `src/config.py` 的 `get_settings()`
   - GitHub Secrets必须包含所有飞书凭证

4. **测试要求**:
   - 飞书API Mock测试 (避免真实调用)
   - SQLite降级逻辑必须测试
   - 卡片格式必须符合飞书规范

5. **Linus哲学**:
   - 简单优先: 不要过度工程
   - 最大嵌套层级 ≤ 3
   - 关键逻辑必须中文注释

## 实施时间预估

- Task 5 (飞书存储+管理器): 40分钟
- Task 6 (飞书通知): 30分钟
- Task 7 (主流程+Actions): 20分钟
- 单元测试编写: 30分钟
- 调试验证: 30分钟

**总计**: ~2.5小时

## 完成后通知

实现完成后,通知Claude Code进行验收测试。Claude Code将:
1. 检查代码是否符合Phase 2规范
2. 运行完整单元测试
3. 手动测试完整流程 (需配置飞书API)
4. 更新测试报告
5. 验收通过后准备部署

---

**开发者**: Codex
**审核人**: Claude Code
**截止日期**: 2025-11-13 (Phase 2完整功能)
