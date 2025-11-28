# Codex开发指令：修复通知重复推送问题

## 问题诊断

### 现象
连续两天的飞书推送中出现相同条目：
- `wilpel/caveman-compression` 在11/27和11/28均被推送
- 多篇arXiv论文连续两天重复推送
- 评分略有不同（7.1 vs 6.8），说明是独立评估的结果

### 根本原因
**数据流断层**：通知模块没有获取到存储层的去重结果

```
当前数据流（有BUG）：
Step 1-4: 采集 → 去重 → 预筛选 → 评分 → scored列表(15条)
Step 6:   storage.save(scored) → 飞书去重，写入10条，跳过5条重复
Step 7:   notifier.notify(scored) → 使用原始15条推送！包含5条重复项！
```

**关键代码** (main.py:288-298)：
```python
# 当前代码（有BUG）
await storage.save(scored)  # 返回None，调用方不知道哪些被去重
...
await notifier.notify(scored)  # 使用原始列表，包含已存在的URL
```

## 解决方案

### Step 1: 修改 feishu_storage.py

**文件**: `src/storage/feishu_storage.py`
**修改**: `save()` 方法返回实际写入的记录列表

#### 当前代码 (line 110-157)
```python
async def save(self, candidates: List[ScoredCandidate]) -> None:
    """批量写入飞书多维表格"""

    if not candidates:
        return

    await self._ensure_access_token()
    existing_urls = await self.get_existing_urls()

    # 写入前按URL做二次去重
    deduped_candidates: list[ScoredCandidate] = []
    skipped = 0
    for cand in candidates:
        url_key = canonicalize_url(cand.url)
        if url_key and url_key in existing_urls:
            skipped += 1
            continue
        deduped_candidates.append(cand)

    if skipped:
        logger.info("飞书写入前去重: 跳过%d条已存在URL", skipped)

    if not deduped_candidates:
        logger.info("飞书去重后无新增记录，跳过写入")
        return

    # ... 写入逻辑 ...
```

#### 修改后代码
```python
async def save(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """批量写入飞书多维表格

    Args:
        candidates: 待写入的候选列表

    Returns:
        实际写入的候选列表（去重后），用于后续通知
    """

    if not candidates:
        return []  # 返回空列表而非None

    await self._ensure_access_token()
    existing_urls = await self.get_existing_urls()

    # 写入前按URL做二次去重
    deduped_candidates: list[ScoredCandidate] = []
    skipped = 0
    for cand in candidates:
        url_key = canonicalize_url(cand.url)
        if url_key and url_key in existing_urls:
            skipped += 1
            continue
        deduped_candidates.append(cand)

    if skipped:
        logger.info("飞书写入前去重: 跳过%d条已存在URL", skipped)

    if not deduped_candidates:
        logger.info("飞书去重后无新增记录，跳过写入")
        return []  # 返回空列表

    # ... 写入逻辑保持不变 ...

    return deduped_candidates  # 新增：返回实际写入的列表
```

### Step 2: 修改 storage_manager.py

**文件**: `src/storage/storage_manager.py`
**修改**: `save()` 方法传递返回值

检查该文件是否有包装层，如有需同步修改返回类型。

### Step 3: 修改 main.py

**文件**: `src/main.py`
**修改**: 使用存储返回值进行通知

#### 当前代码 (line 288-298)
```python
# Step 6: 存储入库
logger.info("[6/7] 存储入库...")
await storage.save(scored)
await storage.sync_from_sqlite()
await storage.cleanup()
logger.info("存储完成\n")

# Step 7: 飞书通知
logger.info("[7/7] 飞书通知...")
notifier = FeishuNotifier(settings=settings)
await notifier.notify(scored)  # BUG: 使用原始列表
```

#### 修改后代码
```python
# Step 6: 存储入库
logger.info("[6/7] 存储入库...")
actually_saved = await storage.save(scored)  # 获取实际写入的记录
await storage.sync_from_sqlite()
await storage.cleanup()
logger.info("存储完成: 新增%d条\n", len(actually_saved))

# Step 7: 飞书通知（仅通知新增记录）
logger.info("[7/7] 飞书通知...")
notifier = FeishuNotifier(settings=settings)
if actually_saved:
    await notifier.notify(actually_saved)  # 只通知新增的
    logger.info("通知完成: %d条新增候选\n", len(actually_saved))
else:
    logger.info("无新增候选，跳过通知\n")
```

### Step 4: 更新统计日志

**文件**: `src/main.py`
**修改**: 结尾统计区分"评分"和"实际入库"

#### 当前代码 (line 301-313)
```python
high_priority = [c for c in scored if c.priority == "high"]
medium_priority = [c for c in scored if c.priority == "medium"]
avg_score = sum(c.total_score for c in scored) / len(scored) if scored else 0

logger.info("=" * 60)
logger.info("BenchScope Phase 2 完成")
logger.info("  采集: %d条", len(all_candidates))
logger.info("  去重: %d条新发现 (过滤%d条重复)", len(deduplicated), duplicate_count)
logger.info("  预筛选: %d条", len(filtered))
logger.info("  高优先级: %d条", len(high_priority))
logger.info("  中优先级: %d条", len(medium_priority))
logger.info("  平均分: %.2f/10", avg_score)
logger.info("=" * 60)
```

#### 修改后代码
```python
# 从实际入库的记录统计
high_priority = [c for c in actually_saved if c.priority == "high"]
medium_priority = [c for c in actually_saved if c.priority == "medium"]
avg_score = sum(c.total_score for c in actually_saved) / len(actually_saved) if actually_saved else 0

# 统计跳过的重复记录
skipped_count = len(scored) - len(actually_saved)

logger.info("=" * 60)
logger.info("BenchScope Phase 2 完成")
logger.info("  采集: %d条", len(all_candidates))
logger.info("  去重(Step1.5): %d条新发现 (过滤%d条)", len(deduplicated), duplicate_count)
logger.info("  预筛选: %d条", len(filtered))
logger.info("  评分: %d条", len(scored))
logger.info("  实际入库: %d条 (跳过%d条飞书已存在)", len(actually_saved), skipped_count)
logger.info("  推送: 高%d条, 中%d条", len(high_priority), len(medium_priority))
logger.info("  平均分: %.2f/10", avg_score)
logger.info("=" * 60)
```

## 测试验证

### 单元测试
```python
# tests/test_storage_dedup.py
import pytest
from src.storage import FeishuStorage
from src.models import ScoredCandidate

@pytest.mark.asyncio
async def test_save_returns_actually_written():
    """验证save()返回实际写入的记录"""
    storage = FeishuStorage()

    # 准备测试数据
    candidates = [
        ScoredCandidate(title="New Item", url="https://example.com/new", ...),
        ScoredCandidate(title="Existing Item", url="https://example.com/existing", ...),
    ]

    # 模拟existing包含一个URL
    # ...

    result = await storage.save(candidates)

    # 验证只返回新增的
    assert len(result) == 1
    assert result[0].url == "https://example.com/new"
```

### 集成测试
```bash
# 运行完整流程
.venv/bin/python -m src.main

# 检查日志输出
# 期望看到:
# - "存储完成: 新增X条"
# - "通知完成: X条新增候选"
# - 飞书推送不应包含前一天已推送的项目
```

### 手动验证
1. 运行完整流程两次（间隔1小时以上）
2. 第二次运行时，检查飞书推送是否只包含新增候选
3. 验证日志中"跳过X条飞书已存在"的数量与第一次运行的入库数量一致

## 成功标准

- [ ] `feishu_storage.save()` 返回 `List[ScoredCandidate]`
- [ ] `main.py` 使用返回值进行通知
- [ ] 日志清晰区分"评分数"和"实际入库数"
- [ ] 连续运行两次，第二次不推送重复项
- [ ] 单元测试通过
- [ ] 代码符合PEP8规范

## 风险评估

**低风险修改**：
- 仅修改返回类型和调用逻辑
- 不改变去重算法
- 不影响数据写入
- 向后兼容（原来调用方忽略返回值）

## 预计工时

- 代码修改: 30分钟
- 测试验证: 30分钟
- 总计: 1小时
