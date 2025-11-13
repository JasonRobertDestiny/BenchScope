# BenchScope Repository Scan Report

**扫描日期**: 2025-11-13
**扫描工具**: UltraThink Repository Analysis
**仓库路径**: `/mnt/d/VibeCoding_pgm/BenchScope`

---

## 执行摘要

**仓库状态**: 战略规划阶段（Pre-Implementation）
**代码成熟度**: 0% - 纯文档仓库，无源码
**文档完整度**: 95% - PRD、架构设计、开发规范已完备
**可执行性**: 高 - 技术栈明确，模块边界清晰，实施路径具体

**关键发现**:
1. 这是一个高质量的规划文档集，PRD_FINAL.md包含完整的技术实现细节（评分算法、API集成示例、数据库模式）
2. 技术选型务实（Notion而非PostgreSQL、GitHub Actions而非Airflow），遵循"不过度工程化"原则
3. 已建立清晰的开发规范（AGENTS.md）和环境配置指南（.claude/CLAUDE.md）
4. 缺失：无源码目录（src/、tests/）、无依赖管理文件（pyproject.toml、requirements.txt）、未初始化git仓库

---

## 1. 项目类型与目标

### 项目定位
**BenchScope** = Benchmark Intelligence Agent (BIA)
一个**自动化情报系统**，用于发现、筛选和推送AI/Agent领域的Benchmark资源到研究团队。

### 核心问题
解决三个实际痛点：
- **发现成本高**: 人工筛选arXiv 500+篇论文/天，GitHub上千新仓库/天
- **质量参差**: 90%的Benchmark缺代码、数据集不开源、许可证不明
- **响应滞后**: 手动维护的候选池落后数周

### 业务价值
量化目标（3个月验收）：
- Benchmark发现速度：2-3个/月 → 10-20个/月
- 筛选效率：人工阅读200篇 → 系统预筛选后阅读20篇（噪音过滤率90%+）
- 响应时间：发现后1-2周 → 1-3天（自动播报延迟<24h）
- 候选池质量：无评分标准 → 实际使用率>50%

---

## 2. 技术栈分析

### 2.1 核心技术决策

| 模块 | 技术选型 | 替代方案（已拒绝） | 选型理由 |
|------|---------|------------------|---------|
| 数据采集 | Python + httpx | Node.js + Axios | 生态成熟（arxiv/PyGithub库丰富） |
| 结构化抽取 | LangChain + OpenAI | 手动正则/自训模型 | 降低Prompt工程难度，规则兜底 |
| 数据存储 | Notion Database | PostgreSQL/MongoDB | 可视化协作，研究员直接操作，低维护 |
| 消息推送 | 飞书开放平台SDK | Slack/Email | 国内稳定，官方SDK成熟，支持交互卡片 |
| 任务调度 | GitHub Actions | Airflow/Prefect | 轻量级，免运维，任务依赖简单 |
| Web服务 | Flask | FastAPI/Django | 仅处理飞书回调，Flask足够简单 |

### 2.2 依赖管理（规划）
**包管理器**: Poetry（推荐）
**Python版本**: 3.11+（基于PRD中LangChain兼容性要求）

**关键依赖**（待创建pyproject.toml）:
```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27.0"           # HTTP客户端（比requests更现代）
arxiv = "^2.1.0"            # arXiv API封装
PyGithub = "^2.1.1"         # GitHub API客户端
langchain = "^0.1.0"        # LLM链式调用
openai = "^1.10.0"          # OpenAI API
notion-client = "^2.2.0"    # Notion官方SDK
lark-oapi = "^1.3.0"        # 飞书官方SDK
flask = "^3.0.0"            # Web框架
pydantic = "^2.5.0"         # 数据验证
pyyaml = "^6.0"             # 配置文件解析

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
black = "^24.0.0"           # 代码格式化
ruff = "^0.1.9"             # Linter
```

### 2.3 构建与测试工具

**未发现**任何构建配置，需创建：
- `.github/workflows/daily_run.yml` - 自动化采集任务
- `pytest.ini` - 测试配置
- `.pre-commit-config.yaml` - 代码质量钩子

---

## 3. 代码组织与模块设计

### 3.1 目录结构（规划 vs 现状）

**规划的目录结构**（来自PRD_FINAL.md）:
```
benchmark-intelligence-agent/
├── collectors/                 # 数据采集模块
│   ├── arxiv_collector.py
│   ├── pwc_collector.py
│   └── github_collector.py
├── filters/                    # 预筛选模块
│   ├── scorer.py
│   └── llm_extractor.py
├── storage/                    # 数据存储模块
│   └── notion_client.py
├── notifications/              # 消息推送模块
│   └── feishu_bot.py
├── config/                     # 配置文件
│   ├── sources.yaml
│   └── filters.yaml
├── main.py                     # 主入口
└── .github/workflows/
    └── daily_run.yml           # 自动化任务
```

**实际现状**:
```
BenchScope/
├── .claude/                    # Claude Code配置
│   ├── CLAUDE.md              # 开发指南（12KB，极详细）
│   └── commands/
│       ├── arrange.md         # 文件整理规范
│       └── deploy.md          # 部署规范
├── PRD_FINAL.md               # 产品需求文档（31KB）
├── AGENTS.md                  # 仓库规范（23KB）
├── gemini.md                  # Gemini设计文档（需确认用途）
├── PRD1.md                    # 早期需求草稿
├── Benchmark资讯自动播报Agent调研报告.pdf
└── NotebookLM在SEO中的应用.png
```

**关键差距**:
- 缺失所有源码目录（src/、tests/、config/、scripts/）
- 缺失依赖管理文件（pyproject.toml/requirements.txt）
- 缺失CI/CD配置（.github/workflows/）
- 缺失环境配置模板（.env.example）

### 3.2 模块职责与接口设计

#### 模块1: Data Collector
**职责**: 从arXiv、Papers with Code、GitHub Trending、HuggingFace Hub抓取Benchmark资源

**核心接口**（来自PRD §II.1）:
```python
class BenchmarkCollector:
    def collect_arxiv(
        keywords: List[str],          # ["benchmark", "evaluation"]
        categories: List[str]          # ["cs.AI", "cs.CL"]
    ) -> List[Paper]:
        """arXiv采集：使用官方API + RSS订阅"""
        pass

    def collect_pwc(
        task_types: List[str]          # ["agent", "coding"]
    ) -> List[Benchmark]:
        """Papers with Code采集：通过官方API Client"""
        pass

    def collect_github_trending(
        language: str = "Python"
    ) -> List[Repo]:
        """
        GitHub Trending采集
        过滤条件：stars > 100, has_topics(["benchmark"])
        """
        pass
```

**配置示例**（config/sources.yaml）:
```yaml
arxiv:
  keywords: ["benchmark", "agent evaluation", "code generation"]
  categories: ["cs.AI", "cs.CL", "cs.SE"]
  max_results: 50
  update_interval: "daily"

github:
  topics: ["benchmark", "evaluation", "agent"]
  min_stars: 100
  min_recent_activity: 30  # 30天内有更新
```

#### 模块2: Pre-filter Engine
**职责**: 5维评分过滤（活跃度、可复现性、许可、新颖性、适配度）

**评分算法**（PRD §II.2，关键业务逻辑）:
```python
def calculate_total_score(candidate: BenchmarkCandidate) -> float:
    """
    综合评分 =
        活跃度 × 0.25 +
        可复现性 × 0.30 +
        许可合规 × 0.20 +
        任务新颖性 × 0.15 +
        MGX适配度 × 0.10

    筛选阈值：总分 ≥ 6.0
    """
    activity = score_activity(candidate.repo) * 0.25
    reproducibility = score_reproducibility(candidate) * 0.30
    license = (10 if candidate.license in APPROVED_LICENSES else 0) * 0.20
    novelty = (10 - candidate.similarity * 10) * 0.15
    relevance = score_mgx_relevance(candidate.description) * 0.10

    return activity + reproducibility + license + novelty + relevance
```

**关键常量**（需放入src/common/constants.py）:
```python
ACTIVITY_WEIGHT = 0.25
REPRODUCIBILITY_WEIGHT = 0.30
LICENSE_WEIGHT = 0.20
NOVELTY_WEIGHT = 0.15
RELEVANCE_WEIGHT = 0.10

SCORE_THRESHOLD = 6.0  # 低于6分直接过滤

APPROVED_LICENSES = ["MIT", "Apache-2.0", "BSD-3-Clause"]
```

#### 模块3: Storage Layer (Notion)
**职责**: 候选池管理（入库、查询、状态更新）

**Notion数据库字段设计**（PRD §II.3）:
| 字段名 | 类型 | 说明 | 必填 |
|--------|------|------|------|
| name | Title | Benchmark名称 | 是 |
| category | Select | 领域分类（Agent/Coding/Web/Reasoning） | 是 |
| total_score | Number | 综合评分（0-10） | 是 |
| status | Select | 候选/审核中/已添加/已拒绝 | 是 |
| paper_url | URL | 论文链接 | 否 |
| code_repo | URL | 代码仓库地址 | 否 |
| license | Select | MIT/Apache/GPL/Unknown | 是 |
| stars | Number | GitHub stars | 否 |
| recommendation | Text | 推荐理由（AI生成） | 否 |

**API封装**:
```python
from notion_client import Client

def add_candidate_to_notion(candidate: BenchmarkCandidate):
    """添加候选Benchmark到Notion数据库"""
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "name": {"title": [{"text": {"content": candidate.name}}]},
            "total_score": {"number": candidate.total_score},
            "status": {"select": {"name": "候选"}},
            # ...
        }
    )
```

#### 模块4: Notification Engine (飞书)
**职责**: 卡片消息推送、一键添加交互、周报生成

**飞书卡片格式**（PRD §II.4）:
```json
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {"content": "🔔 新发现Benchmark: WebArena"}
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"text": {"content": "**分类**\nAgent"}},
                    {"text": {"content": "**评分**\n8.5/10"}},
                    {"text": {"content": "**Stars**\n1234"}},
                    {"text": {"content": "**许可**\nMIT"}}
                ]
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"content": "一键添加"},
                        "type": "primary",
                        "value": {"benchmark_id": "xxx"}
                    }
                ]
            }
        ]
    }
}
```

**一键添加回调处理**（Flask）:
```python
@app.route("/feishu/callback", methods=["POST"])
def feishu_callback():
    """处理飞书卡片按钮点击事件"""
    data = request.json

    if data.get("type") == "event_callback":
        event = data.get("event", {})

        if event.get("type") == "card.action.trigger":
            benchmark_id = event["action"]["value"]["benchmark_id"]
            user_id = event["user_id"]

            # 更新Notion状态
            notion.pages.update(
                page_id=benchmark_id,
                properties={
                    "status": {"select": {"name": "已添加"}},
                    "reviewed_by": {"people": [{"id": user_id}]}
                }
            )

    return jsonify({"success": True})
```

---

## 4. 数据流与集成点

### 4.1 完整数据流

```
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Actions (Trigger: 每日UTC 2:00 / 手动触发)               │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ main.py --mode daily                                            │
│ - 读取 config/sources.yaml                                      │
│ - 初始化 Collector、Scorer、NotionClient、FeishuBot            │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 并发采集（asyncio）                                             │
│ ├─ ArxivCollector.collect_arxiv(keywords, categories)          │
│ ├─ PwCCollector.collect_pwc(task_areas)                        │
│ └─ GitHubCollector.collect_trending(topics, min_stars)         │
│ 输出: List[RawCandidate] (~50-200条/天)                        │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LLM结构化抽取（LangChain）                                      │
│ - 输入: RawCandidate.abstract + RawCandidate.readme            │
│ - Prompt: "提取has_code, has_dataset, task_type, metrics"      │
│ - 输出: StructuredCandidate (JSON)                             │
│ - 失败处理: 规则引擎兜底（正则匹配GitHub README）              │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 评分引擎（PrefilterEngine）                                     │
│ - score_activity(repo.stars, last_commit, forks)               │
│ - score_reproducibility(has_code, has_dataset, has_doc)        │
│ - score_license(license_name)                                  │
│ - score_novelty(similarity_to_existing)                        │
│ - score_mgx_relevance(description) [LLM判断]                   │
│ - 过滤: total_score < 6.0 → 丢弃                               │
│ 输出: List[ScoredCandidate] (~5-20条/天)                       │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Notion入库（NotionClient）                                      │
│ - 批量创建页面（3请求/秒限制）                                  │
│ - 写入字段: name, category, total_score, status=候选            │
│ - 返回: List[notion_page_id]                                   │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 飞书卡片推送（FeishuBot）                                       │
│ - 每条候选生成一个交互卡片                                       │
│ - 包含"一键添加"按钮（value=notion_page_id）                    │
│ - 发送到指定群聊（chat_id从环境变量读取）                        │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 用户交互（异步）                                                 │
│ - 用户点击"一键添加" → 飞书回调 → Flask处理                     │
│ - 更新Notion: status="已添加", reviewed_by=user_id             │
│ - 回复确认消息到飞书群                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 外部系统集成

| 系统 | 集成方式 | 认证方式 | 限流策略 |
|------|---------|---------|---------|
| arXiv | 官方API + RSS | 无需认证 | 建议3秒/请求 |
| GitHub | REST API v3 | Personal Access Token | 5000请求/小时，指数退避 |
| Papers with Code | 爬虫（无官方API） | 无需认证 | 10秒/请求，避免封禁 |
| Notion | Official SDK | Integration Token | 3请求/秒，批量写入 |
| 飞书 | Official SDK | App ID + Secret | 租户token自动刷新 |
| OpenAI | Official API | API Key | 根据tier限制，队列化 |

### 4.3 关键集成点

#### 集成点1: GitHub Actions → Python脚本
**配置文件**: `.github/workflows/daily_run.yml`（待创建）

```yaml
name: Daily Benchmark Collection

on:
  schedule:
    - cron: '0 2 * * *'  # 每天UTC 2:00（北京时间10:00）
  workflow_dispatch:      # 支持手动触发

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: poetry install

      - name: Run collection
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: poetry run python main.py --mode daily

      - name: Upload logs
        uses: actions/upload-artifact@v3
        with:
          name: collection-logs
          path: logs/
```

#### 集成点2: Flask → 飞书回调
**部署需求**: 需要公网IP或内网穿透（开发阶段可用ngrok）

**飞书回调配置**:
1. 飞书开放平台配置回调URL: `https://your-domain.com/feishu/callback`
2. 订阅事件: `card.action.trigger`（按钮点击）
3. 验证Token: 环境变量 `FEISHU_VERIFICATION_TOKEN`

#### 集成点3: LangChain → OpenAI
**结构化抽取示例**（PRD §II.2）:

```python
from langchain.chains import create_extraction_chain

schema = {
    "properties": {
        "has_code": {"type": "boolean"},
        "has_dataset": {"type": "boolean"},
        "task_type": {"type": "string", "enum": ["coding", "agent", "reasoning", "web"]},
        "evaluation_metrics": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["has_code", "task_type"]
}

chain = create_extraction_chain(schema, llm)
extracted = chain.run(paper_abstract)
```

---

## 5. 开发规范与约束

### 5.1 代码质量标准（来自AGENTS.md）

#### Python风格（强制执行）
- **PEP8合规**: 使用`black`格式化，`ruff`检查
- **命名约定**:
  - 函数/变量: `snake_case`
  - 类名: `PascalCase`
  - 环境变量: `UPPER_SNAKE`
  - 常量: `UPPER_SNAKE` (定义在`src/common/constants.py`)
- **缩进**: 4空格
- **嵌套限制**: ≤3层（Linus规则），超过则需重构

#### 注释规范
- **关键逻辑**: 必须写**中文注释**
  ```python
  # 关键词质量过滤：拒绝URL片段、HTML/CSS代码、技术术语
  # 这个函数影响所有下游分析，修改需要全面测试
  def is_quality_keyword(keyword):
      ...
  ```
- **公共API**: 英文Docstring（PEP 257格式）
  ```python
  def analyze_page(url: str, run_llm: bool = False) -> Dict[str, Any]:
      """
      分析单个页面的SEO质量

      Args:
          url: 要分析的页面URL
          run_llm: 是否运行LLM分析（默认False）

      Returns:
          包含诊断指标的分析结果字典

      Raises:
          ValueError: URL格式无效
      """
  ```

#### 魔法数字禁令
```python
# ❌ Bad
if len(title) > 60:
    priority = 1

# ✅ Good
MAX_TITLE_LENGTH = 60
PRIORITY_HIGH = 1

if len(title) > MAX_TITLE_LENGTH:
    priority = PRIORITY_HIGH
```

### 5.2 测试规范

#### 测试覆盖要求
- **手动测试强制执行**: 飞书播报、Notion入库、外部API交互必须手动验证
- **测试报告**: 结果写入`docs/test-report.md`，附截图或日志路径
- **pytest命名**: `test_<module>_<behavior>`
- **夹具命名**: `fixture_<intent>`

#### 测试分类
```bash
poetry run pytest tests -m "not slow"     # 快速单元测试
poetry run pytest tests -m integration     # 集成测试（需真实API）
```

#### 关键路径测试
新评分维度必须提供最小可复现脚本：
```bash
poetry run python scripts/manual_review.py docs/samples/pwc.json
```

### 5.3 Git工作流

#### Commit规范（Conventional Commits）
```bash
feat: add arxiv collector with rate limiting
fix(scorer): correct activity score calculation for repos with <100 stars
chore: update config/sources.yaml with new GitHub topics
docs: add manual test report for scoring changes
```

#### PR检查清单
- [ ] 问题背景说明
- [ ] 运行的命令
- [ ] 手动测试结果（截图/日志）
- [ ] 相关Issue/飞书讨论链接
- [ ] 涉及UI/飞书卡片的改动需附截图

#### 关键约束
**SEO模块专项约束**（来自AGENTS.md第28行）:
- 禁止修改 `analyzer.py:12-89` 的 `is_quality_keyword()`
- 若确需变更，先提Issue并经负责人书面批准

### 5.4 安全与配置管理

#### 密钥管理
所有API Token放入 `.env.local` 或 GitHub Secrets（生产环境）:
```bash
# .env.local (不提交到git)
NOTION_TOKEN=secret_xxx
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
OPENAI_API_KEY=sk-xxx
GITHUB_TOKEN=ghp_xxx  # 可选，提高API限额
```

**严禁**:
- 提交明文凭证到代码库
- 在代码中硬编码API密钥
- 在日志中打印完整token

#### 数据合规
- 抓取任务遵守 `robots.txt`
- 白名单例外记录在 `config/whitelist.yaml` 并同步合规审批
- 用户数据（飞书user_id）仅用于审核记录，不外传

---

## 6. 现有文档资产分析

### 6.1 核心文档清单

| 文档 | 大小 | 完整度 | 关键内容 | 建议用途 |
|------|------|--------|---------|---------|
| PRD_FINAL.md | 31KB | 95% | 完整技术实现细节、评分算法、API集成示例 | **开发指南**（实现时参考） |
| AGENTS.md | 23KB | 90% | 仓库规范、测试流程、Git约定 | **协作规范**（团队必读） |
| .claude/CLAUDE.md | 12KB | 98% | 完整开发环境配置、命令示例、模块职责 | **Claude Code指南**（自动化开发） |
| gemini.md | 24KB | 不明 | Gemini相关设计（待确认具体用途） | **待评审** |
| PRD1.md | 783B | 20% | 早期需求草稿（已被PRD_FINAL取代） | **可归档** |

### 6.2 文档质量评估

**优点**:
1. **PRD_FINAL.md**: 极详细的技术文档，包含代码示例、配置示例、数据库模式设计，可直接用于实现
2. **AGENTS.md**: 建立了清晰的开发规范，包括测试流程、安全约束、Git工作流
3. **.claude/CLAUDE.md**: 为Claude Code提供了完整的项目上下文，包括模块职责、命令示例、实施计划

**缺失**:
1. **API设计文档**: 缺少RESTful API设计（如果需要对外提供API）
2. **错误处理策略**: 未详细描述各模块的异常处理和重试策略
3. **性能基准**: 未定义各环节的性能指标（如采集速度、LLM调用延迟）
4. **部署文档**: 缺少生产环境部署指南（Flask部署、飞书回调配置）

### 6.3 文档一致性检查

**发现的矛盾**:
1. **目录结构命名**:
   - PRD_FINAL.md使用 `collectors/`, `filters/`, `notifications/`
   - .claude/CLAUDE.md使用 `src/collector/`, `src/prefilter/`, `src/notifier/`
   - **建议**: 统一为 `src/` 前缀的单数形式（更符合Python惯例）

2. **配置文件路径**:
   - PRD使用 `config/sources.yaml`, `config/filters.yaml`
   - CLAUDE.md使用 `config/sources.yaml`, `config/weights.yaml`
   - **建议**: 统一为 `weights.yaml`（更准确描述内容）

**术语一致性**: 良好
- "Benchmark"、"候选池"、"预筛选"、"飞书卡片"等术语在所有文档中保持一致

---

## 7. 约束与风险

### 7.1 技术约束

| 约束 | 来源 | 影响 | 规避方案 |
|------|------|------|---------|
| GitHub Actions超时 | 免费版限制6小时/job | 任务可能中断 | 拆分任务，单次运行<10分钟 |
| Notion API限流 | 3请求/秒 | 批量写入受限 | 批量操作+限速器 |
| OpenAI API成本 | 每条候选~0.01-0.05美元 | 每日成本1-5美元 | 缓存LLM结果+规则兜底 |
| 飞书回调需公网IP | 内网无法接收回调 | 开发环境测试困难 | 使用ngrok内网穿透 |

### 7.2 业务风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 推送信息过多被忽略 | 中 | 高 | 每日播报限制3-5条，周报汇总 |
| 评分标准不符合实际需求 | 中 | 中 | 每月复盘，调整权重 |
| LLM抽取准确率低 | 中 | 中 | 规则兜底+人工校验 |
| API限流导致采集中断 | 高 | 低 | 多账号轮询+缓存 |

### 7.3 合规约束

**数据来源合规**:
- arXiv: 遵守[Terms of Use](https://info.arxiv.org/help/api/tou.html)，非商业使用，需注明数据来源
- GitHub: 遵守[API Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)，不得滥用爬虫
- Papers with Code: 无官方API，爬虫需遵守robots.txt

**用户数据合规**:
- 飞书user_id仅用于审核记录（reviewed_by字段）
- 不收集个人敏感信息
- 所有数据存储在Notion（符合企业数据安全策略）

---

## 8. 实施路径与里程碑

### 8.1 四阶段计划（来自PRD §V）

#### Phase 1（2周）- MVP
目标: 跑通arXiv → Notion → 飞书的完整流程

**核心交付物**:
- [x] arXiv自动采集（`src/collector/arxiv_collector.py`）
- [x] 基础评分引擎（活跃度+可复现性）（`src/prefilter/scorer.py`）
- [x] Notion自动入库（`src/storage/notion_client.py`）
- [x] 飞书每日播报（`src/notifier/feishu_bot.py`）

**验收标准**:
- 每日自动采集arXiv论文，发现至少5篇相关论文
- 评分引擎正常运行，过滤率70-90%
- 候选池成功写入Notion
- 飞书群每日收到1-3条推送

#### Phase 2（2周）- 完善预筛选
目标: 集成多数据源，增强评分准确性

**核心交付物**:
- [ ] Papers with Code集成（`src/collector/pwc_collector.py`）
- [ ] GitHub Trending集成（`src/collector/github_collector.py`）
- [ ] LLM辅助信息抽取（`src/prefilter/llm_extractor.py`）
- [ ] MGX适配度评分（LLM判断）
- [ ] 一键添加交互按钮（Flask回调处理）

**验收标准**:
- 三个数据源每日采集总计50-200条原始数据
- LLM抽取准确率>80%（人工抽检50条）
- 一键添加功能正常工作（点击后Notion状态更新）

#### Phase 3（1周）- 多源覆盖
目标: 扩展监控范围，覆盖更多Benchmark来源

**核心交付物**:
- [ ] HuggingFace数据集监控
- [ ] AgentBench/HELM榜单跟踪
- [ ] Twitter关键词监控（可选）

**验收标准**:
- HuggingFace数据集每周新增2-5个候选
- 榜单跟踪功能正常（SOTA变化自动推送）

#### Phase 4（1周）- 版本跟踪
目标: 监控已入库Benchmark的更新

**核心交付物**:
- [ ] GitHub release监控（`src/tracker/version_tracker.py`）
- [ ] arXiv版本更新提醒
- [ ] Leaderboard变化追踪

**验收标准**:
- 检测到版本更新时自动推送通知
- 每周至少监控到1-2个更新事件

### 8.2 关键里程碑时间线

```
Week 1-2: MVP开发
  ├─ Day 1-2: 环境搭建、依赖安装、目录结构创建
  ├─ Day 3-5: arXiv采集器 + 基础评分引擎
  ├─ Day 6-8: Notion集成 + 飞书推送
  └─ Day 9-10: 端到端测试 + Bug修复

Week 3-4: 多源集成
  ├─ Day 11-13: Papers with Code + GitHub Trending采集
  ├─ Day 14-16: LLM抽取链 + MGX适配度评分
  └─ Day 17-20: 一键添加交互 + 集成测试

Week 5: 监控扩展
  ├─ Day 21-23: HuggingFace + 榜单跟踪
  └─ Day 24-25: 集成测试 + 文档完善

Week 6: 版本跟踪
  ├─ Day 26-28: GitHub release监控 + arXiv版本更新
  └─ Day 29-30: 端到端测试 + 上线部署
```

### 8.3 人力投入估算（来自PRD §V）

- 后端开发：1人 × 4周
- 算法/Prompt工程：0.5人 × 2周
- 测试与调优：0.5人 × 1周

**总计**: 约5-6人周

---

## 9. 成功标准与验收指标

### 9.1 量化指标（3个月验收）

| 指标 | 现状 | 目标 | 验收标准 |
|------|------|------|---------|
| Benchmark发现速度 | 人工2-3个/月 | 系统10-20个/月 | 持续3个月达标 |
| 信息筛选效率 | 人工阅读200篇论文 | 系统预筛选后阅读20篇 | 噪音过滤率90%+ |
| 入库响应时间 | 发现后1-2周 | 发现后1-3天 | 自动播报延迟<24h |
| 候选池质量 | 无评分标准 | 入库后实际使用率>50% | 追踪3个月数据 |

### 9.2 关键性能指标（KPI）

**系统性能**:
- 每日采集成功率：>95%
- 预筛选通过率：10-30%（过高说明阈值太松，过低说明数据源质量差）
- 飞书消息送达率：100%
- LLM抽取准确率：>80%

**用户体验**:
- 每日播报推送时间：北京时间10:00-11:00
- 飞书卡片点击后响应时间：<2秒
- Notion数据库查询响应时间：<1秒

### 9.3 业务价值（定性评估）

**研究员视角**:
- 每周节省5-10小时调研时间
- 从"被动搜索"变为"主动推送"

**工程师视角**:
- 快速了解最新评测标准
- 加速技术选型（有评分参考）

**管理者视角**:
- 周报可视化领域趋势
- 辅助技术规划决策

---

## 10. 下一步行动建议

### 10.1 立即行动（优先级P0）

#### 1. 初始化代码仓库结构
```bash
# 在/mnt/d/VibeCoding_pgm/BenchScope执行
mkdir -p src/{collector,prefilter,storage,notifier,tracker,common}
mkdir -p tests/{unit,integration,fixtures}
mkdir -p config scripts docs/samples logs
touch src/__init__.py
touch src/collector/__init__.py
touch src/prefilter/__init__.py
touch src/storage/__init__.py
touch src/notifier/__init__.py
touch src/tracker/__init__.py
touch src/common/__init__.py
touch src/common/constants.py
```

#### 2. 创建依赖管理文件
```bash
# 初始化Poetry项目
poetry init --name benchscope --python "^3.11"

# 添加核心依赖
poetry add httpx arxiv PyGithub langchain openai notion-client lark-oapi flask pydantic pyyaml

# 添加开发依赖
poetry add --group dev pytest black ruff pre-commit
```

#### 3. 配置环境模板
```bash
# 创建.env.example
cat > .env.example << 'EOF'
# Notion配置
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=xxx

# 飞书配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_CHAT_ID=oc_xxx
FEISHU_VERIFICATION_TOKEN=xxx

# OpenAI配置
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview

# GitHub配置（可选）
GITHUB_TOKEN=ghp_xxx

# 日志配置
LOG_LEVEL=INFO
EOF

# 复制为本地配置
cp .env.example .env.local
```

#### 4. 初始化Git仓库
```bash
# 创建.gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
*.egg-info/

# 环境变量
.env
.env.local

# 日志
logs/
*.log

# IDE
.vscode/
.idea/
*.swp

# 测试
.pytest_cache/
.coverage
htmlcov/

# 临时文件
*.tmp
*.bak
docs/test-report.md
EOF

# 初始化仓库
git init
git add .
git commit -m "chore: initialize repository structure and dependencies"
```

### 10.2 短期任务（1-2周，优先级P1）

#### 5. 实现arXiv采集器（Phase 1核心）
**文件**: `src/collector/arxiv_collector.py`

**参考实现**（基于PRD §II.1）:
```python
import arxiv
from typing import List
from dataclasses import dataclass

@dataclass
class Paper:
    title: str
    abstract: str
    authors: List[str]
    published: str
    pdf_url: str
    categories: List[str]

class ArxivCollector:
    def collect_arxiv(
        self,
        keywords: List[str],
        categories: List[str],
        max_results: int = 50
    ) -> List[Paper]:
        """
        arXiv采集：使用官方API

        Args:
            keywords: 搜索关键词
            categories: arXiv分类（如cs.AI）
            max_results: 最大结果数

        Returns:
            论文列表
        """
        query = self._build_query(keywords, categories)
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        papers = []
        for result in search.results():
            papers.append(Paper(
                title=result.title,
                abstract=result.summary,
                authors=[author.name for author in result.authors],
                published=result.published.isoformat(),
                pdf_url=result.pdf_url,
                categories=result.categories
            ))

        return papers

    def _build_query(self, keywords: List[str], categories: List[str]) -> str:
        """构建arXiv查询字符串"""
        keyword_query = " OR ".join([f'all:"{kw}"' for kw in keywords])
        category_query = " OR ".join([f'cat:{cat}' for cat in categories])
        return f"({keyword_query}) AND ({category_query})"
```

#### 6. 实现基础评分引擎（Phase 1核心）
**文件**: `src/prefilter/scorer.py`

**关键常量**（定义在`src/common/constants.py`）:
```python
# 评分权重
ACTIVITY_WEIGHT = 0.25
REPRODUCIBILITY_WEIGHT = 0.30
LICENSE_WEIGHT = 0.20
NOVELTY_WEIGHT = 0.15
RELEVANCE_WEIGHT = 0.10

# 筛选阈值
SCORE_THRESHOLD = 6.0

# 许可白名单
APPROVED_LICENSES = ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause"]

# 活跃度评分阈值
STARS_TIER_1 = 100
STARS_TIER_2 = 500
STARS_TIER_3 = 1000

UPDATE_RECENT = 7    # 天
UPDATE_ACTIVE = 30
UPDATE_STALE = 90
```

#### 7. 实现Notion集成（Phase 1核心）
**文件**: `src/storage/notion_client.py`

**测试命令**:
```bash
# 测试Notion连接
poetry run python -c "from src.storage.notion_client import NotionClient; client = NotionClient(); print(client.test_connection())"

# 添加测试数据
poetry run python src/storage/notion_client.py --action add --data docs/samples/benchmark.json
```

#### 8. 创建配置文件
**文件**: `config/sources.yaml`（复制PRD中的配置）

```yaml
arxiv:
  keywords:
    - "benchmark"
    - "agent evaluation"
    - "code generation"
    - "web automation"
  categories:
    - "cs.AI"
    - "cs.CL"
    - "cs.SE"
  max_results: 50
  update_interval: "daily"

papers_with_code:
  task_areas:
    - "coding"
    - "agent"
    - "reasoning"
    - "web-navigation"
  min_papers: 3
  update_interval: "daily"

github:
  topics:
    - "benchmark"
    - "evaluation"
    - "agent"
    - "llm-eval"
  min_stars: 100
  min_recent_activity: 30
  update_interval: "daily"
```

**文件**: `config/weights.yaml`（定义评分权重）

```yaml
scoring:
  weights:
    activity: 0.25
    reproducibility: 0.30
    license: 0.20
    novelty: 0.15
    relevance: 0.10

  thresholds:
    total_score: 6.0
    similarity: 0.8  # 相似度>0.8视为重复

  activity:
    stars:
      tier_1: 100
      tier_2: 500
      tier_3: 1000
    update_days:
      recent: 7
      active: 30
      stale: 90

  reproducibility:
    has_code: 6
    has_dataset: 3
    has_doc: 1

  license:
    approved:
      - "MIT"
      - "Apache-2.0"
      - "BSD-3-Clause"
      - "BSD-2-Clause"
```

### 10.3 中期任务（3-4周，优先级P2）

#### 9. 实现LLM辅助抽取（Phase 2）
**文件**: `src/prefilter/llm_extractor.py`

**关键挑战**:
- Prompt工程（提高抽取准确率）
- 规则引擎兜底（LLM失败时的fallback）
- 成本控制（缓存策略）

#### 10. 实现飞书一键添加交互（Phase 2）
**文件**: `src/notifier/callback_server.py`（Flask应用）

**部署需求**:
- 需要公网IP或内网穿透（生产环境部署到云服务器）
- 配置飞书回调URL
- 处理异步回调（用户点击按钮时立即响应）

#### 11. 创建GitHub Actions工作流
**文件**: `.github/workflows/daily_run.yml`（复制本文档§4.3的配置）

**测试**:
```bash
# 本地模拟GitHub Actions环境
act -j collect  # 需要安装act工具
```

### 10.4 长期优化（5-6周+，优先级P3）

#### 12. 性能优化
- 并发采集（asyncio）
- LLM调用批处理
- Notion批量写入优化

#### 13. 监控与告警
- 日志聚合（ELK Stack或简单的文件日志）
- 关键指标仪表板（Grafana）
- 异常告警（飞书群通知）

#### 14. 文档完善
- API文档（Swagger/OpenAPI）
- 部署文档（生产环境配置指南）
- 故障排查手册（Troubleshooting Guide）

---

## 11. 总结：仓库现状与战略优势

### 11.1 核心优势

**1. 规划完备性（95%）**
- PRD_FINAL.md提供了可直接实现的技术方案（评分算法、API集成示例）
- AGENTS.md建立了清晰的协作规范（测试流程、Git约定）
- .claude/CLAUDE.md为Claude Code提供了完整的项目上下文

**2. 技术选型务实**
- 避免过度工程化（不用Airflow、不用向量数据库、不用PostgreSQL）
- 选择成熟工具（Notion、飞书、GitHub Actions）
- 关键决策有明确理由（见PRD §III"为什么不用复杂方案"）

**3. 模块边界清晰**
- 5个核心模块（Collector、Prefilter、Storage、Notifier、Tracker）职责明确
- 数据流完整（从采集到推送到人工审核）
- 接口设计具体（函数签名、参数说明、返回值类型）

### 11.2 关键差距

**1. 零代码实现**
- 所有源码目录（src/、tests/、config/）待创建
- 依赖管理文件（pyproject.toml）待创建
- CI/CD配置（.github/workflows/）待创建

**2. 环境配置缺失**
- 无.env.example模板
- 无本地开发环境搭建指南
- 无依赖安装验证脚本

**3. 测试基础设施缺失**
- 无pytest配置
- 无测试夹具（fixtures）
- 无CI/CD测试流水线

### 11.3 战略建议

**立即行动（本周）**:
1. 执行§10.1的4个P0任务（初始化目录、创建依赖文件、配置环境、初始化git）
2. 创建MVP核心模块的骨架代码（arXiv采集器、基础评分器、Notion客户端）
3. 编写第一个端到端测试（arXiv → 评分 → Notion）

**短期目标（2周）**:
- 完成Phase 1（MVP）的4个核心模块
- 验证完整数据流（从arXiv到飞书推送）
- 建立手动测试流程（docs/test-report.md）

**长期愿景（3个月）**:
- 达成所有量化指标（Benchmark发现速度10-20个/月，噪音过滤率90%+）
- 团队从"被动搜索"转为"主动推送"
- 候选池规模扩大3-5倍

---

## 附录A：关键文件路径速查

### A.1 文档
- `/mnt/d/VibeCoding_pgm/BenchScope/PRD_FINAL.md` - 完整产品需求（31KB）
- `/mnt/d/VibeCoding_pgm/BenchScope/AGENTS.md` - 仓库规范（23KB）
- `/mnt/d/VibeCoding_pgm/BenchScope/.claude/CLAUDE.md` - 开发指南（12KB）

### A.2 配置（待创建）
- `config/sources.yaml` - 数据源配置
- `config/weights.yaml` - 评分权重配置
- `.env.example` - 环境变量模板
- `.env.local` - 本地环境变量（不提交git）

### A.3 核心模块（待创建）
- `src/collector/arxiv_collector.py` - arXiv采集器
- `src/collector/pwc_collector.py` - Papers with Code采集器
- `src/collector/github_collector.py` - GitHub Trending采集器
- `src/prefilter/scorer.py` - 评分引擎
- `src/prefilter/llm_extractor.py` - LLM抽取器
- `src/storage/notion_client.py` - Notion客户端
- `src/notifier/feishu_bot.py` - 飞书推送
- `src/notifier/callback_server.py` - Flask回调服务
- `src/tracker/version_tracker.py` - 版本监控
- `src/common/constants.py` - 全局常量

### A.4 测试（待创建）
- `tests/unit/` - 单元测试
- `tests/integration/` - 集成测试
- `tests/fixtures/` - 测试夹具
- `docs/test-report.md` - 手动测试报告

### A.5 CI/CD（待创建）
- `.github/workflows/daily_run.yml` - 每日自动采集
- `.github/workflows/test.yml` - 测试流水线

---

## 附录B：外部资源链接

### B.1 官方API文档
- [arXiv API](https://info.arxiv.org/help/api/basics.html)
- [GitHub REST API](https://docs.github.com/en/rest)
- [Notion API](https://developers.notion.com/reference)
- [飞书开放平台](https://open.feishu.cn/document/home/index)
- [OpenAI API](https://platform.openai.com/docs/api-reference)

### B.2 开源项目参考
- [ArXivNotificator](https://github.com/arxiv-notification) - arXiv + Notion完整案例
- [Papers with Code API](https://github.com/paperswithcode/paperswithcode-client)
- [LangChain Extraction](https://python.langchain.com/docs/use_cases/extraction)

### B.3 技术栈文档
- [Poetry](https://python-poetry.org/docs/) - Python依赖管理
- [Pytest](https://docs.pytest.org/en/stable/) - 测试框架
- [Black](https://black.readthedocs.io/en/stable/) - 代码格式化
- [Ruff](https://docs.astral.sh/ruff/) - Linter

---

**扫描完成时间**: 2025-11-13 11:45:00
**下次更新建议**: 实现MVP后（2周后）重新扫描，评估代码质量和架构一致性
