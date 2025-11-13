# BenchScope - Codex开发指令文档

**目标受众**: Codex AI开发代理
**项目状态**: 设计完成(PRD 93/100, 架构 94/100) → 准备实施
**开发模式**: BMAD工作流 - Dev阶段
**预计工期**: MVP 2周

---

## 项目背景

你即将开发**BenchScope** - 一个Benchmark情报自动化系统。

**核心价值**:
- 研究员当前手动筛选200+篇论文/月,耗时16小时
- 系统自动化后:每日采集 → 智能评分 → 推送Top候选
- ROI: 节省¥12,750/周人力成本

**技术栈**:
- Python 3.11+ (异步编程)
- LangChain + OpenAI gpt-4o-mini (智能评分)
- 飞书开放平台 (存储+通知)
- GitHub Actions (定时调度)
- Redis (LLM缓存)
- SQLite (降级备份)

---

## 开发任务

### Phase 1 - MVP实施 (当前任务,2周)

你需要实现以下模块:

#### 1. 数据采集层 (`src/collectors/`)

**ArxivCollector** (`arxiv_collector.py`):
- 使用`arxiv`库搜索最近24小时论文
- 关键词: benchmark, agent evaluation, code generation, web automation
- 分类过滤: cs.AI, cs.CL, cs.SE
- 超时控制: 10秒,3次重试
- 输出: `List[RawCandidate]`

**GitHubCollector** (`github_collector.py`):
- 爬取GitHub Trending页面
- 话题: benchmark, evaluation, agent
- 过滤: stars ≥ 100
- BeautifulSoup解析,超时5秒
- 输出: `List[RawCandidate]`

**PwCCollector** (`pwc_collector.py`):
- Papers with Code API集成
- 任务领域: coding, agent, reasoning
- 最少3篇论文的任务才考虑
- 超时15秒
- 输出: `List[RawCandidate]`

**关键要求**:
- 所有采集器必须实现`async def collect() -> List[RawCandidate]`
- 失败返回空列表,**不抛异常**(容忍部分失败)
- 使用`asyncio.gather(return_exceptions=True)`并发采集

#### 2. 预处理层 (`src/prefilter/`)

**RuleBasedPrefilter** (`rule_filter.py`):
- 过滤低质量数据(目标:50%过滤率)
- 去重:标题相似度>0.9或URL重复
- 规则:
  - 拒绝star<50的GitHub仓库
  - 拒绝无摘要的arXiv论文
  - 拒绝标题含"survey"但无代码的论文
- 输出: `List[RawCandidate]`

#### 3. 智能评分层 (`src/scorer/`)

**LLMScorer** (`llm_scorer.py`):
- 模型: gpt-4o-mini
- 评分维度(每个0-10分):
  - 创新性 (Innovation)
  - 技术深度 (Technical Depth)
  - 影响力 (Impact)
  - 数据质量 (Data Quality)
  - 可复现性 (Reproducibility)
- Redis缓存: 7天TTL,key=`score:md5(title)`
- 超时30秒,失败fallback到规则评分
- 返回JSON格式,解析为`BenchmarkScore`

**RuleScorer** (`rule_scorer.py`):
- 兜底评分逻辑(LLM失败时使用)
- 基于GitHub stars粗略估算:
  - stars≥1000 → 8分
  - stars≥500 → 6分
  - stars≥100 → 4分
  - 其他 → 2分

#### 4. 存储层 (`src/storage/`)

**FeishuStorage** (`feishu_storage.py`):
- 飞书多维表格批量写入
- API: `POST /bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create`
- 批量大小: 20条/请求
- 字段映射:
  ```python
  {
      "标题": title,
      "来源": source,
      "URL": url,
      "摘要": abstract,
      "创新性": score.innovation,
      "技术深度": score.technical_depth,
      "影响力": score.impact,
      "数据质量": score.data_quality,
      "可复现性": score.reproducibility,
      "总分": score.total_score,
      "优先级": score.priority,  # high/medium/low
      "状态": "待审阅",
      "发现时间": datetime.now().isoformat(),
      "GitHub Stars": github_stars or 0,
      "GitHub URL": github_url or "",
      "数据集URL": dataset_url or ""
  }
  ```
- 限流: 100请求/分钟,批次间等待0.6秒
- 认证: tenant_access_token,2小时有效期,提前5分钟刷新

**SQLiteFallback** (`sqlite_fallback.py`):
- 表结构:
  ```sql
  CREATE TABLE fallback_candidates (
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      source TEXT NOT NULL,
      url TEXT UNIQUE NOT NULL,
      score_json TEXT NOT NULL,
      raw_json TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      synced_to_feishu BOOLEAN DEFAULT 0
  )
  ```
- 功能:
  - `save()`: 写入SQLite
  - `get_unsynced()`: 获取未同步记录
  - `mark_synced()`: 标记已同步
  - `cleanup_old_records(days=7)`: 清理旧数据

**StorageManager** (`storage_manager.py`):
- 统一存储接口
- 逻辑:
  1. 尝试写入飞书
  2. 成功 → 清理7天前SQLite备份 + 同步未同步记录
  3. 失败 → 降级到SQLite + 发送告警

#### 5. 通知层 (`src/notifier/`)

**FeishuNotifier** (`feishu_notifier.py`):
- MVP: 简单文本消息(Webhook推送)
- 内容:
  ```
  📊 BenchScope日报 - {date}

  本次发现 {count} 个高质量Benchmark候选

  🔥 Top 5推荐:
  1. {title} - 总分{score} ({priority})
     {url}
  2. ...

  查看详情: {飞书多维表格链接}
  ```
- Phase 2: 卡片消息+一键添加按钮(暂不实现)

#### 6. 编排器 (`src/main.py`)

**主流程**:
```python
async def run_daily_collection():
    # Step 1: 并发采集
    collectors = [ArxivCollector(), GitHubCollector(), PwCCollector()]
    results = await asyncio.gather(*[c.collect() for c in collectors], return_exceptions=True)

    # 合并结果,跳过失败
    all_candidates = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"采集失败: {r}")
        else:
            all_candidates.extend(r)

    # Step 2: 预筛选
    prefilter = RuleBasedPrefilter()
    filtered = prefilter.filter(all_candidates)

    # Step 3: LLM评分(串行,MVP不并发)
    scorer = LLMScorer()
    scored_candidates = []
    for c in filtered:
        try:
            score = await scorer.score(c)
            scored_candidates.append(ScoredCandidate(raw=c, score=score))
        except Exception as e:
            logger.error(f"评分失败: {e}")

    # Step 4: 存储
    storage = StorageManager()
    await storage.save(scored_candidates)

    # Step 5: 通知
    top5 = sorted(scored_candidates, key=lambda x: x.score.total_score, reverse=True)[:5]
    notifier = FeishuNotifier()
    await notifier.notify(top5)

    logger.info(f"流程完成,处理{len(scored_candidates)}条候选")
```

#### 7. 数据模型 (`src/models.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class RawCandidate:
    title: str
    url: str
    source: str  # 'arxiv' | 'github' | 'pwc'
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    dataset_url: Optional[str] = None
    raw_metadata: dict = None

@dataclass
class BenchmarkScore:
    innovation: int        # 0-10
    technical_depth: int   # 0-10
    impact: int           # 0-10
    data_quality: int     # 0-10
    reproducibility: int  # 0-10

    @property
    def total_score(self) -> int:
        return sum([self.innovation, self.technical_depth, self.impact,
                   self.data_quality, self.reproducibility])

    @property
    def priority(self) -> str:
        if self.total_score >= 40:
            return "high"
        elif self.total_score >= 30:
            return "medium"
        else:
            return "low"

@dataclass
class ScoredCandidate:
    raw: RawCandidate
    score: BenchmarkScore
    filter_reason: Optional[str] = None
```

#### 8. 配置管理 (`src/config.py`)

```python
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

    # 飞书
    FEISHU_APP_ID = os.getenv('FEISHU_APP_ID')
    FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET')
    FEISHU_BITABLE_APP_TOKEN = os.getenv('FEISHU_BITABLE_APP_TOKEN')
    FEISHU_BITABLE_TABLE_ID = os.getenv('FEISHU_BITABLE_TABLE_ID')
    FEISHU_WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK_URL')

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

    # 日志
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = os.getenv('LOG_DIR', 'logs/')

    # 验证必需配置
    @classmethod
    def validate(cls):
        required = ['OPENAI_API_KEY', 'FEISHU_APP_ID', 'FEISHU_APP_SECRET']
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"缺少必需配置: {missing}")
```

#### 9. GitHub Actions (`github/workflows/daily_collect.yml`)

```yaml
name: BenchScope Daily Collection

on:
  schedule:
    - cron: '0 2 * * *'  # UTC 2:00 (北京10:00)
  workflow_dispatch:

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Run Collection
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
          FEISHU_BITABLE_TABLE_ID: ${{ secrets.FEISHU_BITABLE_TABLE_ID }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          REDIS_URL: redis://localhost:6379
        run: python src/main.py

      - name: Upload Logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: logs
          path: logs/
          retention-days: 7
```

---

## 代码规范

### Python风格 (强制执行)

1. **PEP8合规**:
   - 4空格缩进
   - 函数/变量: `snake_case`
   - 类名: `PascalCase`
   - 常量: `UPPER_SNAKE_CASE`
   - 最大行长: 100字符

2. **类型注解**:
   ```python
   async def collect(self) -> List[RawCandidate]:
       ...

   def filter(self, candidates: List[RawCandidate]) -> List[RawCandidate]:
       ...
   ```

3. **中文注释**:
   - 关键逻辑必须写中文注释
   - 复杂算法解释WHY,不仅是WHAT
   ```python
   # 关键词质量过滤:拒绝URL片段、HTML/CSS代码、技术术语
   # 这个函数影响所有下游分析,修改需要全面测试
   def is_quality_keyword(keyword: str) -> bool:
       ...
   ```

4. **Docstrings**:
   ```python
   async def score(self, candidate: RawCandidate) -> BenchmarkScore:
       """
       为候选Benchmark打分

       Args:
           candidate: 待评分的候选

       Returns:
           5维度评分结果

       Raises:
           TimeoutError: LLM调用超时
           OpenAIError: API调用失败
       """
   ```

5. **嵌套层级**:
   - 最大3层(Linus规则)
   - 超过3层必须重构,使用early return

   ```python
   # ❌ Bad (4层嵌套)
   def process(data):
       if data:
           if data.valid:
               if data.score > 0:
                   if data.approved:
                       return result

   # ✅ Good (early return)
   def process(data):
       if not data:
           return None
       if not data.valid:
           return None
       if data.score <= 0:
           return None
       if not data.approved:
           return None
       return result
   ```

6. **魔法数字**:
   - 定义在`src/common/constants.py`
   ```python
   # constants.py
   ARXIV_TIMEOUT = 10
   ARXIV_MAX_RETRIES = 3
   GITHUB_MIN_STARS = 100
   FEISHU_BATCH_SIZE = 20
   SCORE_THRESHOLD = 6.0
   CACHE_TTL_DAYS = 7
   ```

### 异步编程模式

1. **使用async/await**:
   ```python
   # ✅ 正确
   async def fetch_data():
       async with httpx.AsyncClient() as client:
           resp = await client.get(url)
           return resp.json()

   # ❌ 错误:阻塞主线程
   def fetch_data():
       resp = requests.get(url)  # 同步调用
       return resp.json()
   ```

2. **超时控制**:
   ```python
   async with asyncio.timeout(10):
       result = await long_running_task()
   ```

3. **并发限流**:
   ```python
   # 限制并发度为5
   semaphore = asyncio.Semaphore(5)

   async def score_with_limit(candidate):
       async with semaphore:
           return await scorer.score(candidate)

   scores = await asyncio.gather(*[score_with_limit(c) for c in candidates])
   ```

### 错误处理

1. **采集器容错**:
   ```python
   # 失败返回空列表,不抛异常
   async def collect(self) -> List[RawCandidate]:
       try:
           results = await self._fetch_data()
           return results
       except Exception as e:
           logger.error(f"采集失败: {e}")
           return []  # 不抛异常
   ```

2. **重试策略**:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(
       stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=1, max=10)
   )
   async def call_api():
       ...
   ```

3. **降级策略**:
   ```python
   try:
       score = await llm_scorer.score(candidate)
   except Exception as e:
       logger.error(f"LLM评分失败,fallback到规则: {e}")
       score = rule_scorer.score(candidate)
   ```

### 日志规范

```python
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('BenchScope')

# 使用示例
logger.info(f"采集arXiv: 发现{count}篇新论文")
logger.warning(f"GitHub API限流,等待{retry_after}秒")
logger.error(f"Notion写入失败: {error}")
```

---

## 测试要求

### 单元测试

每个模块必须有对应测试:

```python
# tests/unit/test_scorer.py

import pytest
from src.scorer.llm_scorer import LLMScorer
from src.models import RawCandidate

@pytest.mark.asyncio
async def test_llm_scorer_basic():
    scorer = LLMScorer()

    candidate = RawCandidate(
        title="TestBench: A Benchmark for Testing",
        url="https://arxiv.org/abs/2024.00000",
        source="arxiv",
        abstract="A new benchmark...",
        github_stars=500
    )

    score = await scorer.score(candidate)

    assert 0 <= score.innovation <= 10
    assert 0 <= score.total_score <= 50
    assert score.priority in ['high', 'medium', 'low']
```

### 手动测试清单

MVP阶段必须手动验证:

- [ ] arXiv采集返回结果
- [ ] GitHub Trending爬取成功
- [ ] LLM评分返回合理分数
- [ ] 飞书多维表格写入成功
- [ ] 飞书通知推送成功
- [ ] SQLite降级备份正常
- [ ] GitHub Actions定时任务触发

**测试报告要求**:
- 记录测试时间、环境
- 附截图或日志
- 保存到`docs/test-report.md`

---

## 依赖清单

```txt
# requirements.txt

python>=3.11

# HTTP
httpx>=0.25.0
requests>=2.31.0

# 数据采集
arxiv>=2.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# LLM
openai>=1.3.0
langchain>=0.1.0
langchain-openai>=0.0.2

# 缓存
redis>=5.0.0

# 飞书
lark-oapi>=1.2.0

# 工具
python-dotenv>=1.0.0
pydantic>=2.5.0
tenacity>=8.2.0

# 测试
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
```

---

## 开发流程

### 1. 环境准备

```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env.local
# 编辑.env.local,填入真实API密钥
```

### 2. 实施顺序

**建议按此顺序开发**:

1. **数据模型** (`models.py`) - 基础
2. **配置管理** (`config.py`) - 基础
3. **采集器** (`collectors/`) - 核心功能
   - 先实现ArxivCollector(最重要)
   - 再实现GitHubCollector和PwCCollector
4. **预筛选** (`prefilter/rule_filter.py`) - 减少LLM成本
5. **评分器** (`scorer/`) - 核心功能
   - 先实现RuleScorer(简单)
   - 再实现LLMScorer(复杂)
6. **存储层** (`storage/`) - 核心功能
   - 先实现SQLiteFallback(简单)
   - 再实现FeishuStorage(复杂)
   - 最后StorageManager(组合)
7. **通知** (`notifier/feishu_notifier.py`) - 简单
8. **编排器** (`main.py`) - 串联所有模块
9. **GitHub Actions** (`.github/workflows/`) - 自动化

### 3. 测试策略

每完成一个模块:
1. 编写单元测试
2. 本地手动测试
3. 记录测试结果到`docs/test-report.md`

### 4. 提交规范

```bash
# Conventional Commits格式
git commit -m "feat(collector): add arxiv collector with rate limiting"
git commit -m "fix(scorer): correct cache key generation"
git commit -m "docs: add testing guide for MVP"

# ❌ 禁止
# - 不要添加emoji
# - 不要添加"Generated with Claude Code"
# - 不要添加"Co-Authored-By: Claude"
```

---

## 验收标准

MVP完成后,必须满足:

### 功能验收

- [ ] GitHub Actions每日UTC 2:00自动运行
- [ ] arXiv/GitHub/PwC三个数据源全部可用
- [ ] 预筛选过滤率达到40-60%
- [ ] LLM评分成功率 > 90%
- [ ] 飞书多维表格自动写入
- [ ] 飞书通知每日推送
- [ ] SQLite降级备份可用
- [ ] 日志完整记录到logs/

### 性能验收

- [ ] 总执行时间 < 20分钟
- [ ] LLM月成本 < ¥50
- [ ] 数据采集成功率 > 95%

### 质量验收

- [ ] 所有代码通过`black`格式化
- [ ] 所有代码通过`ruff check`
- [ ] 关键逻辑有中文注释
- [ ] 核心模块有单元测试
- [ ] 手动测试报告完整

---

## 关键约束

1. **SEO模块约束**:
   - 仓库中存在`analyzer.py:12-89`的`is_quality_keyword()`函数
   - **禁止修改**此函数
   - 如确需变更,必须先提Issue

2. **手动测试强制执行**:
   - 飞书播报、飞书多维表格、外部API必须手动验证
   - 结果记录到`docs/test-report.md`并附截图

3. **评分逻辑变更流程**:
   - 修改`scorer.py`前需提供最小可复现脚本
   - 提供样例输入和预期输出
   - PR附变更前后对比

4. **不要过度工程**:
   - 不需要Airflow(GitHub Actions足够)
   - 不需要向量数据库(Numpy足够)
   - 不需要PostgreSQL(飞书多维表格足够)
   - MVP串行采集(5分钟<<20分钟,够用)

---

## 参考文档

已完成的设计文档位于`.claude/specs/benchmark-intelligence-agent/`:

1. **00-repo-scan.md** - 仓库分析(已完成)
2. **01-product-requirements.md** - PRD (93/100质量)
   - 包含14个用户故事
   - 完整的验收标准
   - ROI分析
3. **02-system-architecture.md** - 架构设计 (94/100质量)
   - 5层架构详解
   - 完整的代码示例
   - 错误处理策略
   - 性能与成本分析

**重要**: 实施时优先参考架构文档中的代码示例,它们已经过设计验证。

---

## 成功指标

3个月后,系统应达成:

- **Benchmark发现速度**: 从2-3个/月 → 10-20个/月
- **信息筛选效率**: 噪音过滤率90%+
- **入库响应时间**: 发现后1-3天(自动播报延迟<24h)
- **候选池质量**: 入库后实际使用率>50%

---

## 开始开发

**你的任务**:
1. 严格按照上述规范实施MVP
2. 优先参考`02-system-architecture.md`中的代码示例
3. 遵循代码规范和测试要求
4. 完成后更新`.claude/CLAUDE.md`记录关键决策

**关键原则** (Linus哲学):
1. **Is this a real problem?** → 只解决真实问题,拒绝过度工程
2. **Is there a simpler way?** → 永远寻找最简单的实现
3. **What will this break?** → MVP零破坏(纯新项目)

Good luck! 开始编码吧。
