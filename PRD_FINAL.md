# Benchmark Intelligence Agent (BIA) 产品需求文档

**版本**: v2.0 Final
**日期**: 2025-11-12
**状态**: 可执行版本

---

## 一、项目背景与核心问题

### 真实问题

AI/Agent领域的Benchmark每周都有新的出现，但90%的信息噪音让人无法高效筛选：

- **信息过载**：arXiv每天500+篇论文，GitHub每天上千个新仓库，人工筛选成本极高
- **质量参差**：大量Benchmark缺少代码、数据集不开源、许可证不明确，浪费评估时间
- **更新滞后**：手动维护的Benchmark候选池，往往发现新资源时已经落后数周
- **适配度低**：很多看起来"热门"的Benchmark与内部需求完全不相关

### 解决什么问题

建立一个自动化情报系统，解决三个核心问题：

1. **发现成本高** → 自动从多源头采集，覆盖论文库/榜单/社区/社交媒体
2. **筛选效率低** → 自动评分（活跃度/可复现性/许可/适配度），过滤噪音
3. **入库流程慢** → 一键审核入库，定期播报推送，人机协作决策

### 不解决什么问题

- 不做SEO优化、不做对外内容营销（纯内部系统）
- 不做深度模型训练（使用规则+LLM抽取即可）
- 不追求100%自动化（关键决策保留人工审核）

---

## 二、系统架构设计

### 整体流程

```
数据源配置
    ↓
定时采集调度 (GitHub Actions / Airflow)
    ↓
多源数据抓取 (arXiv/PwC/GitHub/HuggingFace)
    ↓
结构化信息抽取 (LLM + 规则引擎)
    ↓
预筛选评分 (活跃度/可复现性/许可/适配度)
    ↓
候选池入库 (Notion/Airtable)
    ↓
飞书播报 (卡片消息 + 一键添加按钮)
    ↓
人工审核确认
    ↓
正式Benchmark库
    ↓
版本跟踪与更新监控
```

### 模块拆解

#### 1. 数据采集模块 (Data Collector)

**数据源优先级**：

| 来源 | API/工具 | 更新频率 | 价值评级 |
|------|---------|---------|---------|
| arXiv | arXiv API + RSS | 每日 | 高（新研究） |
| Papers with Code | PwC API Client | 每日 | 高（任务榜单） |
| GitHub Trending | GitHub API / Trending API | 每日 | 中（代码热度） |
| HuggingFace Hub | `huggingface_hub` SDK | 每日 | 中（数据集） |
| AgentBench/HELM | 官方API/爬虫 | 每周 | 高（评测标准） |
| Twitter/X | snscrape / Twitter API | 按需 | 低（噪音大） |
| 内部线索 | 飞书监控 | 实时 | 高（针对性强） |

**实现细节**：

```python
# 核心采集接口
class BenchmarkCollector:
    def collect_arxiv(self, keywords: List[str], categories: List[str]) -> List[Paper]:
        """
        arXiv采集：使用官方API + RSS订阅
        keywords: ["benchmark", "evaluation", "dataset"]
        categories: ["cs.AI", "cs.CL", "cs.LG"]
        """
        pass

    def collect_pwc(self, task_types: List[str]) -> List[Benchmark]:
        """
        Papers with Code采集：通过官方API Client
        task_types: ["agent", "coding", "web-navigation"]
        """
        pass

    def collect_github_trending(self, language: str = "Python") -> List[Repo]:
        """
        GitHub Trending采集：Trending API
        过滤条件：stars > 100, has_topics(["benchmark", "evaluation"])
        """
        pass
```

**关键配置**：

```yaml
# config/sources.yaml
arxiv:
  keywords: ["benchmark", "agent evaluation", "code generation"]
  categories: ["cs.AI", "cs.CL", "cs.SE"]
  max_results: 50
  update_interval: "daily"

papers_with_code:
  task_areas: ["coding", "agent", "reasoning"]
  min_papers: 3  # 至少3篇论文的任务才考虑
  update_interval: "daily"

github:
  topics: ["benchmark", "evaluation", "agent"]
  min_stars: 100
  min_recent_activity: 30  # 30天内有更新
  update_interval: "daily"
```

#### 2. 预筛选模块 (Pre-filter Engine)

**评分维度**：

| 维度 | 权重 | 数据来源 | 阈值 |
|------|------|---------|------|
| 活跃度 | 25% | GitHub stars/forks/commits | stars > 50 |
| 可复现性 | 30% | 代码/数据开源状态 | 必须有代码或数据 |
| 许可合规 | 20% | License字段 | MIT/Apache/BSD |
| 任务新颖性 | 15% | 与已有任务的相似度 | 相似度 < 0.8 |
| MGX适配度 | 10% | LLM判断业务相关性 | 评分 > 6/10 |

**评分算法**：

```python
# 活跃度评分（0-10分）
def score_activity(repo: GitHubRepo) -> float:
    """
    评分规则：
    - stars: 0-100 → 0-3分, 100-500 → 3-6分, 500+ → 6-10分
    - 最近更新: 7天内 → +2分, 30天内 → +1分, 90天+ → -2分
    - forks: 每100个 +0.5分（上限2分）
    """
    score = 0
    if repo.stars < 100:
        score += repo.stars / 100 * 3
    elif repo.stars < 500:
        score += 3 + (repo.stars - 100) / 400 * 3
    else:
        score += 6 + min((repo.stars - 500) / 1000 * 4, 4)

    days_since_update = (datetime.now() - repo.last_commit).days
    if days_since_update <= 7:
        score += 2
    elif days_since_update <= 30:
        score += 1
    elif days_since_update > 90:
        score -= 2

    score += min(repo.forks / 100 * 0.5, 2)
    return max(0, min(10, score))

# 可复现性评分（0-10分）
def score_reproducibility(item: BenchmarkCandidate) -> float:
    """
    评分规则：
    - 有开源代码仓库 → 6分
    - 有数据集下载链接 → 3分
    - 有复现脚本/文档 → 1分
    - 无任何资源 → 0分（直接过滤）
    """
    score = 0
    if item.has_code_repo:
        score += 6
    if item.has_dataset:
        score += 3
    if item.has_reproduction_doc:
        score += 1
    return score

# MGX适配度评分（LLM判断）
def score_mgx_relevance(description: str) -> float:
    """
    使用LLM判断与MGX项目的相关性
    Prompt: "阅读这段Benchmark描述，判断其与'多智能体协作/对话/代码生成'的相关性，打分0-10"
    """
    prompt = f"""
    MGX项目关注：多智能体协作、人机对话、代码生成、Web自动化

    Benchmark描述：
    {description}

    请判断该Benchmark与MGX项目的相关性，返回JSON：
    {{
        "relevance_score": 0-10,
        "reasoning": "判断理由"
    }}
    """
    response = llm.call(prompt)
    return response['relevance_score']

# 综合评分
def calculate_total_score(candidate: BenchmarkCandidate) -> float:
    """
    加权综合评分 =
        活跃度 * 0.25 +
        可复现性 * 0.30 +
        许可合规 * 0.20 +
        任务新颖性 * 0.15 +
        MGX适配度 * 0.10

    筛选阈值：总分 >= 6.0
    """
    activity = score_activity(candidate.repo) * 0.25
    reproducibility = score_reproducibility(candidate) * 0.30
    license = (10 if candidate.license in ['MIT', 'Apache-2.0', 'BSD'] else 0) * 0.20
    novelty = (10 - candidate.similarity_to_existing * 10) * 0.15
    relevance = score_mgx_relevance(candidate.description) * 0.10

    return activity + reproducibility + license + novelty + relevance
```

**LLM辅助信息抽取**：

```python
# 使用LangChain结构化抽取
from langchain.chains import create_extraction_chain

schema = {
    "properties": {
        "has_code": {"type": "boolean"},
        "has_dataset": {"type": "boolean"},
        "task_type": {"type": "string", "enum": ["coding", "agent", "reasoning", "web"]},
        "evaluation_metrics": {"type": "array", "items": {"type": "string"}},
        "is_novel": {"type": "boolean"},
    },
    "required": ["has_code", "task_type"]
}

chain = create_extraction_chain(schema, llm)
extracted = chain.run(paper_abstract)
```

#### 3. 候选池管理模块 (Candidate Manager)

**数据存储方案**：推荐使用 **Notion** 或 **Airtable**（理由见下）

**为什么选Notion/Airtable而不是数据库**：

1. **可视化管理**：研究员可以直接在Notion表格中筛选、排序、标注
2. **低代码维护**：字段修改不需要写migration脚本
3. **协作友好**：支持评论、@提醒、权限管理
4. **API成熟**：官方SDK支持自动化写入

**Benchmark候选表字段设计**：

| 字段名 | 类型 | 说明 | 必填 |
|--------|------|------|------|
| id | Text | 唯一标识（自动生成） | 是 |
| name | Title | Benchmark名称 | 是 |
| category | Select | 领域分类（Agent/Coding/Web/Reasoning） | 是 |
| paper_url | URL | 论文链接 | 否 |
| code_repo | URL | 代码仓库地址 | 否 |
| dataset_url | URL | 数据集下载地址 | 否 |
| metrics | Multi-select | 评测指标（Pass@1/Win Rate/Accuracy） | 否 |
| license | Select | 开源许可（MIT/Apache/GPL/Unknown） | 是 |
| stars | Number | GitHub stars | 否 |
| last_update | Date | 最近更新时间 | 否 |
| activity_score | Number | 活跃度评分（0-10） | 是 |
| reproducibility_score | Number | 可复现性评分（0-10） | 是 |
| relevance_score | Number | MGX适配度评分（0-10） | 是 |
| total_score | Formula | 综合评分（自动计算） | 是 |
| status | Select | 状态（候选/审核中/已添加/已拒绝） | 是 |
| recommendation | Text | 推荐理由（AI生成） | 否 |
| added_at | Created Time | 入库时间 | 是 |
| reviewed_by | Person | 审核人 | 否 |
| notes | Text | 备注 | 否 |

**Notion API集成示例**：

```python
from notion_client import Client

notion = Client(auth=os.environ["NOTION_TOKEN"])
database_id = "your-database-id"

def add_candidate_to_notion(candidate: BenchmarkCandidate):
    """添加候选Benchmark到Notion数据库"""
    notion.pages.create(
        parent={"database_id": database_id},
        properties={
            "name": {"title": [{"text": {"content": candidate.name}}]},
            "category": {"select": {"name": candidate.category}},
            "paper_url": {"url": candidate.paper_url},
            "code_repo": {"url": candidate.code_repo},
            "total_score": {"number": candidate.total_score},
            "status": {"select": {"name": "候选"}},
            "recommendation": {"rich_text": [{"text": {"content": candidate.reasoning}}]}
        }
    )
```

#### 4. 自动播报模块 (Notification Engine)

**飞书卡片消息格式**：

```json
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🔔 新发现Benchmark: WebArena"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": true,
                        "text": {
                            "tag": "lark_md",
                            "content": "**分类**\nAgent"
                        }
                    },
                    {
                        "is_short": true,
                        "text": {
                            "tag": "lark_md",
                            "content": "**评分**\n8.5/10"
                        }
                    },
                    {
                        "is_short": true,
                        "text": {
                            "tag": "lark_md",
                            "content": "**Stars**\n1234"
                        }
                    },
                    {
                        "is_short": true,
                        "text": {
                            "tag": "lark_md",
                            "content": "**许可**\nMIT"
                        }
                    }
                ]
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**推荐理由**\n首个真实Web环境的Agent评测基准，包含50+网站任务，可复现性强，与MGX的Web自动化方向高度相关。"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "一键添加"
                        },
                        "type": "primary",
                        "value": {
                            "benchmark_id": "benchmark_id_123"
                        }
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看详情"
                        },
                        "type": "default",
                        "url": "https://notion.so/xxx"
                    }
                ]
            }
        ]
    }
}
```

**一键添加交互实现**：

```python
from flask import Flask, request, jsonify
import hmac
import hashlib
import json

app = Flask(__name__)

# 飞书开放平台配置
FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]
FEISHU_VERIFICATION_TOKEN = os.environ["FEISHU_VERIFICATION_TOKEN"]
FEISHU_ENCRYPT_KEY = os.environ.get("FEISHU_ENCRYPT_KEY", "")

class FeishuClient:
    """飞书API客户端"""

    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.tenant_access_token = None

    def get_tenant_access_token(self):
        """获取tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        response = requests.post(url, json=payload)
        data = response.json()
        if data.get("code") == 0:
            self.tenant_access_token = data["tenant_access_token"]
        return self.tenant_access_token

    def send_card_message(self, chat_id: str, card: dict):
        """发送卡片消息"""
        if not self.tenant_access_token:
            self.get_tenant_access_token()

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card)
        }
        params = {"receive_id_type": "chat_id"}

        response = requests.post(url, headers=headers, json=payload, params=params)
        return response.json()

feishu = FeishuClient()

@app.route("/feishu/callback", methods=["POST"])
def feishu_callback():
    """处理飞书事件回调"""
    data = request.json

    # 验证请求来源（URL验证）
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})

    # 验证Token
    if data.get("token") != FEISHU_VERIFICATION_TOKEN:
        return jsonify({"error": "invalid token"}), 401

    # 处理消息卡片回调
    if data.get("type") == "event_callback":
        event = data.get("event", {})

        # 处理按钮点击事件
        if event.get("type") == "card.action.trigger":
            action = event.get("action", {})
            user_id = event.get("user_id", "")

            # 获取benchmark_id
            benchmark_id = action.get("value", {}).get("benchmark_id")

            if benchmark_id:
                # 更新Notion数据库状态
                notion.pages.update(
                    page_id=benchmark_id,
                    properties={
                        "status": {"select": {"name": "已添加"}},
                        "reviewed_by": {"people": [{"id": user_id}]}
                    }
                )

                # 回复确认消息
                chat_id = event.get("open_chat_id")
                confirmation_card = {
                    "msg_type": "text",
                    "content": {
                        "text": f"<at user_id=\"{user_id}\"></at> 已将该Benchmark添加到正式库！"
                    }
                }
                feishu.send_card_message(chat_id, confirmation_card)

    return jsonify({"success": True})

def send_benchmark_notification(benchmark: BenchmarkCandidate, chat_id: str):
    """发送Benchmark通知到飞书群"""
    card = {
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔔 新发现Benchmark: {benchmark.name}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**分类**\n{benchmark.category}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**评分**\n{benchmark.total_score}/10"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**Stars**\n{benchmark.stars}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**许可**\n{benchmark.license}"
                            }
                        }
                    ]
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**推荐理由**\n{benchmark.recommendation}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "一键添加"
                            },
                            "type": "primary",
                            "value": {
                                "benchmark_id": benchmark.id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看详情"
                            },
                            "type": "default",
                            "url": benchmark.notion_url
                        }
                    ]
                }
            ]
        }
    }

    feishu.send_card_message(chat_id, card)

# 启动Flask服务（用于接收飞书回调）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

**飞书机器人配置步骤**：

1. **创建飞书应用**：
   - 访问[飞书开放平台](https://open.feishu.cn/)
   - 创建企业自建应用
   - 获取 App ID 和 App Secret

2. **配置权限**：
   - 添加机器人能力
   - 开通权限：`im:message`, `im:message.group_at_msg`, `im:chat`
   - 配置消息卡片回调地址：`https://your-domain.com/feishu/callback`

3. **订阅事件**：
   - 订阅 `card.action.trigger` 事件（按钮点击）
   - 订阅 `im.message.receive_v1` 事件（接收消息，可选）

4. **部署服务**：
   - 将Flask应用部署到服务器（需要公网IP）
   - 或使用内网穿透工具（如ngrok）用于开发测试

**定期周报生成**：

```python
def generate_weekly_report() -> str:
    """生成周报摘要"""
    candidates = notion.databases.query(
        database_id=database_id,
        filter={
            "property": "added_at",
            "date": {"past_week": {}}
        }
    )

    report = f"""
## 本周Benchmark情报周报（{datetime.now().strftime('%Y-%m-%d')}）

### 新发现
- 本周采集论文: {count_papers}篇
- 新增候选Benchmark: {len(candidates)}个
- 通过预筛选: {len([c for c in candidates if c['total_score'] >= 6])}个

### 热门方向
{generate_category_stats(candidates)}

### 重点推荐
{generate_top_recommendations(candidates, top_n=3)}

### 候选池状态
- 待审核: {count_pending}个
- 已添加: {count_added}个
- 总数: {count_total}个
"""
    return report

def send_weekly_report_to_feishu(chat_id: str):
    """发送周报到飞书群"""
    report_text = generate_weekly_report()

    card = {
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 Benchmark情报周报"
                },
                "template": "turquoise"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": report_text
                    }
                }
            ]
        }
    }

    feishu.send_card_message(chat_id, card)
```

#### 5. 版本跟踪模块 (Version Tracker)

**监控维度**：

- GitHub仓库的release更新
- 论文的arXiv版本更新（v1 → v2）
- Leaderboard榜单的SOTA变化

**实现逻辑**：

```python
def track_benchmark_updates():
    """定期检查已入库Benchmark的更新"""
    benchmarks = get_all_benchmarks_from_notion()

    for bench in benchmarks:
        # 检查GitHub release
        if bench.code_repo:
            latest_release = github.get_latest_release(bench.code_repo)
            if latest_release.version != bench.version:
                send_update_alert(bench, f"新版本发布: {latest_release.version}")

        # 检查arXiv版本
        if bench.paper_url and 'arxiv' in bench.paper_url:
            latest_version = arxiv.get_latest_version(bench.paper_url)
            if latest_version > bench.paper_version:
                send_update_alert(bench, f"论文更新至v{latest_version}")
```

---

## 三、技术栈选型

### 核心技术决策

| 模块 | 技术选型 | 理由 |
|------|---------|------|
| 数据采集 | Python + Requests/httpx | 生态成熟，API库丰富 |
| 结构化抽取 | LangChain + OpenAI/Claude | 降低Prompt工程难度 |
| 数据存储 | Notion/Airtable | 可视化管理，协作友好 |
| 消息推送 | 飞书开放平台SDK | 官方SDK，国内稳定 |
| 任务调度 | GitHub Actions | 轻量级，免运维 |
| 工作流编排 | Python脚本 + Shell | 简单直接，易调试 |

### 为什么不用复杂方案

- **不用Airflow/Prefect**：任务依赖简单，GitHub Actions定时触发足够
- **不用向量数据库**：候选池规模小（< 1000条），Embedding相似度用Numpy计算即可
- **不训练模型**：规则+LLM抽取能解决90%问题，训练模型投入产出比低

### 技术风险与规避

| 风险 | 影响 | 规避方案 |
|------|------|---------|
| API限流 | 采集中断 | 多账号轮询 + 缓存 + 指数退避 |
| LLM不稳定 | 抽取错误 | 规则兜底 + 人工二次校验 |
| Notion API限制 | 写入失败 | 批量写入 + 重试机制 |
| GitHub Actions超时 | 任务失败 | 拆分任务，单次运行<10分钟 |

---

## 四、部署与运维

### 最小可行方案（MVP）

**第一周目标**：跑通arXiv → Notion → 飞书的完整流程

```bash
# 目录结构
benchmark-intelligence-agent/
├── collectors/
│   ├── arxiv_collector.py
│   ├── pwc_collector.py
│   └── github_collector.py
├── filters/
│   ├── scorer.py
│   └── llm_extractor.py
├── storage/
│   └── notion_client.py
├── notifications/
│   └── feishu_bot.py
├── config/
│   ├── sources.yaml
│   └── filters.yaml
├── main.py
└── .github/workflows/daily_run.yml
```

**GitHub Actions配置**：

```yaml
# .github/workflows/daily_run.yml
name: Daily Benchmark Collection

on:
  schedule:
    - cron: '0 2 * * *'  # 每天UTC 2:00执行（北京时间10:00）
  workflow_dispatch:  # 支持手动触发

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run collection
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_CHAT_ID: ${{ secrets.FEISHU_CHAT_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python main.py --mode daily

      - name: Upload logs
        uses: actions/upload-artifact@v3
        with:
          name: collection-logs
          path: logs/
```

### 监控与告警

**关键指标**：

- 每日采集成功率（目标 > 95%）
- 预筛选通过率（目标 10-30%）
- 飞书消息送达率（目标 100%）
- 候选池增长速度（目标 2-5个/周）

**日志记录**：

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

logger = logging.getLogger('BIA')

# 记录关键事件
logger.info(f"采集arXiv: 发现{count}篇新论文")
logger.warning(f"GitHub API限流，等待{retry_after}秒")
logger.error(f"Notion写入失败: {error}")
```

---

## 五、实施计划

### 迭代优先级

**Phase 1（2周）- MVP**：
- 实现arXiv自动采集
- 基础评分引擎（活跃度+可复现性）
- Notion自动入库
- 飞书每日播报

**Phase 2（2周）- 完善预筛选**：
- 集成Papers with Code / GitHub Trending
- LLM辅助信息抽取
- MGX适配度评分
- 一键添加交互按钮

**Phase 3（1周）- 多源覆盖**：
- HuggingFace数据集监控
- AgentBench/HELM榜单跟踪
- Twitter关键词监控

**Phase 4（1周）- 版本跟踪**：
- GitHub release监控
- arXiv版本更新提醒
- Leaderboard变化追踪

### 人力投入估算

- 后端开发：1人 * 4周
- 算法/Prompt工程：0.5人 * 2周
- 测试与调优：0.5人 * 1周

总计：约5-6人周

---

## 六、成功标准

### 量化指标

| 指标 | 现状 | 目标 | 验收标准 |
|------|------|------|---------|
| Benchmark发现速度 | 人工2-3个/月 | 系统10-20个/月 | 持续3个月达标 |
| 信息筛选效率 | 人工阅读200篇论文 | 系统预筛选后阅读20篇 | 噪音过滤率90%+ |
| 入库响应时间 | 发现后1-2周 | 发现后1-3天 | 自动播报延迟<24h |
| 候选池质量 | 无评分标准 | 入库后实际使用率>50% | 追踪3个月数据 |

### 业务价值

- **研究员**：每周节省5-10小时调研时间
- **工程师**：快速了解最新评测标准，加速技术选型
- **管理者**：周报可视化领域趋势，辅助技术规划

---

## 七、风险与应对

### 技术风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| LLM抽取准确率低 | 中 | 中 | 规则兜底 + 人工校验 |
| API限流导致采集中断 | 高 | 低 | 多账号轮询 + 缓存 |
| Notion写入并发限制 | 中 | 低 | 批量写入 + 限速 |
| GitHub Actions免费额度不足 | 低 | 中 | 迁移到内部Cron |

### 业务风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 推送信息过多被忽略 | 中 | 高 | 每日播报限制3-5条，周报汇总 |
| 评分标准不符合实际需求 | 中 | 中 | 每月复盘，调整权重 |
| 团队不习惯使用 | 低 | 高 | 培训 + 试点推广 |

---

## 八、后续扩展方向（非当前需求）

可选的增强功能（按需实施）：

1. **自动生成评测报告**：对比多个模型在新Benchmark上的表现
2. **Benchmark知识图谱**：构建任务、数据集、论文的关系网络
3. **趋势分析仪表板**：可视化不同领域的热度变化曲线
4. **内部评测自动化**：一键触发在新Benchmark上的模型评测任务

---

## 九、总结：为什么这个方案可行

### 三个关键设计

1. **不追求完美自动化**：关键决策（入库确认）保留人工，降低误判风险
2. **从MVP快速迭代**：先跑通arXiv→Notion→飞书，再逐步扩展数据源
3. **技术选型务实**：用成熟工具（Notion/飞书/GitHub Actions）而非从头造轮子

### 核心差异化

- **不是爬虫**：结合LLM智能筛选，不是简单堆砌链接
- **不是数据库**：Notion可视化协作，研究员能直接参与管理
- **不是通知工具**：飞书交互按钮实现人机协同决策

### 预期效果

3个月后，团队能够：
- 每周自动获取10-20个高质量候选Benchmark
- 信息噪音过滤率达到90%以上
- 从"被动搜索"变为"主动推送"
- Benchmark候选池规模扩大3-5倍

这是一个**简单、实用、可持续**的自动化情报系统，而不是一个过度工程化的"AI全自动决策平台"。

---

## 附录：参考资料

### 开源项目参考

1. **ArXivNotificator**：arXiv论文 + Notion + 飞书完整案例（可参考Slack版改造）
2. **arxiv-slack-bot**：arXiv爬取与摘要生成（消息推送可改为飞书）
3. **Infogent**：Navigator-Extractor-Aggregator架构参考
4. **Papers with Code API Client**：榜单数据获取

### API文档

- [arXiv API Basics](https://info.arxiv.org/help/api/basics.html)
- [Notion API Reference](https://developers.notion.com/reference)
- [飞书开放平台文档](https://open.feishu.cn/document/home/index)
- [飞书消息卡片开发指南](https://open.feishu.cn/document/ukTMukTMukTM/uczM3QjL3MzN04yNzcDN)
- [飞书机器人快速开始](https://open.feishu.cn/document/ukTMukTMukTM/uAjMxEjLwITMx4CMyETM)
- [GitHub REST API](https://docs.github.com/en/rest)

### 飞书开发资源

- [飞书Python SDK](https://github.com/larksuite/oapi-sdk-python) - 官方Python SDK
- [飞书消息卡片搭建工具](https://open.feishu.cn/tool/cardbuilder) - 可视化卡片设计
- [飞书开发者社区](https://open.feishu.cn/community) - 问题求助与案例分享
