# P14: 重复推送根因分析与修复方案

## 问题诊断

### 现象
2025-12-06和2025-12-07连续两天推送了相同的GitHub仓库:
- `SIGMME/IWR-Bench`
- `ace-agent/ace`

### 调查过程

#### 第一阶段：P13分页修复验证
通过详细调试，确认P13分页修复已生效：
```
GET /records 分页结果:
Page 1: items=500, has_more=True
Page 2: items=500, has_more=True
Page 3: items=3, has_more=False
总记录: 1003条 (全部读取成功)
唯一URL数: 280条 (数据本身存在大量重复)
```

#### 第二阶段：目标仓库搜索
在飞书表格全量数据中搜索目标仓库：
```python
targets = ['IWR-Bench', 'ace-agent/ace', 'SIGMME']
# 搜索URL字段和标题字段
# 结果: 未在飞书表格中找到目标仓库!
```

### 根本原因

**目标仓库从未被成功写入飞书表格！**

#### 问题链条
1. **P13修复前**: `get_existing_urls()`使用POST search API，分页bug导致只能读取前500条记录（约276个URL）
2. **遗漏检测**: 目标仓库URL不在前500条记录的去重集合中
3. **错误判断**: 每次运行都判断为"新记录"
4. **写入失败**: 尝试写入飞书但失败（原因待查）
5. **错误返回**: `save()`方法返回了"待写入列表"而非"实际成功写入列表"
6. **错误通知**: 基于错误的返回值发送了推送通知

---

## 代码分析

### 当前存储流程 (`feishu_storage.py:146-202`)

```python
async def save(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """批量写入飞书多维表格"""

    # 获取已存在URL用于去重
    existing_urls = await self.get_existing_urls()

    # 去重
    deduped_candidates: list[ScoredCandidate] = []
    for cand in candidates:
        url_key = canonicalize_url(cand.url)
        if url_key and url_key in existing_urls:
            continue
        deduped_candidates.append(cand)

    # 批量写入
    async with httpx.AsyncClient(timeout=10) as client:
        for start in range(0, len(deduped_candidates), self.batch_size):
            chunk = deduped_candidates[start : start + self.batch_size]
            records = [self._to_feishu_record(c) for c in chunk]
            await self._batch_create_records(client, records)  # 可能部分失败!

            # 将当前批次加入缓存
            for cand in chunk:
                url_key = canonicalize_url(cand.url)
                if url_key:
                    existing_urls.add(url_key)

    return deduped_candidates  # BUG: 返回全部去重候选，而非实际成功写入的
```

### 问题点

1. **返回值语义错误**: `save()`返回的是"去重后待写入的列表"，而非"实际成功写入的列表"
2. **部分失败无感知**: 如果`_batch_create_records()`部分记录写入失败，调用方无从得知
3. **通知与存储不一致**: `main.py`基于`save()`返回值发送通知，但实际存储可能失败

---

## 解决方案

### 方案A：追踪实际写入结果（推荐）

修改`save()`方法，只返回实际成功写入的记录：

```python
async def save(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    """批量写入飞书多维表格

    Returns:
        实际成功写入的候选列表（用于后续通知）
    """
    if not candidates:
        return []

    await self._ensure_access_token()
    existing_urls = await self.get_existing_urls()

    # 去重
    deduped_candidates: list[ScoredCandidate] = []
    for cand in candidates:
        url_key = canonicalize_url(cand.url)
        if url_key and url_key in existing_urls:
            continue
        deduped_candidates.append(cand)

    if not deduped_candidates:
        logger.info("飞书去重后无新增记录，跳过写入")
        return []

    # P14修复: 追踪实际成功写入的记录
    actually_saved: list[ScoredCandidate] = []

    async with httpx.AsyncClient(timeout=10) as client:
        for start in range(0, len(deduped_candidates), self.batch_size):
            chunk = deduped_candidates[start : start + self.batch_size]
            records = [self._to_feishu_record(c) for c in chunk]

            try:
                # P14: 获取实际写入数量
                created_count = await self._batch_create_records_with_count(client, records)

                # 只有全部成功才计入
                if created_count == len(chunk):
                    actually_saved.extend(chunk)
                    for cand in chunk:
                        url_key = canonicalize_url(cand.url)
                        if url_key:
                            existing_urls.add(url_key)
                else:
                    logger.warning(
                        "飞书批次部分失败: 预期%d条, 实际%d条",
                        len(chunk), created_count
                    )
                    # 部分成功的情况下，需要查询实际写入的记录
                    # 简化处理：部分失败时不计入已保存列表

            except FeishuAPIError as exc:
                if "access_token不存在" in str(exc):
                    logger.warning("飞书写入token失效，自动刷新后重试当前批次")
                    await self._ensure_access_token()
                    try:
                        created_count = await self._batch_create_records_with_count(client, records)
                        if created_count == len(chunk):
                            actually_saved.extend(chunk)
                            for cand in chunk:
                                url_key = canonicalize_url(cand.url)
                                if url_key:
                                    existing_urls.add(url_key)
                    except Exception as retry_exc:
                        logger.error("飞书批次重试失败: %s", retry_exc)
                else:
                    logger.error("飞书批次写入失败: %s", exc)

            if start + self.batch_size < len(deduped_candidates):
                await asyncio.sleep(self.rate_interval)

    logger.info(
        "飞书写入完成: 去重%d条, 实际成功%d条",
        len(deduped_candidates), len(actually_saved)
    )
    return actually_saved


async def _batch_create_records_with_count(
    self, client: httpx.AsyncClient, records: List[dict]
) -> int:
    """批量创建记录并返回实际创建数量

    P14新增: 返回实际成功创建的记录数，而非假设全部成功
    """
    url = (
        f"{self.base_url}/bitable/v1/apps/{self.settings.feishu.bitable_app_token}/"
        f"tables/{self.settings.feishu.bitable_table_id}/records/batch_create"
    )

    await self._ensure_field_cache(client)

    filtered_records = [
        {"fields": self._filter_existing_fields(record["fields"])}
        for record in records
    ]
    filtered_records = [r for r in filtered_records if r["fields"]]

    if not filtered_records:
        logger.error("飞书表字段缺失，导致本批次无可写字段")
        return 0

    resp = await self._request_with_retry(
        client, "POST", url,
        headers=self._auth_header(),
        json={"records": filtered_records},
    )
    resp.raise_for_status()

    data = resp.json()
    code = data.get("code")
    msg = data.get("msg", "")

    if code != 0:
        logger.error("飞书API业务错误: code=%s, msg=%s", code, msg)
        raise FeishuAPIError(f"飞书API返回错误: {code} - {msg}")

    # P14: 返回实际创建的记录数
    created_records = data.get("data", {}).get("records", [])
    actual_count = len(created_records)

    logger.info(
        "飞书批次写入: 提交%d条, 实际创建%d条",
        len(filtered_records), actual_count
    )

    return actual_count
```

### 方案B：写入后验证（更可靠但性能差）

写入后立即查询验证：

```python
async def save(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
    # ... 写入逻辑 ...

    # P14: 写入后验证
    await asyncio.sleep(1)  # 等待飞书数据同步
    verified_urls = await self.get_existing_urls()

    actually_saved = []
    for cand in deduped_candidates:
        url_key = canonicalize_url(cand.url)
        if url_key and url_key in verified_urls:
            actually_saved.append(cand)

    if len(actually_saved) != len(deduped_candidates):
        logger.warning(
            "飞书写入验证: 预期%d条, 实际%d条",
            len(deduped_candidates), len(actually_saved)
        )

    return actually_saved
```

---

## 实施步骤

### Step 1: 修改 `_batch_create_records()` 方法

**文件**: `src/storage/feishu_storage.py`
**位置**: 约行204-268

将方法重命名为 `_batch_create_records_with_count()`，返回实际创建数量。

### Step 2: 修改 `save()` 方法

**文件**: `src/storage/feishu_storage.py`
**位置**: 约行146-202

实现方案A的逻辑，追踪并只返回实际成功写入的记录。

### Step 3: 验证修复

```bash
# 测试写入并验证返回值
.venv/bin/python -c "
import asyncio
from src.storage import FeishuStorage
from src.models import ScoredCandidate

async def test():
    storage = FeishuStorage()

    # 创建测试候选
    test_candidate = ScoredCandidate(
        title='P14 Test Candidate',
        source='test',
        url='https://github.com/test/p14-test-' + str(int(time.time())),
        # ... 其他字段
    )

    saved = await storage.save([test_candidate])
    print(f'返回保存数: {len(saved)}')

    # 验证是否真正写入
    urls = await storage.get_existing_urls()
    url_key = canonicalize_url(test_candidate.url)
    print(f'验证结果: {url_key in urls}')

asyncio.run(test())
"
```

---

## 验收标准

- [ ] `save()`方法返回的记录数与飞书实际新增记录数一致
- [ ] 部分写入失败时，只返回成功的记录
- [ ] 连续两次运行，第二次返回空列表（去重生效）
- [ ] 日志清晰显示"提交X条，实际创建Y条"

---

## 风险评估

### 低风险
- 修改不影响现有字段映射
- 修改不影响去重逻辑
- 修改向后兼容（调用方无需修改）

### 注意事项
- 如果飞书API有延迟，可能出现写入成功但立即查询找不到的情况
- 建议在验证时增加短暂等待

---

## 相关文件

- `src/storage/feishu_storage.py` - 需要修改的文件
- `src/storage/storage_manager.py` - 调用方，无需修改
- `src/main.py` - 最终调用方，无需修改
- `.claude/specs/benchmark-intelligence-agent/CODEX-P13-PAGINATION-FIX.md` - 前置修复

---

## 附录：调试日志

### 飞书表格数据分布
```
总记录数: 1003
唯一URL数: 280
重复率: 72.2%

重复最多的URL (HELM来源):
- 每个HELM URL重复约6次
```

### 目标仓库搜索结果
```
搜索关键词: IWR-Bench, ace-agent/ace, SIGMME
搜索范围: URL字段 + 标题字段
结果: 0条匹配
结论: 目标仓库从未成功写入飞书表格
```
