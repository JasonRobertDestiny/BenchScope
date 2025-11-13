# BenchScope MVP开发任务 - Codex执行指令

你是一个专业的Python开发工程师，现在需要开发**BenchScope** - 一个Benchmark情报自动化系统。

---

## 项目上下文

### 业务背景
- **问题**: 研究团队手动筛选AI/Agent领域Benchmark，每月阅读200+篇论文，耗时16小时
- **方案**: 自动化系统每日采集、智能评分、推送高质量候选
- **ROI**: 节省¥12,750/周人力成本，Benchmark发现速度从2-3个/月提升到10-20个/月

### 技术栈
- **语言**: Python 3.11+
- **异步框架**: asyncio + httpx
- **LLM**: OpenAI gpt-4o-mini (成本优化: ¥1/月)
- **缓存**: Redis (7天TTL, 30%命中率)
- **存储**: 飞书多维表格(主) + SQLite(降级备份)
- **调度**: GitHub Actions (每日UTC 2:00)
- **通知**: 飞书Webhook

### 架构设计(已完成,94/100质量)
```
GitHub Actions Cron
  ↓
main.py 编排器
  ↓
并发采集 (asyncio.gather)
  ├─ ArxivCollector (10s timeout, 3 retries)
  ├─ GitHubCollector (5s timeout)
  └─ PwCCollector (15s timeout)
  ↓
规则预筛选 (过滤50%噪音)
  ↓
LLM评分 (gpt-4o-mini + Redis缓存7天)
  ├─ 5维度: 创新性/技术深度/影响力/数据质量/可复现性
  └─ Fallback: 规则评分
  ↓
存储管理器
  ├─ Primary: 飞书多维表格 (批量写入20条/请求)
  └─ Fallback: SQLite (7天自动同步)
  ↓
飞书通知 (Webhook推送Top 5)
```

---

## 已完成设计文档

你可以在以下位置查阅完整设计:

1. **`.claude/specs/benchmark-intelligence-agent/01-product-requirements.md`**
   - 93/100质量分
   - 14个用户故事，完整验收标准

2. **`.claude/specs/benchmark-intelligence-agent/02-system-architecture.md`**
   - 94/100质量分
   - 完整代码示例、错误处理策略、性能分析

3. **`.claude/specs/benchmark-intelligence-agent/CODEX-DEVELOPMENT-BRIEF.md`**
   - MVP实施清单
   - 代码规范、测试要求

---

## MVP开发任务清单

### 目录结构
```
BenchScope/
├── src/
│   ├── models.py                    # 数据模型
│   ├── config.py                    # 配置管理
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── arxiv_collector.py       # arXiv采集器
│   │   ├── github_collector.py      # GitHub Trending采集器
│   │   └── pwc_collector.py         # Papers with Code采集器
│   ├── prefilter/
│   │   ├── __init__.py
│   │   └── rule_filter.py           # 规则预筛选
│   ├── scorer/
│   │   ├── __init__.py
│   │   ├── llm_scorer.py            # LLM评分器
│   │   └── rule_scorer.py           # 规则评分器
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── feishu_storage.py        # 飞书存储
│   │   ├── sqlite_fallback.py       # SQLite降级
│   │   └── storage_manager.py       # 存储管理器
│   ├── notifier/
│   │   ├── __init__.py
│   │   └── feishu_notifier.py       # 飞书通知
│   └── main.py                      # 主编排器
├── tests/
│   └── unit/
│       ├── test_scorer.py
│       └── test_storage.py
├── .github/
│   └── workflows/
│       └── daily_collect.yml        # GitHub Actions工作流
├── logs/                            # 日志目录
├── .env.example                     # 环境变量模板
├── requirements.txt                 # 依赖清单
└── README.md                        # 项目说明
```

---

## 实施步骤 (严格按此顺序)

### Step 1: 基础模块 (30分钟)

#### 1.1 数据模型 (`src/models.py`)
```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class RawCandidate:
    """采集器原始输出"""
    title: str
    url: str
    source: str  # 'arxiv' | 'github' | 'pwc'
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    dataset_url: Optional[str] = None
    raw_metadata: Optional[dict] = None

@dataclass
class BenchmarkScore:
    """5维度评分"""
    innovation: int        # 0-10: 创新性
    technical_depth: int   # 0-10: 技术深度
    impact: int           # 0-10: 影响力
    data_quality: int     # 0-10: 数据质量
    reproducibility: int  # 0-10: 可复现性

    @property
    def total_score(self) -> int:
        return sum([
            self.innovation, self.technical_depth,
            self.impact, self.data_quality, self.reproducibility
        ])

    @property
    def priority(self) -> str:
        """优先级分级"""
        if self.total_score >= 40:
            return "high"
        elif self.total_score >= 30:
            return "medium"
        else:
            return "low"

@dataclass
class ScoredCandidate:
    """评分后的候选"""
    raw: RawCandidate
    score: BenchmarkScore
    filter_reason: Optional[str] = None
```

#### 1.2 配置管理 (`src/config.py`)
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
    LOG_DIR = 'logs/'

    @classmethod
    def validate(cls):
        """验证必需配置"""
        required = ['OPENAI_API_KEY', 'FEISHU_APP_ID', 'FEISHU_APP_SECRET']
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"缺少必需配置: {missing}")
```

### Step 2: 数据采集器 (1小时)

**优先级**: ArxivCollector > GitHubCollector > PwCCollector

#### 2.1 ArxivCollector (`src/collectors/arxiv_collector.py`)
```python
import arxiv
import asyncio
import logging
from typing import List
from datetime import datetime, timedelta
from ..models import RawCandidate

logger = logging.getLogger('BenchScope.ArxivCollector')

class ArxivCollector:
    """arXiv论文采集器"""

    def __init__(self):
        self.keywords = ["benchmark", "agent evaluation", "code generation", "web automation"]
        self.categories = ["cs.AI", "cs.CL", "cs.SE"]
        self.max_results = 50
        self.timeout = 10

    async def collect(self) -> List[RawCandidate]:
        """采集最近24小时的论文"""

        # 构建查询
        query_parts = [f'all:"{kw}"' for kw in self.keywords]
        query = " OR ".join(query_parts)

        cat_filter = " OR ".join([f"cat:{c}" for c in self.categories])
        full_query = f"({query}) AND ({cat_filter})"

        try:
            search = arxiv.Search(
                query=full_query,
                max_results=self.max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(None, list, search.results()),
                timeout=self.timeout
            )

        except asyncio.TimeoutError:
            logger.error(f"arXiv采集超时({self.timeout}s)")
            return []
        except Exception as e:
            logger.error(f"arXiv采集失败: {e}")
            return []

        # 转换为RawCandidate
        candidates = []
        cutoff_date = datetime.now() - timedelta(days=1)

        for paper in results:
            if paper.published < cutoff_date:
                continue

            candidates.append(RawCandidate(
                title=paper.title,
                url=paper.pdf_url,
                source='arxiv',
                abstract=paper.summary,
                authors=[a.name for a in paper.authors],
                publish_date=paper.published,
                raw_metadata={
                    'arxiv_id': paper.entry_id.split('/')[-1],
                    'categories': paper.categories
                }
            ))

        logger.info(f"arXiv采集完成,发现{len(candidates)}篇新论文")
        return candidates
```

#### 2.2 GitHubCollector (`src/collectors/github_collector.py`)
```python
import httpx
from bs4 import BeautifulSoup
import logging
from typing import List
from datetime import datetime
from ..models import RawCandidate

logger = logging.getLogger('BenchScope.GitHubCollector')

class GitHubCollector:
    """GitHub Trending采集器"""

    def __init__(self):
        self.min_stars = 100
        self.timeout = 5
        self.base_url = "https://github.com/trending"

    async def collect(self) -> List[RawCandidate]:
        """采集GitHub Trending仓库"""

        candidates = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.base_url)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, 'html.parser')
                repos = soup.find_all('article', class_='Box-row')

                for repo in repos:
                    h2 = repo.find('h2')
                    if not h2:
                        continue

                    repo_name = h2.get_text(strip=True).replace(' ', '').replace('\n', '')
                    repo_url = f"https://github.com/{repo_name}"

                    # 提取star数
                    star_elem = repo.find('svg', {'aria-label': 'star'})
                    stars = 0
                    if star_elem:
                        stars_text = star_elem.find_next('span').get_text(strip=True)
                        stars = self._parse_stars(stars_text)

                    if stars < self.min_stars:
                        continue

                    # 提取描述
                    desc_elem = repo.find('p', class_='col-9')
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    candidates.append(RawCandidate(
                        title=repo_name,
                        url=repo_url,
                        source='github',
                        abstract=description,
                        github_stars=stars,
                        github_url=repo_url,
                        publish_date=datetime.now()
                    ))

        except httpx.TimeoutException:
            logger.error(f"GitHub Trending采集超时")
            return []
        except Exception as e:
            logger.error(f"GitHub Trending采集失败: {e}")
            return []

        logger.info(f"GitHub采集完成,发现{len(candidates)}个trending仓库")
        return candidates

    def _parse_stars(self, stars_text: str) -> int:
        """解析star数量: '1.2k' -> 1200"""
        stars_text = stars_text.replace(',', '')
        if 'k' in stars_text:
            return int(float(stars_text.replace('k', '')) * 1000)
        return int(stars_text)
```

#### 2.3 PwCCollector - 暂时返回空列表(Phase 2实现)
```python
# src/collectors/pwc_collector.py
import logging
from typing import List
from ..models import RawCandidate

logger = logging.getLogger('BenchScope.PwCCollector')

class PwCCollector:
    """Papers with Code采集器 (Phase 2实现)"""

    async def collect(self) -> List[RawCandidate]:
        """暂时返回空列表"""
        logger.info("PwC采集器暂未实现,返回空列表")
        return []
```

### Step 3: 预筛选器 (30分钟)

#### 3.1 规则预筛选 (`src/prefilter/rule_filter.py`)
```python
import logging
from typing import List
from ..models import RawCandidate

logger = logging.getLogger('BenchScope.RuleFilter')

class RuleBasedPrefilter:
    """规则预筛选器"""

    def __init__(self):
        self.min_stars = 50

    def filter(self, candidates: List[RawCandidate]) -> List[RawCandidate]:
        """规则过滤"""

        filtered = []

        for c in candidates:
            # 规则1: GitHub仓库star数过低
            if c.source == 'github' and (c.github_stars or 0) < self.min_stars:
                logger.debug(f"过滤: {c.title} - star数过低({c.github_stars})")
                continue

            # 规则2: arXiv论文无摘要
            if c.source == 'arxiv' and not c.abstract:
                logger.debug(f"过滤: {c.title} - 无摘要")
                continue

            # 规则3: 标题含"survey"但无代码
            if 'survey' in c.title.lower() and not c.github_url:
                logger.debug(f"过滤: {c.title} - survey类论文无代码")
                continue

            filtered.append(c)

        filter_rate = (1 - len(filtered) / len(candidates)) * 100 if candidates else 0
        logger.info(f"预筛选完成,过滤率{filter_rate:.1f}%,剩余{len(filtered)}条")

        return filtered
```

### Step 4: 评分器 (1.5小时)

#### 4.1 规则评分器 (`src/scorer/rule_scorer.py`)
```python
from ..models import BenchmarkScore, RawCandidate

class RuleScorer:
    """规则评分器(LLM fallback)"""

    def score(self, candidate: RawCandidate) -> BenchmarkScore:
        """基于GitHub stars粗略评分"""

        stars = candidate.github_stars or 0

        if stars >= 1000:
            base_score = 8
        elif stars >= 500:
            base_score = 6
        elif stars >= 100:
            base_score = 4
        else:
            base_score = 2

        return BenchmarkScore(
            innovation=base_score,
            technical_depth=base_score,
            impact=base_score,
            data_quality=base_score,
            reproducibility=base_score if candidate.github_url else 2
        )
```

#### 4.2 LLM评分器 (`src/scorer/llm_scorer.py`)
```python
import openai
import redis
import json
import hashlib
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from ..models import BenchmarkScore, RawCandidate
from ..config import Config
from .rule_scorer import RuleScorer

logger = logging.getLogger('BenchScope.LLMScorer')

class LLMScorer:
    """LLM智能评分器"""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.timeout = 30
        self.cache = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.cache_ttl = 7 * 24 * 3600  # 7天
        self.fallback_scorer = RuleScorer()

    async def score(self, candidate: RawCandidate) -> BenchmarkScore:
        """为候选打分"""

        # 检查缓存
        cache_key = self._get_cache_key(candidate)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"缓存命中: {candidate.title[:50]}")
            return BenchmarkScore(**json.loads(cached))

        # 构建Prompt
        prompt = self._build_prompt(candidate)

        # 调用LLM
        try:
            score = await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM调用失败,fallback到规则评分: {e}")
            score = self.fallback_scorer.score(candidate)

        # 写入缓存
        self.cache.setex(cache_key, self.cache_ttl, json.dumps(score.__dict__))

        return score

    def _build_prompt(self, candidate: RawCandidate) -> str:
        """构建评分Prompt"""
        return f"""
请对以下Benchmark/评测数据集进行5维度评分(每个维度0-10分):

标题: {candidate.title}
来源: {candidate.source}
摘要: {candidate.abstract or 'N/A'}
GitHub Stars: {candidate.github_stars or 'N/A'}

评分维度:
1. 创新性 (Innovation): 任务或方法的新颖性
2. 技术深度 (Technical Depth): 技术复杂度,学术价值
3. 影响力 (Impact): 在AI/Agent领域的潜在影响力
4. 数据质量 (Data Quality): 数据集规模、多样性
5. 可复现性 (Reproducibility): 代码/数据开源程度

请以JSON格式返回:
{{
    "innovation": <0-10>,
    "technical_depth": <0-10>,
    "impact": <0-10>,
    "data_quality": <0-10>,
    "reproducibility": <0-10>
}}
""".strip()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _call_llm(self, prompt: str) -> BenchmarkScore:
        """调用LLM API"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个AI Benchmark评估专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200,
            timeout=self.timeout
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        return BenchmarkScore(
            innovation=data['innovation'],
            technical_depth=data['technical_depth'],
            impact=data['impact'],
            data_quality=data['data_quality'],
            reproducibility=data['reproducibility']
        )

    def _get_cache_key(self, candidate: RawCandidate) -> str:
        """生成缓存key"""
        return f"score:{hashlib.md5(candidate.title.encode()).hexdigest()}"
```

### Step 5: 存储层 (1.5小时)

#### 5.1 SQLite降级备份 (`src/storage/sqlite_fallback.py`)
```python
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List
from ..models import ScoredCandidate, RawCandidate, BenchmarkScore

logger = logging.getLogger('BenchScope.SQLiteFallback')

class SQLiteFallback:
    """SQLite降级存储"""

    def __init__(self, db_path='fallback.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fallback_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                score_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_to_feishu BOOLEAN DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    async def save(self, candidates: List[ScoredCandidate]):
        """保存到SQLite"""
        conn = sqlite3.connect(self.db_path)

        for c in candidates:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO fallback_candidates
                       (title, source, url, score_json, raw_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        c.raw.title,
                        c.raw.source,
                        c.raw.url,
                        json.dumps(c.score.__dict__),
                        json.dumps({
                            'title': c.raw.title,
                            'url': c.raw.url,
                            'source': c.raw.source,
                            'abstract': c.raw.abstract,
                            'github_stars': c.raw.github_stars,
                            'github_url': c.raw.github_url
                        })
                    )
                )
            except Exception as e:
                logger.error(f"SQLite写入失败: {c.raw.title} - {e}")

        conn.commit()
        conn.close()
        logger.info(f"SQLite备份完成: {len(candidates)}条")

    async def get_unsynced(self) -> List[ScoredCandidate]:
        """获取未同步记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT score_json, raw_json FROM fallback_candidates WHERE synced_to_feishu = 0"
        )

        candidates = []
        for row in cursor:
            score_data = json.loads(row[0])
            raw_data = json.loads(row[1])

            candidates.append(ScoredCandidate(
                raw=RawCandidate(**raw_data),
                score=BenchmarkScore(**score_data)
            ))

        conn.close()
        return candidates

    async def mark_synced(self, urls: List[str]):
        """标记已同步"""
        conn = sqlite3.connect(self.db_path)
        for url in urls:
            conn.execute(
                "UPDATE fallback_candidates SET synced_to_feishu = 1 WHERE url = ?",
                (url,)
            )
        conn.commit()
        conn.close()

    async def cleanup_old_records(self, days=7):
        """清理旧记录"""
        cutoff = datetime.now() - timedelta(days=days)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM fallback_candidates WHERE synced_to_feishu = 1 AND created_at < ?",
            (cutoff,)
        )
        conn.commit()
        conn.close()
        logger.info(f"清理{days}天前的已同步SQLite记录")
```

#### 5.2 飞书存储 (`src/storage/feishu_storage.py`)
```python
import httpx
import asyncio
import logging
from typing import List
from datetime import datetime, timedelta
from ..models import ScoredCandidate
from ..config import Config

logger = logging.getLogger('BenchScope.FeishuStorage')

class FeishuStorage:
    """飞书多维表格存储"""

    def __init__(self):
        self.app_id = Config.FEISHU_APP_ID
        self.app_secret = Config.FEISHU_APP_SECRET
        self.app_token = Config.FEISHU_BITABLE_APP_TOKEN
        self.table_id = Config.FEISHU_BITABLE_TABLE_ID
        self.base_url = "https://open.feishu.cn/open-apis"
        self.batch_size = 20
        self.access_token = None
        self.token_expires_at = None

    async def save(self, candidates: List[ScoredCandidate]) -> bool:
        """批量保存到飞书"""

        await self._ensure_access_token()

        # 构建记录
        records = []
        for c in candidates:
            records.append({
                "fields": {
                    "标题": c.raw.title,
                    "来源": c.raw.source,
                    "URL": c.raw.url,
                    "摘要": c.raw.abstract or "",
                    "创新性": c.score.innovation,
                    "技术深度": c.score.technical_depth,
                    "影响力": c.score.impact,
                    "数据质量": c.score.data_quality,
                    "可复现性": c.score.reproducibility,
                    "总分": c.score.total_score,
                    "优先级": c.score.priority,
                    "状态": "待审阅",
                    "发现时间": datetime.now().isoformat(),
                    "GitHub Stars": c.raw.github_stars or 0,
                    "GitHub URL": c.raw.github_url or ""
                }
            })

        # 分批写入
        url = f"{self.base_url}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"

        async with httpx.AsyncClient() as client:
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i+self.batch_size]

                try:
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                        json={"records": batch},
                        timeout=10
                    )
                    resp.raise_for_status()
                    logger.info(f"飞书写入成功: batch {i//self.batch_size + 1}, {len(batch)}条")

                except httpx.HTTPStatusError as e:
                    logger.error(f"飞书API错误: {e.response.status_code}")
                    raise FeishuAPIError(f"Batch write failed: {e}")

                await asyncio.sleep(0.6)  # 限流: 100 req/min

        return True

    async def _ensure_access_token(self):
        """确保access_token有效"""
        now = datetime.now()

        if self.access_token and self.token_expires_at and now < self.token_expires_at:
            return

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()

            self.access_token = data['tenant_access_token']
            self.token_expires_at = now + timedelta(seconds=data['expire'] - 300)

class FeishuAPIError(Exception):
    """飞书API异常"""
    pass
```

#### 5.3 存储管理器 (`src/storage/storage_manager.py`)
```python
import logging
from typing import List
from ..models import ScoredCandidate
from .feishu_storage import FeishuStorage, FeishuAPIError
from .sqlite_fallback import SQLiteFallback

logger = logging.getLogger('BenchScope.StorageManager')

class StorageManager:
    """存储管理器: 飞书主存储 + SQLite降级"""

    def __init__(self):
        self.feishu = FeishuStorage()
        self.sqlite = SQLiteFallback()

    async def save(self, candidates: List[ScoredCandidate]) -> bool:
        """保存候选"""

        try:
            # 尝试写入飞书
            await self.feishu.save(candidates)
            logger.info(f"✓ 飞书写入成功: {len(candidates)}条")

            # 成功后清理旧备份
            await self.sqlite.cleanup_old_records(days=7)

            # 同步未同步记录
            await self._sync_sqlite_to_feishu()

            return True

        except (FeishuAPIError, Exception) as e:
            logger.error(f"✗ 飞书写入失败,降级到SQLite: {e}")

            # 写入SQLite
            await self.sqlite.save(candidates)
            logger.warning(f"已启用SQLite降级备份")

            return False

    async def _sync_sqlite_to_feishu(self):
        """同步SQLite未同步记录"""
        unsynced = await self.sqlite.get_unsynced()

        if not unsynced:
            return

        logger.info(f"发现{len(unsynced)}条未同步SQLite记录,尝试同步")

        try:
            await self.feishu.save(unsynced)
            urls = [c.raw.url for c in unsynced]
            await self.sqlite.mark_synced(urls)
            logger.info(f"✓ SQLite记录同步成功: {len(unsynced)}条")

        except Exception as e:
            logger.error(f"✗ SQLite同步失败,下次重试: {e}")
```

### Step 6: 通知器 (30分钟)

#### 6.1 飞书通知 (`src/notifier/feishu_notifier.py`)
```python
import httpx
import logging
from typing import List
from datetime import datetime
from ..models import ScoredCandidate
from ..config import Config

logger = logging.getLogger('BenchScope.FeishuNotifier')

class FeishuNotifier:
    """飞书通知"""

    def __init__(self):
        self.webhook_url = Config.FEISHU_WEBHOOK_URL

    async def notify(self, candidates: List[ScoredCandidate]):
        """发送通知"""

        if not candidates:
            logger.info("无高分候选,跳过通知")
            return

        # 构建消息
        message = self._build_message(candidates)

        # 发送Webhook
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self.webhook_url,
                    json={"msg_type": "text", "content": {"text": message}},
                    timeout=5
                )
                resp.raise_for_status()
                logger.info(f"飞书通知发送成功")

            except Exception as e:
                logger.error(f"飞书通知失败: {e}")

    def _build_message(self, candidates: List[ScoredCandidate]) -> str:
        """构建消息内容"""

        lines = [
            f"📊 BenchScope日报 - {datetime.now():%Y-%m-%d}",
            "",
            f"本次发现 {len(candidates)} 个高质量Benchmark候选",
            "",
            "🔥 Top 5推荐:"
        ]

        for i, c in enumerate(candidates[:5], 1):
            lines.append(
                f"{i}. {c.raw.title} - 总分{c.score.total_score} ({c.score.priority})\n"
                f"   {c.raw.url}"
            )

        return "\n".join(lines)
```

### Step 7: 主编排器 (30分钟)

#### 7.1 主流程 (`src/main.py`)
```python
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from .models import ScoredCandidate
from .config import Config
from .collectors.arxiv_collector import ArxivCollector
from .collectors.github_collector import GitHubCollector
from .collectors.pwc_collector import PwCCollector
from .prefilter.rule_filter import RuleBasedPrefilter
from .scorer.llm_scorer import LLMScorer
from .storage.storage_manager import StorageManager
from .notifier.feishu_notifier import FeishuNotifier

# 配置日志
Path(Config.LOG_DIR).mkdir(exist_ok=True)
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{Config.LOG_DIR}/{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('BenchScope.Main')

async def run_daily_collection():
    """每日采集主流程"""

    logger.info("========== BenchScope每日采集开始 ==========")

    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        return

    # Step 1: 并发采集
    logger.info("Step 1: 数据采集...")
    collectors = [ArxivCollector(), GitHubCollector(), PwCCollector()]

    results = await asyncio.gather(
        *[c.collect() for c in collectors],
        return_exceptions=True
    )

    all_candidates = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"采集器{collectors[i].__class__.__name__}失败: {result}")
        else:
            all_candidates.extend(result)
            logger.info(f"{collectors[i].__class__.__name__}采集到{len(result)}条")

    logger.info(f"采集完成,共{len(all_candidates)}条原始数据")

    if not all_candidates:
        logger.warning("无数据采集,流程结束")
        return

    # Step 2: 规则预筛选
    logger.info("Step 2: 规则预筛选...")
    prefilter = RuleBasedPrefilter()
    filtered = prefilter.filter(all_candidates)

    # Step 3: LLM评分
    logger.info("Step 3: LLM评分...")
    scorer = LLMScorer()
    scored_candidates = []

    for candidate in filtered:
        try:
            score = await scorer.score(candidate)
            scored_candidates.append(ScoredCandidate(raw=candidate, score=score))
        except Exception as e:
            logger.error(f"评分失败: {candidate.title[:50]} - {e}")

    logger.info(f"评分完成,成功{len(scored_candidates)}条")

    if not scored_candidates:
        logger.warning("无候选通过评分,流程结束")
        return

    # Step 4: 存储
    logger.info("Step 4: 存储...")
    storage = StorageManager()
    success = await storage.save(scored_candidates)

    # Step 5: 通知
    logger.info("Step 5: 发送通知...")
    top5 = sorted(scored_candidates, key=lambda x: x.score.total_score, reverse=True)[:5]
    notifier = FeishuNotifier()
    await notifier.notify(top5)

    logger.info(f"========== 流程结束,处理{len(scored_candidates)}条候选 ==========")

if __name__ == '__main__':
    asyncio.run(run_daily_collection())
```

### Step 8: GitHub Actions (15分钟)

#### 8.1 工作流 (`.github/workflows/daily_collect.yml`)
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
        run: python -m src.main

      - name: Upload Logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: logs
          path: logs/
          retention-days: 7
```

### Step 9: 依赖和环境 (15分钟)

#### 9.1 依赖清单 (`requirements.txt`)
```txt
python>=3.11

# HTTP
httpx>=0.25.0

# 数据采集
arxiv>=2.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# LLM
openai>=1.3.0

# 缓存
redis>=5.0.0

# 工具
python-dotenv>=1.0.0
tenacity>=8.2.0

# 测试
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

#### 9.2 环境变量模板 (`.env.example`)
```bash
# OpenAI API
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# 飞书开放平台
FEISHU_APP_ID=cli_...
FEISHU_APP_SECRET=...
FEISHU_BITABLE_APP_TOKEN=...
FEISHU_BITABLE_TABLE_ID=...
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...

# Redis缓存
REDIS_URL=redis://localhost:6379

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs/
```

### Step 10: 测试 (30分钟)

#### 10.1 单元测试 (`tests/unit/test_scorer.py`)
```python
import pytest
from src.models import RawCandidate
from src.scorer.llm_scorer import LLMScorer
from src.scorer.rule_scorer import RuleScorer

@pytest.mark.asyncio
async def test_llm_scorer_basic():
    """测试LLM评分基本功能"""
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

def test_rule_scorer():
    """测试规则评分"""
    scorer = RuleScorer()

    candidate = RawCandidate(
        title="Test",
        url="https://test.com",
        source="github",
        github_stars=1500
    )

    score = scorer.score(candidate)
    assert score.total_score >= 30  # 高star应该高分
```

---

## 代码规范 (强制执行)

### Python风格
1. **PEP8合规**: 4空格缩进, `snake_case`函数/变量, `PascalCase`类名
2. **类型注解**: 所有函数必须有类型注解
3. **中文注释**: 关键逻辑必须写中文注释
4. **嵌套限制**: 最大3层嵌套(Linus规则),超过必须early return
5. **魔法数字**: 定义常量,不要硬编码

### 异步编程
- 使用`async/await`
- 超时控制: `asyncio.timeout()`
- 并发限流: `asyncio.Semaphore()`
- 容错: `return_exceptions=True`

### 错误处理
- 采集器失败返回空列表,不抛异常
- LLM失败fallback到规则评分
- 飞书失败降级到SQLite
- 使用`tenacity`重试

---

## 验收标准

### 功能验收
- [ ] GitHub Actions每日自动运行
- [ ] arXiv/GitHub/PwC三个采集器可用
- [ ] 预筛选过滤率40-60%
- [ ] LLM评分成功率>90%
- [ ] 飞书多维表格自动写入
- [ ] 飞书通知每日推送
- [ ] SQLite降级备份可用
- [ ] 日志完整记录

### 性能验收
- [ ] 总执行时间 < 20分钟
- [ ] LLM月成本 < ¥50
- [ ] 数据采集成功率 > 95%

### 质量验收
- [ ] 代码通过`black`格式化
- [ ] 代码通过`ruff check`
- [ ] 关键逻辑有中文注释
- [ ] 核心模块有单元测试
- [ ] 手动测试报告完整

---

## 关键约束

1. **手动测试强制执行**:
   - 飞书播报、飞书多维表格必须手动验证
   - 结果记录到`docs/test-report.md`并附截图

2. **Linus哲学**:
   - Is this a real problem? → 拒绝过度工程
   - Is there a simpler way? → 永远寻找最简单实现
   - What will this break? → MVP零破坏

3. **成本控制**:
   - LLM月成本必须<¥50
   - 优先使用缓存和规则过滤

---

## 开始开发

**你的任务**:
1. 严格按照上述步骤实施MVP (Step 1-10)
2. 遵循代码规范和测试要求
3. 完成后进行手动测试并记录
4. 提交代码前运行`black`和`ruff`

**参考文档**:
- `.claude/specs/benchmark-intelligence-agent/02-system-architecture.md` - 完整架构设计
- `.claude/specs/benchmark-intelligence-agent/CODEX-DEVELOPMENT-BRIEF.md` - 详细开发指南

**预估时间**: 6-8小时

Good luck! 开始编码吧。🚀
