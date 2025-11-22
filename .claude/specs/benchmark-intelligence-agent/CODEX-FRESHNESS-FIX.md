# Codex开发指令文档：修复Benchmark新鲜度问题

## 文档元信息
- **创建时间**: 2025-11-22
- **创建者**: Claude Code
- **执行者**: Codex
- **优先级**: P0 (紧急)
- **预计工作量**: 2小时

---

## 问题诊断

### 用户反馈
用户报告采集到的benchmark都不够新，如swebench/uitars/camel等都是旧项目。

### 根本原因分析

**问题1：GitHub采集器使用错误的时间字段**

当前代码 (`src/collectors/github_collector.py:118-126`):
```python
lookback_date = (
    datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
).strftime("%Y-%m-%d")
params = {
    "q": f"{topic} benchmark in:name,description,readme pushed:>={lookback_date}",  # ← 使用 pushed
    "sort": "stars",
    "order": "desc",
    "per_page": self.per_page,
}
```

**错误**：
- `pushed:>=` 表示"最后push时间"，不是"首次发布时间"
- swebench (2023年发布) 如果2025年11月有新commit，就会被采集
- 用户想要："新发布的benchmark"
- 实际采集："最近有更新的benchmark"（包括老项目的小更新）

**影响范围**：
- GitHub采集器采集到大量老项目（只要最近有commit）
- 飞书表格充斥着用户已知的旧benchmark
- 降低系统价值和用户信任度

**问题2：时间窗口过长**

当前配置 (`config/sources.yaml`):
```yaml
arxiv:
  lookback_hours: 720  # 30天窗口

github:
  lookback_days: 30  # 30天窗口

huggingface:
  lookback_days: 14  # 14天窗口
```

30天窗口对于"发现新benchmark"场景过长，导致：
- arXiv采集到30天内所有论文（包括非首发、更新版本）
- GitHub采集到30天内所有有commit的项目

---

## 解决方案设计

### 核心策略：区分"新项目"和"活跃老项目"

**设计哲学** (Linus原则):
1. **Is this a real problem?** ✅ 是真实问题，用户反馈明确
2. **Is there a simpler way?** ✅ 用 `created:>=` 替代 `pushed:>=`
3. **What will this break?** ✅ 零破坏（纯优化查询逻辑）

### 三层防御机制

#### 第1层：GitHub查询优化（改用 `created:>=`）

**修改前**:
```python
params = {
    "q": f"{topic} benchmark in:name,description,readme pushed:>={lookback_date}",
}
```

**修改后**:
```python
params = {
    "q": f"{topic} benchmark in:name,description,readme created:>={lookback_date}",
}
```

**效果**：
- ✅ 只采集"最近创建的新仓库"
- ✅ 过滤掉老项目的小更新（如README typo修复）
- ❌ 可能错过老项目的重大更新（如新dataset发布）

**权衡**：接受错过老项目重大更新的风险，优先保证新鲜度

#### 第2层：缩短时间窗口

**修改 `config/sources.yaml`**:
```yaml
arxiv:
  lookback_hours: 336  # 30天 → 14天 (14*24=336)

github:
  lookback_days: 14  # 30天 → 14天

huggingface:
  lookback_days: 14  # 保持14天
```

**理由**：
- 14天足够覆盖大部分新benchmark发布
- 减少噪音和重复数据
- 提升数据新鲜度

#### 第3层：记录 `created_at` 字段（可选，用于后续优化）

**新增字段到 `RawCandidate`**:
```python
@dataclass
class RawCandidate:
    # ... 现有字段 ...
    created_at: Optional[datetime] = None  # 项目首次创建时间（仅GitHub）
```

**提取逻辑** (`src/collectors/github_collector.py`):
```python
return RawCandidate(
    # ... 现有字段 ...
    created_at=self._parse_datetime(repo.get("created_at")),  # 新增
    publish_date=self._parse_datetime(repo.get("pushed_at")),  # 保持现有
)
```

**用途**：
- 飞书表格显示"项目年龄"，辅助人工判断
- 预筛选阶段可加规则：创建时间>6个月的项目降低优先级
- 日志分析：统计采集到的项目年龄分布

---

## 实施步骤

### Step 1: 修改GitHub采集器查询逻辑

**文件**: `src/collectors/github_collector.py`

**修改位置**: 第118-126行

**当前代码**:
```python
async def _fetch_topic(
    self, client: httpx.AsyncClient, topic: str
) -> List[RawCandidate]:
    """调用GitHub搜索API"""

    lookback_date = (
        datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
    ).strftime("%Y-%m-%d")
    params = {
        "q": f"{topic} benchmark in:name,description,readme pushed:>={lookback_date}",
        "sort": "stars",
        "order": "desc",
        "per_page": self.per_page,
    }
    resp = await self._request_with_retry(client, params, topic)
    # ...
```

**修改后代码**:
```python
async def _fetch_topic(
    self, client: httpx.AsyncClient, topic: str
) -> List[RawCandidate]:
    """调用GitHub搜索API"""

    lookback_date = (
        datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
    ).strftime("%Y-%m-%d")
    params = {
        "q": f"{topic} benchmark in:name,description,readme created:>={lookback_date}",  # pushed → created
        "sort": "stars",
        "order": "desc",
        "per_page": self.per_page,
    }
    resp = await self._request_with_retry(client, params, topic)
    # ...
```

**关键修改**:
- 第122行: `pushed:>=` → `created:>=`
- 只改一个单词，影响巨大！

---

### Step 2: 增加 `created_at` 字段记录（可选）

**文件1**: `src/models.py`

**修改位置**: `RawCandidate` 类定义

**当前代码** (约第30-60行):
```python
@dataclass
class RawCandidate:
    title: str
    url: str
    source: str
    abstract: Optional[str] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    publish_date: Optional[datetime] = None
    # ... 其他字段 ...
```

**修改后代码**:
```python
@dataclass
class RawCandidate:
    title: str
    url: str
    source: str
    abstract: Optional[str] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    publish_date: Optional[datetime] = None
    created_at: Optional[datetime] = None  # 新增：项目首次创建时间（仅GitHub）
    # ... 其他字段 ...
```

**文件2**: `src/collectors/github_collector.py`

**修改位置**: `_build_candidate` 方法的 `return RawCandidate(...)` 部分

**当前代码** (约第220-239行):
```python
return RawCandidate(
    title=repo.get("full_name", ""),
    url=repo.get("html_url", ""),
    source="github",
    abstract=cleaned_abstract,
    github_stars=stars,
    github_url=repo.get("html_url"),
    publish_date=self._parse_datetime(repo.get("pushed_at")),
    license_type=license_type,
    task_type=task_type,
    dataset_url=dataset_url,
    raw_metrics=readme_meta.metrics or None,
    raw_baselines=readme_meta.baselines or None,
    raw_dataset_size=readme_meta.dataset_size,
    raw_metadata={
        "topic": topic,
        "language": str(repo.get("language") or ""),
    },
    hero_image_url=hero_image_url,
)
```

**修改后代码**:
```python
return RawCandidate(
    title=repo.get("full_name", ""),
    url=repo.get("html_url", ""),
    source="github",
    abstract=cleaned_abstract,
    github_stars=stars,
    github_url=repo.get("html_url"),
    publish_date=self._parse_datetime(repo.get("pushed_at")),  # 保持：最后更新时间
    created_at=self._parse_datetime(repo.get("created_at")),  # 新增：首次创建时间
    license_type=license_type,
    task_type=task_type,
    dataset_url=dataset_url,
    raw_metrics=readme_meta.metrics or None,
    raw_baselines=readme_meta.baselines or None,
    raw_dataset_size=readme_meta.dataset_size,
    raw_metadata={
        "topic": topic,
        "language": str(repo.get("language") or ""),
    },
    hero_image_url=hero_image_url,
)
```

---

### Step 3: 缩短时间窗口配置

**文件**: `config/sources.yaml`

**修改位置**: 第11行、第191行

**当前代码**:
```yaml
arxiv:
  enabled: true
  max_results: 100
  lookback_hours: 720  # 30天窗口
  timeout_seconds: 20
  max_retries: 2

github:
  enabled: true
  # ... 其他配置 ...
  min_stars: 50
  lookback_days: 30  # 30天窗口
  timeout_seconds: 5
```

**修改后代码**:
```yaml
arxiv:
  enabled: true
  max_results: 100
  lookback_hours: 336  # 14天窗口 (14*24=336)
  timeout_seconds: 20
  max_retries: 2

github:
  enabled: true
  # ... 其他配置 ...
  min_stars: 50
  lookback_days: 14  # 14天窗口
  timeout_seconds: 5
```

**关键修改**:
- arXiv: `lookback_hours: 720` → `336` (30天→14天)
- GitHub: `lookback_days: 30` → `14`

---

### Step 4: 更新飞书表格字段（可选，如果实现了Step 2）

**文件**: `scripts/create_feishu_fields.py`

**新增字段定义**:
```python
{
    "field_name": "项目年龄",
    "type": 5,  # DateTime类型
    "property": {
        "formatter": "yyyy/MM/dd",
        "auto_fill": False,
    },
}
```

**文件**: `src/storage/feishu_storage.py`

**修改 `_candidate_to_feishu_record` 方法**:

**当前代码** (约第200-250行):
```python
def _candidate_to_feishu_record(self, candidate: ScoredCandidate) -> dict[str, Any]:
    """将ScoredCandidate转换为飞书API所需格式"""
    return {
        "标题": candidate.title,
        "URL": candidate.url,
        # ... 其他字段 ...
        "开源时间": self._format_datetime(candidate.publish_date),
    }
```

**修改后代码**:
```python
def _candidate_to_feishu_record(self, candidate: ScoredCandidate) -> dict[str, Any]:
    """将ScoredCandidate转换为飞书API所需格式"""
    return {
        "标题": candidate.title,
        "URL": candidate.url,
        # ... 其他字段 ...
        "开源时间": self._format_datetime(candidate.publish_date),
        "项目年龄": self._format_datetime(candidate.created_at) if candidate.created_at else None,  # 新增
    }
```

---

## 测试验证计划

### 测试1: GitHub查询结果对比

**步骤**:
1. 修改前运行一次GitHub采集，记录结果
2. 修改后运行一次GitHub采集，记录结果
3. 对比两次结果的"项目创建时间"分布

**预期结果**:
- 修改前：包含2023年、2024年创建的老项目
- 修改后：只包含最近14天创建的新项目

**验证命令**:
```bash
# 运行采集并查看日志
.venv/bin/python -m src.main

# 分析日志中的GitHub采集结果
tail -100 logs/benchscope.log | grep -A 5 "GitHubCollector"
```

### 测试2: 手动验证采集到的项目

**步骤**:
1. 从日志或飞书表格中随机抽取5个GitHub项目
2. 访问项目页面，查看"Created on"时间戳
3. 验证是否在最近14天内创建

**验证方法**:
```bash
# 假设采集到 owner/repo
# 访问: https://github.com/owner/repo
# 查看右侧信息栏的 "Created" 时间
```

### 测试3: 完整流程验证

**步骤**:
1. 运行完整采集流程
2. 检查飞书表格中的新记录
3. 验证是否都是最近14天内发布的benchmark

**成功标准**:
- ✅ 飞书表格中无swebench/uitars/camel等2023年发布的老项目
- ✅ 所有GitHub项目的创建时间都在最近14天内
- ✅ arXiv论文的发布时间都在最近14天内
- ✅ 数据量合理（预计5-15条/天，而不是几十条）

---

## 成功标准和检查清单

### 代码修改检查
- [ ] `src/collectors/github_collector.py:122` 已将 `pushed:>=` 改为 `created:>=`
- [ ] `config/sources.yaml` 已将时间窗口缩短到14天
- [ ] （可选）`src/models.py` 新增 `created_at` 字段
- [ ] （可选）`src/collectors/github_collector.py` 提取 `created_at` 字段
- [ ] （可选）`src/storage/feishu_storage.py` 映射 `created_at` 到飞书字段

### 功能验证检查
- [ ] 运行完整流程无错误
- [ ] GitHub采集结果都是最近14天创建的项目
- [ ] arXiv采集结果都是最近14天发布的论文
- [ ] 飞书表格中无老项目（创建时间>6个月）
- [ ] 日志显示采集数量合理（不是0，也不是100+）

### 质量验证检查
- [ ] 代码符合PEP8规范
- [ ] 关键修改处有中文注释
- [ ] 无魔法数字（14天配置在YAML中）
- [ ] 无破坏性修改（现有功能正常）
- [ ] Git commit message符合规范

---

## 风险评估与缓解

### 风险1：采集数量锐减

**风险**：改用 `created:>=` 后，GitHub采集数量可能从30-50条降至5-10条

**影响**：用户可能觉得系统"不够用"

**缓解措施**：
1. 这是预期行为：新鲜度 > 数量
2. 如果数量过少（<3条/天），可考虑：
   - 增加topic数量（扩展关键词）
   - 适当延长时间窗口至21天
   - 增加采集频率（每日2次）

### 风险2：错过重大benchmark更新

**风险**：老项目发布新dataset或重大版本更新，可能被漏掉

**影响**：错过有价值的更新

**缓解措施**：
1. 依赖arXiv/HuggingFace采集器（通常重大更新会发新论文/新dataset）
2. 未来可增加"GitHub Release监控"（Phase 6+）
3. 用户可手动添加重要更新到飞书表格

### 风险3：created_at字段缺失

**风险**：GitHub API返回的 `created_at` 可能为空

**影响**：新增字段可能无数据

**缓解措施**：
1. `created_at` 字段设为 `Optional[datetime] = None`
2. 飞书映射时检查 `if candidate.created_at else None`
3. 实测GitHub API通常都有 `created_at`，风险极低

---

## 后续优化建议

### 优化1: 动态时间窗口

根据采集结果动态调整时间窗口：
- 如果14天内采集<5条 → 自动延长至21天
- 如果14天内采集>50条 → 自动缩短至7天

**实现**: 在 `config/sources.yaml` 增加 `adaptive_window` 配置

### 优化2: 混合查询策略

同时查询"新项目"和"活跃新项目"：
- 查询1: `created:>={14天前}` (新项目)
- 查询2: `pushed:>={14天前} AND created:>={6个月前}` (活跃新项目)
- 合并去重

**实现**: 修改 `_fetch_topic` 方法，执行两次查询

### 优化3: 项目年龄分析

在日志分析工具中增加"项目年龄分布"统计：
```python
# scripts/analyze_logs.py
def analyze_project_age_distribution():
    """统计采集到的项目年龄分布"""
    # 0-1个月: XX%
    # 1-3个月: XX%
    # 3-6个月: XX%
    # 6个月+: XX%
```

---

## 参考资料

### GitHub Search API文档
- [GitHub Search Syntax](https://docs.github.com/en/search-github/getting-started-with-searching-on-github/understanding-the-search-syntax)
- `created:>=YYYY-MM-DD` - 仓库创建时间
- `pushed:>=YYYY-MM-DD` - 最后push时间

### 相关Issue/讨论
- 用户反馈: "swebench/uitars/camel都不是新的开源工作"
- 期望: 采集"最近发布的新benchmark"，而不是"最近有更新的老项目"

---

## 附录：完整代码对比

### A. GitHub采集器查询逻辑对比

**修改前** (`src/collectors/github_collector.py:118-126`):
```python
async def _fetch_topic(
    self, client: httpx.AsyncClient, topic: str
) -> List[RawCandidate]:
    """调用GitHub搜索API"""

    lookback_date = (
        datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
    ).strftime("%Y-%m-%d")
    params = {
        "q": f"{topic} benchmark in:name,description,readme pushed:>={lookback_date}",  # ← 使用pushed
        "sort": "stars",
        "order": "desc",
        "per_page": self.per_page,
    }
    resp = await self._request_with_retry(client, params, topic)
    # ... 后续处理 ...
```

**修改后**:
```python
async def _fetch_topic(
    self, client: httpx.AsyncClient, topic: str
) -> List[RawCandidate]:
    """调用GitHub搜索API - 只查询最近创建的新仓库"""

    lookback_date = (
        datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
    ).strftime("%Y-%m-%d")
    params = {
        "q": f"{topic} benchmark in:name,description,readme created:>={lookback_date}",  # ← 改用created
        "sort": "stars",
        "order": "desc",
        "per_page": self.per_page,
    }
    resp = await self._request_with_retry(client, params, topic)
    # ... 后续处理 ...
```

**关键差异**:
- Line 122: `pushed:>=` → `created:>=`
- 注释更新：强调"只查询最近创建的新仓库"

---

## 结语

这个修复方案遵循Linus哲学：
1. ✅ **解决真实问题**：用户明确反馈采集到的都是老项目
2. ✅ **最简单方案**：只改一个单词 `pushed → created`
3. ✅ **零破坏**：不影响现有功能，纯优化查询逻辑

预期效果：
- 飞书表格中将全部是"最近14天新发布"的benchmark
- 用户不再看到swebench/uitars/camel等2023年的老项目
- 系统价值和用户信任度显著提升

---

**文档结束**
