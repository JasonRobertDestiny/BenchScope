# Twitter采集器 MVP PRD - MGX场景聚焦

**产品名称**: BenchScope Twitter Intelligence Collector
**版本**: v1.0 MVP
**优先级**: P1 (Phase 6扩展)
**服务对象**: [MGX (https://mgx.dev)](https://mgx.dev) - 多智能体协作框架

---

## 1. 产品定位

### 1.1 核心价值

**问题**:
- AI/Agent领域的Benchmark讨论大量发生在Twitter/X
- 开源项目发布、论文讨论、评测结果常在Twitter首发
- 错过Twitter信息 = 错过领域前沿动态

**解决方案**:
- 自动采集Twitter/X上AI Agent/Benchmark相关讨论
- 提取高质量推文中的论文链接、GitHub项目、评测数据
- 整合到BenchScope主流程，统一预筛选和评分

**差异化**:
- 聚焦MGX核心场景：AI Agent、代码生成、多智能体协作
- 不采集无关内容（娱乐、政治、营销等）
- 利用Twitter互动数据（点赞、转发）作为质量信号

### 1.2 目标用户

**主要用户**: MGX研发团队
- 需求：快速发现Agent/Coding Benchmark新动态
- 痛点：手动刷Twitter低效，容易遗漏重要信息

**次要用户**: AI研究者
- 需求：追踪领域前沿评测方法
- 痛点：信息碎片化，难以系统整理

---

## 2. 功能范围

### 2.1 MVP核心功能

**In Scope** (MVP必做):
1. ✅ **关键词搜索采集** - 基于预定义关键词搜索推文
2. ✅ **Twitter API v2集成** - 使用Bearer Token认证
3. ✅ **URL提取** - 提取推文中的arXiv/GitHub/HuggingFace链接
4. ✅ **互动数据过滤** - 基于点赞/转发数预筛选
5. ✅ **RawCandidate转换** - 标准化为BenchScope数据模型
6. ✅ **时间窗口控制** - 可配置采集最近N天的推文

**Out of Scope** (MVP暂不做):
- ❌ 账号监控（Follow特定用户）
- ❌ 实时流式采集（Streaming API）
- ❌ 推文回复分析（Thread展开）
- ❌ 图片/视频内容提取
- ❌ 情感分析
- ❌ 推文翻译（仅支持英文）

### 2.2 MGX场景关键词

**Tier 1 (核心关键词)** - 必须包含:
```
- "AI agent benchmark"
- "LLM code generation"
- "multi-agent evaluation"
- "coding benchmark"
- "agent framework"
```

**Tier 2 (扩展关键词)** - 提升覆盖面:
```
- "HumanEval"
- "MBPP benchmark"
- "SWE-bench"
- "agent leaderboard"
- "LLM evaluation"
- "code interpreter"
```

**Tier 3 (MGX相关)** - 品牌监控:
```
- "MGX framework"
- "vibe coding"
- "AI native programming"
```

---

## 3. 数据流设计

### 3.1 采集流程

```
Twitter API v2 Search
    ↓
查询关键词 (Tier 1 + Tier 2)
    ↓
时间窗口过滤 (最近7天)
    ↓
返回推文列表 (最多100条/关键词)
    ↓
预筛选 (互动数、URL存在性)
    ├─ 点赞数 ≥ 10
    ├─ 转发数 ≥ 5
    └─ 必须包含URL链接
    ↓
URL提取与分类
    ├─ arXiv论文 → paper_url
    ├─ GitHub仓库 → url + github_url
    └─ HuggingFace → url
    ↓
转换为RawCandidate
    ↓
合并到主流程 (Step 1.5插入)
    ↓
后续统一预筛选、PDF增强、LLM评分
```

### 3.2 数据模型映射

**Twitter推文** → **RawCandidate**:

| Twitter字段 | RawCandidate字段 | 映射逻辑 |
|------------|-----------------|---------|
| `text` | `abstract` | 推文全文（去除URL） |
| `author.username` | `raw_authors` | 作者Twitter用户名 |
| `created_at` | `publish_date` | 推文发布时间 |
| `public_metrics.like_count` | `github_stars` | 点赞数（复用字段） |
| `entities.urls[].expanded_url` | `url` / `paper_url` | 提取的链接 |
| - | `source` | 固定为 "twitter" |
| `id` | `raw_metadata["tweet_id"]` | 推文ID |
| `public_metrics.retweet_count` | `raw_metadata["retweets"]` | 转发数 |

### 3.3 URL提取规则

**arXiv论文**:
```python
if "arxiv.org/abs/" in url or "arxiv.org/pdf/" in url:
    candidate.paper_url = url
    candidate.source = "arxiv"  # 后续可触发PDF增强
```

**GitHub仓库**:
```python
if "github.com/" in url and "/blob/" not in url:
    candidate.url = url
    candidate.github_url = url
    candidate.source = "github"  # 后续可提取README
```

**HuggingFace**:
```python
if "huggingface.co/" in url:
    candidate.url = url
    candidate.source = "huggingface"
```

**其他链接**:
```python
else:
    candidate.url = url
    candidate.source = "twitter"  # 不触发特殊处理
```

---

## 4. 技术实现

### 4.1 Twitter API配置

**API版本**: Twitter API v2
**认证方式**: Bearer Token (App-only authentication)
**端点**: `GET /2/tweets/search/recent`

**环境变量** (已配置):
```bash
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAA...
```

**速率限制**:
- 免费版: 450次请求/15分钟 (30次/分钟)
- 基础版: 100条推文/请求
- 时间窗口: 最近7天

### 4.2 代码架构

**新增文件**:
```
src/collectors/twitter_collector.py   # Twitter采集器
tests/test_twitter_collector.py       # 单元测试
```

**配置文件** (`config/sources.yaml`):
```yaml
twitter:
  enabled: true
  lookback_days: 7
  max_results_per_query: 100
  search_queries:
    tier1:
      - "AI agent benchmark"
      - "LLM code generation"
      - "multi-agent evaluation"
    tier2:
      - "HumanEval"
      - "SWE-bench"
      - "agent leaderboard"
  filters:
    min_likes: 10
    min_retweets: 5
    must_have_url: true
    language: "en"
  rate_limit_delay: 2.0  # 秒，避免触发限流
```

### 4.3 核心类设计

```python
class TwitterCollector:
    """Twitter/X推文采集器 (MVP版本)

    功能:
    1. 基于关键词搜索推文
    2. 提取推文中的URL链接
    3. 转换为RawCandidate

    限制:
    - 仅支持Twitter API v2
    - 仅搜索最近7天推文
    - 不支持实时流式采集
    """

    def __init__(self, settings: Settings):
        self.bearer_token = settings.twitter_bearer_token
        self.client = httpx.AsyncClient()
        self.config = self._load_config()

    async def collect(self) -> List[RawCandidate]:
        """采集推文并转换为候选项"""
        all_tweets = []

        # Tier 1 + Tier 2关键词
        queries = self.config["tier1"] + self.config["tier2"]

        for query in queries:
            tweets = await self._search_tweets(query)
            all_tweets.extend(tweets)

        # 去重（同一推文可能匹配多个关键词）
        unique_tweets = self._deduplicate(all_tweets)

        # 预筛选
        filtered = self._prefilter(unique_tweets)

        # 转换为RawCandidate
        candidates = [self._to_candidate(t) for t in filtered]

        return candidates

    async def _search_tweets(self, query: str) -> List[Dict]:
        """调用Twitter API v2搜索推文"""
        # 实现API调用逻辑
        pass

    def _prefilter(self, tweets: List[Dict]) -> List[Dict]:
        """预筛选：互动数、URL存在性"""
        filtered = []
        for tweet in tweets:
            metrics = tweet["public_metrics"]

            # 检查互动数
            if metrics["like_count"] < self.config["min_likes"]:
                continue
            if metrics["retweet_count"] < self.config["min_retweets"]:
                continue

            # 检查URL
            if self.config["must_have_url"]:
                if not tweet.get("entities", {}).get("urls"):
                    continue

            filtered.append(tweet)

        return filtered

    def _to_candidate(self, tweet: Dict) -> RawCandidate:
        """转换推文为RawCandidate"""
        # 提取URL
        urls = tweet.get("entities", {}).get("urls", [])
        primary_url = urls[0]["expanded_url"] if urls else None

        # 分类URL
        source = "twitter"
        paper_url = None
        github_url = None

        if primary_url:
            if "arxiv.org" in primary_url:
                source = "arxiv"
                paper_url = primary_url
            elif "github.com" in primary_url:
                source = "github"
                github_url = primary_url

        return RawCandidate(
            title=self._extract_title(tweet["text"]),
            url=primary_url,
            source=source,
            abstract=self._clean_text(tweet["text"]),
            authors=None,
            publish_date=tweet["created_at"],
            github_stars=tweet["public_metrics"]["like_count"],
            paper_url=paper_url,
            github_url=github_url,
            raw_metadata={
                "tweet_id": tweet["id"],
                "retweets": tweet["public_metrics"]["retweet_count"],
                "replies": tweet["public_metrics"]["reply_count"],
                "author_username": tweet["author"]["username"],
                "tweet_url": f"https://twitter.com/i/web/status/{tweet['id']}",
            },
        )
```

---

## 5. 验收标准

### 5.1 功能验收

- [ ] 成功调用Twitter API v2搜索端点
- [ ] 能够搜索Tier 1关键词并返回推文
- [ ] 正确提取推文中的URL（arXiv/GitHub/HuggingFace）
- [ ] 互动数预筛选正常工作（过滤低质量推文）
- [ ] 转换为RawCandidate格式正确
- [ ] 推文去重逻辑有效（同一推文不重复）
- [ ] 集成到主流程（Step 1.5插入）
- [ ] 单元测试覆盖率 ≥ 80%

### 5.2 数据质量验收

**测试数据**（预期1周采集量）:
- 采集推文数: 100-200条
- 预筛选通过率: 20-40% (20-80条)
- arXiv链接提取率: ≥30% (6-24条)
- GitHub链接提取率: ≥40% (8-32条)

**质量指标**:
- 误报率 < 20% (非Benchmark内容)
- 漏报率 < 30% (遗漏重要Benchmark)
- URL提取准确率 ≥ 95%

### 5.3 性能验收

- 单次采集耗时 < 60秒 (10个关键词)
- 不触发Twitter API限流（450次/15分钟）
- 内存占用 < 200MB
- 与现有采集器并发运行无冲突

---

## 6. 风险与缓解

### 6.1 技术风险

**风险1: Twitter API限流**
- 影响: 采集失败或不完整
- 缓解:
  - 控制请求频率（2秒间隔）
  - 缓存已采集推文（避免重复请求）
  - 降级策略：失败时跳过当前关键词

**风险2: URL提取不准确**
- 影响: 遗漏有价值链接或提取错误链接
- 缓解:
  - 使用Twitter API的`entities.urls`字段（自动展开短链）
  - 正则表达式严格匹配arXiv/GitHub/HuggingFace模式
  - 单元测试覆盖各种URL格式

**风险3: 推文内容质量低**
- 影响: 噪音过多，淹没有价值信息
- 缓解:
  - 提高互动数阈值（likes≥10, retweets≥5）
  - 强制包含URL链接
  - 仅采集英文推文
  - 规则预筛选和LLM评分双重过滤

### 6.2 业务风险

**风险4: Twitter账号封禁**
- 影响: 无法继续采集
- 缓解:
  - 遵守Twitter API使用条款
  - 使用官方App认证（非爬虫）
  - 控制请求频率，避免滥用

**风险5: 信息覆盖不全**
- 影响: 错过重要Benchmark讨论
- 缓解:
  - 持续优化关键词列表
  - 结合其他数据源（arXiv、GitHub、HELM）
  - 定期复盘遗漏案例，更新查询策略

---

## 7. 开发计划

### 7.1 Week 1 (MVP实现)

**Day 1-2: 核心采集器**
- [x] 创建 `TwitterCollector` 类
- [x] 实现Twitter API v2调用
- [x] 实现关键词搜索逻辑
- [x] 实现URL提取逻辑

**Day 3: 数据转换与集成**
- [ ] 实现 `_to_candidate` 转换方法
- [ ] 集成到 `src/main.py` (Step 1.5)
- [ ] 配置 `config/sources.yaml`

**Day 4: 测试与优化**
- [ ] 编写单元测试
- [ ] 运行完整流程测试
- [ ] 优化预筛选规则

**Day 5: 文档与验收**
- [ ] 编写使用文档
- [ ] 生成测试报告
- [ ] 数据质量分析

### 7.2 Week 2 (优化与扩展，可选)

- [ ] 增加Tier 3关键词（MGX品牌）
- [ ] 优化去重逻辑（基于URL而非推文ID）
- [ ] 添加Redis缓存（避免重复采集）
- [ ] 账号监控功能（Follow @OpenAI等）

---

## 8. 成功指标

**量化目标** (运行1周后):
- 新增候选数: 20-50个/周
- arXiv论文发现: 5-10篇/周
- GitHub项目发现: 10-20个/周
- 最终入库Benchmark: 2-5个/周

**质量目标**:
- Twitter来源候选平均分 ≥ 6.0
- Twitter来源候选入库率 ≥ 10%
- 与arXiv/GitHub采集器重复率 < 30% (证明增量价值)

---

## 9. 后续迭代方向

**Phase 6.1** (短期):
- 支持账号监控（Follow特定用户）
- 支持Hashtag搜索（#MachineLearning）
- 推文Thread展开（完整对话上下文）

**Phase 6.2** (中期):
- 实时流式采集（Streaming API）
- 图片内容OCR提取（评测结果截图）
- 推文情感分析（区分正面/负面讨论）

**Phase 6.3** (长期):
- 多平台整合（Reddit、HackerNews）
- 社区影响力评分（作者follower权重）
- 话题趋势分析（热门Benchmark追踪）

---

**PRD版本**: v1.0
**文档所有者**: Claude Code
**最后更新**: 2025-11-17
**审核状态**: 待用户确认
