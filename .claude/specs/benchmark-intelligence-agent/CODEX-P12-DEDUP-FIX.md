# P12: 修复飞书推送重复问题 - 去重时间字段错误

## 问题诊断

### 现象
2025-12-06和2025-12-07连续两天推送了相同的GitHub仓库:
- `SIGMME/IWR-Bench` (11月19日发布，12月6日推送6.4分，12月7日推送7.2分)
- `ace-agent/ace` (11月18日发布，两天都推送7.1分)

### 根本原因
**去重逻辑使用了内容发布日期(`publish_date`)而不是记录写入时间**

当前代码 `src/main.py:200-206`:
```python
for record in existing_records:
    publish_date = record.get("publish_date")  # 问题在这里
    ...
    if publish_date >= now - timedelta(days=window_days):  # 按发布日期判断
        recent_urls_by_source.setdefault(source_value, set()).add(url_key)
```

**时间线分析**:
- `SIGMME/IWR-Bench` 发布日期: 2025-11-19
- GitHub默认去重窗口: 14天
- 2025-12-07 - 14天 = 2025-11-23
- 11-19 < 11-23 (不在窗口内) -> 被当作新候选重复采集和推送

### 影响范围
- 所有发布日期超过去重窗口的记录都可能被重复推送
- GitHub仓库(14天窗口)影响最大
- arXiv(3天窗口)影响更严重

---

## 解决方案

### 方案选择: 飞书表格记录自动时间戳

飞书多维表格支持系统字段`创建时间`，自动记录每条记录的写入时间，无需手动维护。

**优势**:
1. 零代码改动飞书存储层
2. 系统自动维护，不可篡改
3. 仅需修改去重查询逻辑

---

## 实施步骤

### Step 1: 飞书表格添加系统字段

在飞书多维表格中添加`创建时间`系统字段:
1. 打开飞书多维表格
2. 点击"+"添加字段
3. 选择"创建时间"类型
4. 字段名保持默认`创建时间`

**注意**: 这是一次性手动操作，需要用户在飞书表格界面完成。

### Step 2: 修改 feishu_storage.py - 读取记录时返回创建时间

**文件**: `src/storage/feishu_storage.py`
**方法**: `read_existing_records()`

**当前代码** (约行590-679):
```python
async def read_existing_records(self) -> List[dict[str, Any]]:
    """查询飞书已存在的记录，含URL/发布时间/来源，用于时间窗去重"""
    ...
    for item in items:
        fields = item.get("fields", {})
        url_obj = fields.get(url_field)
        publish_raw = fields.get(publish_field)
        ...
        if url_key:
            source_field = self.FIELD_MAPPING.get("source", "来源")
            source_value = fields.get(source_field, "default")
            record_item: dict[str, Any] = {
                "url": str(url_value),
                "url_key": url_key,
                "publish_date": publish_date,
                "source": str(source_value),
            }
            records.append(record_item)
```

**修改后代码**:
```python
async def read_existing_records(self) -> List[dict[str, Any]]:
    """查询飞书已存在的记录，含URL/发布时间/创建时间/来源，用于时间窗去重

    P12修复: 新增created_at字段（飞书系统字段），用于基于记录写入时间的去重
    """
    ...
    for item in items:
        fields = item.get("fields", {})
        url_obj = fields.get(url_field)
        publish_raw = fields.get(publish_field)

        # P12新增: 读取飞书系统字段"创建时间"
        created_raw = fields.get("创建时间")
        created_at: Optional[datetime] = None
        if isinstance(created_raw, (int, float)):
            created_at = datetime.fromtimestamp(created_raw / 1000)
        elif isinstance(created_raw, str) and created_raw:
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                logger.debug("无法解析创建时间: %s", created_raw)
        if created_at:
            created_at = created_at.replace(tzinfo=None)

        ...
        if url_key:
            source_field = self.FIELD_MAPPING.get("source", "来源")
            source_value = fields.get(source_field, "default")
            record_item: dict[str, Any] = {
                "url": str(url_value),
                "url_key": url_key,
                "publish_date": publish_date,
                "created_at": created_at,  # P12新增
                "source": str(source_value),
            }
            records.append(record_item)
```

### Step 3: 修改 main.py - 使用created_at进行去重

**文件**: `src/main.py`
**位置**: 约行189-228 (Step 1.5 去重逻辑)

**当前代码**:
```python
# 2. 与飞书已存在URL去重（仅对比近N天记录，降低新鲜度损耗）
storage = StorageManager()
now = datetime.now()
existing_records: list[dict[str, Any]] = await storage.read_existing_records()
# 按来源应用不同的去重窗口
recent_urls_by_source: dict[str, set[str]] = {}
for record in existing_records:
    publish_date = record.get("publish_date")  # 问题: 使用发布日期
    url_value = record.get("url")
    source_value = record.get("source", "default")
    url_key = canonicalize_url(url_value)
    if not isinstance(publish_date, datetime) or not url_key:
        continue
    window_days = constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE.get(
        source_value, constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE["default"]
    )
    if publish_date >= now - timedelta(days=window_days):
        recent_urls_by_source.setdefault(source_value, set()).add(url_key)
```

**修改后代码**:
```python
# 2. 与飞书已存在URL去重（基于记录创建时间，避免老内容新入库后被重复推送）
storage = StorageManager()
now = datetime.now()
existing_records: list[dict[str, Any]] = await storage.read_existing_records()

# P12修复: 使用created_at（记录写入时间）而不是publish_date（内容发布时间）
recent_urls_by_source: dict[str, set[str]] = {}
for record in existing_records:
    # 优先使用created_at，兼容旧数据回退到publish_date
    dedup_time = record.get("created_at") or record.get("publish_date")
    url_value = record.get("url")
    source_value = record.get("source", "default")
    url_key = canonicalize_url(url_value)
    if not isinstance(dedup_time, datetime) or not url_key:
        continue
    window_days = constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE.get(
        source_value, constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE["default"]
    )
    if dedup_time >= now - timedelta(days=window_days):
        recent_urls_by_source.setdefault(source_value, set()).add(url_key)
```

### Step 4: 扩大默认去重窗口 (可选但推荐)

**文件**: `src/common/constants.py`
**位置**: 约行701-706

**当前配置**:
```python
DEDUP_LOOKBACK_DAYS: Final[int] = 14
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 3,
    "default": DEDUP_LOOKBACK_DAYS,
}
```

**修改后配置**:
```python
DEDUP_LOOKBACK_DAYS: Final[int] = 30  # P12: 扩大默认窗口到30天
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
    "arxiv": 7,  # P12: arXiv扩大到7天，与采集窗口一致
    "github": 30,  # P12: GitHub明确指定30天
    "default": DEDUP_LOOKBACK_DAYS,
}
```

---

## 测试验证计划

### 单元测试

```python
# tests/test_dedup.py
import pytest
from datetime import datetime, timedelta
from src.common.url_utils import canonicalize_url

def test_dedup_uses_created_at():
    """验证去重使用记录创建时间而非发布时间"""
    now = datetime.now()

    # 模拟: 发布日期很早(30天前)，但创建时间很近(1天前)
    record = {
        "url": "https://github.com/test/repo",
        "publish_date": now - timedelta(days=30),
        "created_at": now - timedelta(days=1),
        "source": "github",
    }

    window_days = 14
    dedup_time = record.get("created_at") or record.get("publish_date")

    # 应该在去重窗口内（基于created_at）
    assert dedup_time >= now - timedelta(days=window_days)
```

### 集成测试

1. 运行完整流程: `.venv/bin/python -m src.main`
2. 检查日志确认去重逻辑使用created_at
3. 第二天再次运行，验证昨天入库的记录被正确去重

### 验收标准

- [ ] 飞书表格已添加"创建时间"系统字段
- [ ] `read_existing_records()` 返回 `created_at` 字段
- [ ] `main.py` 去重逻辑使用 `created_at`
- [ ] 去重窗口已扩大到30天
- [ ] 连续两天运行不产生重复推送
- [ ] 日志输出显示正确的去重统计

---

## 回滚方案

如果出现问题，可以回滚到使用 `publish_date` 的旧逻辑:
```python
# main.py 去重逻辑
dedup_time = record.get("publish_date")  # 回滚到旧行为
```

---

## 相关文件

- `src/main.py` - 主流程去重逻辑
- `src/storage/feishu_storage.py` - 飞书记录读取
- `src/common/constants.py` - 去重窗口配置
- `src/common/url_utils.py` - URL规范化（不需要修改）
