# Codex开发指令：优化去重逻辑解决数据新鲜度问题

## 文档元信息
- **创建时间**: 2025-11-22
- **创建者**: Claude Code
- **执行者**: Codex
- **优先级**: P0 (紧急)
- **预计工作量**: 45分钟
- **前置依赖**: 无

---

## 问题诊断

### 现状数据（2025-11-22 21:44实测）

```
采集: 266条
  - arXiv: 100条（全部是最近7天内发布的新论文）
  - HuggingFace: 47条
  - GitHub: 9条
  - 其他: 110条

去重: 3条新发现（全部来自GitHub）
  - arXiv: 100条 → 0条新发现（100%重复）
  - HuggingFace: 47条 → 0条新发现（100%重复）
  - GitHub: 9条 → 3条新发现（67%重复）

去重率: 99.2%（极高，系统几乎无法发现新Benchmark）
```

### arXiv时间分布验证

运行时间分布分析脚本后确认：
```
arXiv发布时间分布:
  7天内: 100条 (100.0%)  ← 采集到的都是真正的新论文
  7-14天: 0条
  14-30天: 0条
```

**关键发现**：采集逻辑完全正常，问题在去重逻辑。

### 根本原因

**时间窗口重叠导致重复**：
- arXiv 7天窗口：每天运行时有6天重叠
- 示例：
  - 昨天（11-21）采集：11-14到11-21的论文
  - 今天（11-22）采集：11-15到11-22的论文
  - **重叠6天**：约85%的论文会重复

**当前去重逻辑问题**：
- 去重时对比**全部飞书历史数据**（包含最近30-60天所有记录）
- URL相同即认为重复，不考虑时间因素
- 导致：每天只能发现1-2天窗口内的新数据，其余全部被标记为重复

---

## 解决方案

### 核心思路：去重时只对比最近N天的飞书数据

**变更前**：
- 从飞书读取**所有历史URL**进行去重
- 只要URL存在就标记为重复

**变更后**：
- 从飞书读取所有记录（包含发布时间）
- 只对比**最近14天内**的记录（可配置）
- 超过14天的旧记录不参与去重

**预期效果**：
- arXiv去重率从100%降至30-50%
- 每天能发现10-30条新论文
- 保留长期历史数据，不影响数据完整性

---

## 详细实施步骤

### Step 1: 新增常量配置

**文件**: `src/common/constants.py`
**位置**: 文件末尾（约第100行后）

**新增代码**：
```python
# ============================================================
# 去重配置
# ============================================================

# 去重时只对比最近N天的飞书数据
# 超过此天数的历史记录不参与去重
# 建议值：14-30天
DEDUP_LOOKBACK_DAYS: Final[int] = 14
```

---

### Step 2: 新增 `read_existing_records` 方法

**文件**: `src/storage/feishu_storage.py`
**位置**: 在 `read_existing_urls` 方法后（约第180行）

**新增方法**：
```python
async def read_existing_records(self) -> List[dict]:
    """读取飞书表格中的所有记录（包含URL和发布时间）

    用于智能去重：只对比最近N天的数据

    Returns:
        List[dict]: 记录列表，每条包含:
            - url: str - 候选URL
            - publish_date: Optional[datetime] - 发布时间（可能为None）
    """
    records = await self._read_all_records()

    result = []
    for record in records:
        fields = record.get("fields", {})
        url = fields.get("URL", "")

        # 解析发布时间
        publish_date_str = fields.get("开源时间", "")
        publish_date = None

        if publish_date_str:
            try:
                # 支持ISO 8601格式（飞书默认格式）
                publish_date = datetime.fromisoformat(
                    publish_date_str.replace("Z", "+00:00")
                )
                # 移除时区信息，统一为naive datetime便于比较
                publish_date = publish_date.replace(tzinfo=None)
            except Exception as e:
                logger.debug(f"解析发布时间失败: {publish_date_str}, 错误: {e}")

        if url:
            result.append({
                "url": url,
                "publish_date": publish_date
            })

    logger.info(f"从飞书读取到 {len(result)} 条历史记录")
    return result
```

**需要在文件顶部添加导入**（如果尚未导入）：
```python
from datetime import datetime, timedelta
```

---

### Step 3: 修改 `src/main.py` 去重逻辑

**文件**: `src/main.py`
**位置**: 去重段（约第175-210行）

**当前代码**（需要替换）：
```python
logger.info("[1.5/7] URL去重...")

# 本次采集内部去重
seen_urls = set()
deduplicated = []
internal_dup = 0

for c in raw_candidates:
    if c.url not in seen_urls:
        seen_urls.add(c.url)
        deduplicated.append(c)
    else:
        internal_dup += 1

logger.info(f"本次采集内部去重: 过滤{internal_dup}条重复URL")

# 与飞书历史数据去重
existing_urls = await storage.read_existing_urls()
unique_candidates = [c for c in deduplicated if c.url not in existing_urls]

logger.info(
    f"去重完成: 过滤{len(deduplicated)-len(unique_candidates)}条重复,"
    f"保留{len(unique_candidates)}条新发现"
)
```

**修改后代码**：
```python
logger.info("[1.5/7] URL去重...")

# 本次采集内部去重
seen_urls = set()
deduplicated = []
internal_dup = 0

for c in raw_candidates:
    if c.url not in seen_urls:
        seen_urls.add(c.url)
        deduplicated.append(c)
    else:
        internal_dup += 1

logger.info(f"本次采集内部去重: 过滤{internal_dup}条重复URL")

# 与飞书历史数据去重（只对比最近N天）
from datetime import datetime, timedelta
from collections import Counter

cutoff_date = datetime.now() - timedelta(days=constants.DEDUP_LOOKBACK_DAYS)

# 读取飞书所有记录（包含发布时间）
existing_records = await storage.read_existing_records()

# 筛选最近N天的记录
recent_records = [
    r for r in existing_records
    if r.get("publish_date") and r["publish_date"] >= cutoff_date
]

# 提取最近N天的URL集合
recent_urls = {r["url"] for r in recent_records}

# 智能去重：只对比最近N天的数据
unique_candidates = [c for c in deduplicated if c.url not in recent_urls]

# 输出详细统计
total_history = len(existing_records)
recent_history = len(recent_records)
filtered_count = len(deduplicated) - len(unique_candidates)

logger.info(
    f"去重完成: 飞书总记录{total_history}条, "
    f"最近{constants.DEDUP_LOOKBACK_DAYS}天{recent_history}条, "
    f"过滤{filtered_count}条重复, "
    f"保留{len(unique_candidates)}条新发现"
)

# 统计按来源的去重情况
collected_sources = Counter(c.source for c in raw_candidates)
new_sources = Counter(c.source for c in unique_candidates)

logger.info("===== 去重后按来源统计 =====")
for source in sorted(collected_sources.keys()):
    collected = collected_sources[source]
    new_found = new_sources.get(source, 0)
    dup_rate = (collected - new_found) / collected * 100 if collected else 0

    logger.info(
        f"  {source.ljust(15)}: {new_found}条新发现 / {collected}条采集 "
        f"(去重率{dup_rate:.1f}%)"
    )
```

---

### Step 4: 更新导入语句

**文件**: `src/main.py`
**位置**: 文件顶部的import区域

确保包含以下导入：
```python
from datetime import datetime, timedelta
from collections import Counter
```

**文件**: `src/storage/feishu_storage.py`
**位置**: 文件顶部的import区域

确保包含以下导入：
```python
from datetime import datetime
```

---

## 完整代码对比

### `src/common/constants.py` 新增

```python
# ============================================================
# 去重配置
# ============================================================

# 去重时只对比最近N天的飞书数据
DEDUP_LOOKBACK_DAYS: Final[int] = 14
```

### `src/storage/feishu_storage.py` 新增方法

在 `read_existing_urls` 方法后添加：

```python
async def read_existing_records(self) -> List[dict]:
    """读取飞书表格中的所有记录（包含URL和发布时间）

    用于智能去重：只对比最近N天的数据

    Returns:
        List[dict]: 记录列表，每条包含:
            - url: str - 候选URL
            - publish_date: Optional[datetime] - 发布时间
    """
    records = await self._read_all_records()

    result = []
    for record in records:
        fields = record.get("fields", {})
        url = fields.get("URL", "")

        # 解析发布时间
        publish_date_str = fields.get("开源时间", "")
        publish_date = None

        if publish_date_str:
            try:
                publish_date = datetime.fromisoformat(
                    publish_date_str.replace("Z", "+00:00")
                )
                publish_date = publish_date.replace(tzinfo=None)
            except Exception as e:
                logger.debug(f"解析发布时间失败: {publish_date_str}, 错误: {e}")

        if url:
            result.append({
                "url": url,
                "publish_date": publish_date
            })

    logger.info(f"从飞书读取到 {len(result)} 条历史记录")
    return result
```

---

## 测试验证计划

### 测试1: 验证去重统计日志

**运行命令**:
```bash
.venv/bin/python -m src.main 2>&1 | grep -E "(去重完成|去重后按来源)"
```

**预期输出**:
```
去重完成: 飞书总记录XXX条, 最近14天YYY条, 过滤ZZZ条重复, 保留WWW条新发现
===== 去重后按来源统计 =====
  arxiv          : XX条新发现 / 100条采集 (去重率YY.Y%)
  github         : XX条新发现 / 9条采集 (去重率YY.Y%)
  huggingface    : XX条新发现 / 47条采集 (去重率YY.Y%)
```

**验收标准**:
- `最近14天` 数量应明显小于 `飞书总记录`
- `保留WWW条新发现` 应该 >10（至少有arXiv新论文）
- arXiv去重率应 <70%（之前是100%）

### 测试2: 验证来源多样性

**验收标准**:
- arXiv应有新发现（>5条）
- HuggingFace应有新发现（>0条）
- 推送来源不少于2个

### 测试3: 完整流程验证

**运行命令**:
```bash
.venv/bin/python -m src.main
```

**验收标准**:
- 去重率应显著下降（从99.2%降至<60%）
- 飞书推送应包含arXiv/HuggingFace来源的候选
- 无报错，流程正常完成

---

## 成功标准和检查清单

### 代码修改检查
- [ ] `src/common/constants.py` 新增 `DEDUP_LOOKBACK_DAYS = 14`
- [ ] `src/storage/feishu_storage.py` 新增 `read_existing_records` 方法
- [ ] `src/main.py` 去重逻辑已修改（只对比最近14天）
- [ ] 导入语句已添加（datetime, timedelta, Counter）
- [ ] 代码符合PEP8规范
- [ ] 关键逻辑有中文注释

### 功能验证检查
- [ ] 去重率显著下降（<60%）
- [ ] arXiv有新发现（>5条）
- [ ] HuggingFace有新发现（>0条）
- [ ] 来源统计日志正确输出
- [ ] 飞书推送包含多个来源

### 性能验证检查
- [ ] 飞书API调用次数未增加
- [ ] 去重速度未明显下降（<5秒）
- [ ] 日志输出清晰易读

---

## 边界情况处理

### 情况1: 飞书记录没有发布时间

**场景**: 某些记录的"开源时间"字段为空
**处理**: `publish_date` 设为 `None`，该记录不参与去重
**影响**: 这些记录被视为过时数据，不会阻止新数据入库

### 情况2: 飞书总记录<14天数据量

**场景**: 系统刚启动，历史数据不满14天
**处理**: `recent_records` 数量等于 `existing_records`
**影响**: 正常工作，等价于对比全部历史

### 情况3: 时间格式不一致

**场景**: 发布时间格式可能不是标准ISO 8601
**处理**: 使用 `try-except` 捕获解析错误，记录debug日志
**影响**: 解析失败的记录不参与去重

### 情况4: 时区差异

**场景**: arXiv使用UTC时间，本地可能是其他时区
**处理**: 统一移除时区信息 (`replace(tzinfo=None)`)
**影响**: 可能有±1天的误差，但不影响整体效果

---

## 风险评估与缓解

### 风险1: 可能出现重复入库

**风险**: 超过14天的记录被重新入库
**概率**: 低（这些记录已经很旧，不会被新的采集窗口命中）
**缓解**: 保持采集窗口≤去重窗口（7天采集 < 14天去重）

### 风险2: 飞书API性能

**风险**: 读取完整记录比只读URL慢
**概率**: 低（复用现有 `_read_all_records` 方法）
**缓解**: 已有缓存机制，增量解析时间可忽略

### 风险3: 14天窗口可能不适合所有场景

**风险**: 某些场景需要更长/更短的去重窗口
**概率**: 中
**缓解**: 配置化为常量，方便调整

---

## 后续优化建议

### 优化1: 按来源设置不同的去重窗口

```python
# src/common/constants.py
DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict] = {
    "arxiv": 7,      # arXiv论文更新慢，7天足够
    "github": 30,    # GitHub项目可能有延迟推送
    "huggingface": 14,
    "default": 14,
}
```

### 优化2: 定期清理历史数据

创建脚本 `scripts/cleanup_old_records.py`：
- 删除60天以上的飞书记录
- 减少存储和查询负担

### 优化3: 增加去重缓存

使用Redis缓存最近14天的URL集合，减少飞书API调用。

---

## 参考信息

### 飞书字段名称映射

| 字段用途 | 飞书字段名 | Python属性 |
|---------|-----------|-----------|
| 候选URL | URL | url |
| 发布时间 | 开源时间 | publish_date |

### Python datetime处理示例

```python
from datetime import datetime, timedelta

# 计算14天前的日期
cutoff = datetime.now() - timedelta(days=14)

# 解析ISO 8601时间
dt = datetime.fromisoformat("2025-11-22T10:30:45+00:00")

# 移除时区信息
dt_naive = dt.replace(tzinfo=None)

# 比较日期
if dt_naive >= cutoff:
    print("在14天内")
```

---

**文档结束**
