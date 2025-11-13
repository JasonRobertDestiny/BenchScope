# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Workflow & Roles

**重要：本项目采用双Agent协作模式**

### 角色分工

| 角色 | 职责 | 交付物 |
|------|------|--------|
| **Claude Code** (你) | 产品规划、架构设计、开发指令文档编写、**测试执行**、进度监督、验收 | PRD、系统架构、开发prompt文档、测试报告、验收标准 |
| **Codex** | 根据Claude Code提供的文档进行具体编码实现 | 源代码、实现文档 |

### 工作流程

```
用户需求
    ↓
Claude Code分析需求 → 编写PRD → 设计架构 → 编写详细开发指令文档
    ↓
Codex阅读开发指令 → 编写代码 → 实现功能
    ↓
Claude Code执行测试 → 单元测试 + 集成测试 + 手动测试 → 记录测试报告
    ↓
Claude Code验收 → 检查是否符合文档规范 → 通过/打回修改
    ↓
交付用户
```

### 开发指令文档位置

Claude Code编写的所有开发指令文档统一放在:
- `.claude/specs/benchmark-intelligence-agent/` 目录
- 文档命名规范:
  - `PHASE{N}-PROMPT.md` - 阶段总体指令
  - `CODEX-{PHASE}-DETAILED.md` - 详细实现代码+测试用例
  - `CODEX-URGENT-FIXES.md` - 紧急修复指令

### Codex实施要求

**强制执行**:
1. Codex必须**严格按照**开发指令文档实现，不得自行修改设计
2. 如遇到文档不清晰的地方，必须先询问Claude Code，不得自行猜测
3. **不需要编写测试代码** - 测试由Claude Code负责
4. 实现完成后，通知Claude Code进行测试验收

### Claude Code测试职责

**测试类型**:
1. **单元测试**: 编写并执行pytest单元测试
2. **集成测试**: 验证模块间协作是否正常
3. **手动测试**: 使用真实数据验证功能 (如`docs/samples/collected_data.json`)
4. **测试报告**: 记录测试结果到`docs/test-report.md`

**测试流程**:
```bash
# 1. 运行单元测试
pytest tests/unit/test_{module}.py -v

# 2. 手动测试真实数据
python << 'EOF'
# 测试代码...
EOF

# 3. 记录结果到docs/test-report.md
```

### Claude Code监督要点

**每个Task验收时检查**:
- [ ] 代码实现是否完全符合开发指令文档
- [ ] 数据模型、接口签名是否与文档一致
- [ ] 单元测试是否覆盖文档中的所有测试用例
- [ ] 手动测试是否按文档要求执行并记录结果

---

## Project Overview

**BenchScope** = Benchmark Intelligence Agent (BIA)
一个自动化情报系统，每日采集AI/Agent领域的Benchmark资源，预筛选评分，推送到飞书，辅助研究团队高效筛选有价值的评测基准。

核心流程：
```
多源采集 → LLM+规则抽取 → 评分过滤 → 飞书多维表格入库 → 飞书播报 → 人工审核
```

**当前项目状态**:
- 设计阶段: ✅ 完成 (PRD 93/100, 架构 94/100)
- 开发阶段: ✅ Phase 1-2 已完成, 🔄 Phase 3 优化中
- 关键决策: 存储层从Notion改为飞书多维表格(主) + SQLite(降级备份)
- 核心功能: arXiv/GitHub/HuggingFace采集 + URL去重 + LLM评分(GPT-4o) + 飞书存储/通知

**不做的事**：
- 不做SEO优化（纯内部系统）
- 不训练深度模型（规则+LLM抽取足够）
- 不追求100%自动化（关键决策保留人工）

## Architecture

### Core Modules

1. **Data Collector** (`src/collector/`)
   - 数据源：arXiv API, Papers with Code, GitHub Trending, HuggingFace Hub
   - 配置文件：`config/sources.yaml`
   - 关键接口：`BenchmarkCollector.collect_arxiv()`, `collect_pwc()`, `collect_github_trending()`

2. **Pre-filter Engine** (`src/prefilter/`)
   - 评分维度（见PRD §II.2）：
     - 活跃度 25%（GitHub stars/commits）
     - 可复现性 30%（代码/数据开源状态）
     - 许可合规 20%（MIT/Apache/BSD）
     - 任务新颖性 15%（与已有任务相似度）
     - MGX适配度 10%（LLM判断业务相关性）
   - 筛选阈值：总分 ≥ 6.0/10
   - 配置文件：`config/weights.yaml`

3. **Storage Layer** (`src/storage/`)
   - **主存储**: 飞书多维表格 (FeishuStorage)
     - 理由: 国内稳定、API限额充足(100请求/分钟)、团队生态统一
     - 批量写入: 20条/请求
   - **降级备份**: SQLite (SQLiteFallback)
     - 飞书API失败时自动降级
     - 7天TTL,成功后自动同步并清理
   - **统一接口**: StorageManager (封装主备切换逻辑)
   - 关键字段: 标题, 来源, URL, 摘要, 5维评分, 总分, 优先级, 状态, GitHub信息

4. **Notification Engine** (`src/notifier/`)
   - 飞书卡片消息推送（带"一键添加"按钮）
   - 定期周报生成
   - Flask回调处理用户交互（`/feishu/callback`）

5. **Version Tracker** (`src/tracker/`)
   - 监控GitHub release更新
   - 监控arXiv论文版本变化
   - 监控Leaderboard SOTA变化

### Data Flow

```
GitHub Actions (每日UTC 2:00)
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
  ↓
存储管理器
  ├─ Primary: 飞书多维表格 (批量写入)
  └─ Fallback: SQLite (降级备份)
  ↓
飞书通知 (Webhook推送Top 5)
  ↓
Phase 2: 飞书卡片 + 一键添加按钮
```

## Technology Stack

| 模块 | 技术选型 | 关键依赖 |
|------|---------|---------|
| 数据采集 | Python + httpx | `arxiv`, `httpx`, `beautifulsoup4` |
| 智能评分 | LangChain + OpenAI | `langchain`, `openai` (gpt-4o-mini) |
| 数据存储 | 飞书多维表格 + SQLite | `lark-oapi`, `sqlite3` |
| 缓存 | Redis | `redis` (7天TTL, 30%命中率) |
| 消息推送 | 飞书开放平台 | `lark-oapi` (Webhook) |
| 任务调度 | GitHub Actions | `.github/workflows/daily_collect.yml` |
| Web服务 | Flask (Phase 2) | 处理飞书回调 |

**为什么不用复杂方案**：
- 不用Airflow：任务依赖简单，GitHub Actions足够
- 不用向量数据库：候选池规模小（<1000条），Numpy计算相似度即可
- 不用PostgreSQL：飞书多维表格满足需求，还能让研究员直接操作
- 不用Notion：飞书生态统一，国内访问更稳定

## Development Commands

### Initial Setup
```bash
python3.11 -m venv venv                # 创建虚拟环境
source venv/bin/activate               # 激活环境
pip install -r requirements.txt        # 安装依赖
cp .env.example .env.local            # 配置环境变量
# 填写 OPENAI_API_KEY, FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID
```

### Data Collection (单一数据源测试)
```bash
python src/collectors/cli.py --source arxiv --dry-run
python src/collectors/cli.py --source github --limit 10
python src/collectors/cli.py --source pwc --limit 10
```

### Scoring & Filtering
```bash
python src/prefilter/rule_filter.py --input docs/samples/arxiv.json
python src/scorer/llm_scorer.py --input docs/samples/filtered.json
```

### Feishu Integration
```bash
python src/storage/feishu_storage.py --test        # 测试飞书写入
python src/notifier/feishu_notifier.py --send-test # 测试通知推送
```

### Full Pipeline
```bash
python src/main.py              # 运行完整流程
```

### Testing
```bash
pytest tests -m "not slow"               # 快速单元测试
pytest tests -m integration              # 集成测试（需配置真实API）
pytest tests/unit/test_scorer.py -v     # 单模块测试
```

### Manual Review (强制执行)
```bash
python scripts/manual_review.py docs/samples/candidates.json
# 输出写入 docs/test-report.md，附截图或日志路径
```

## Code Quality Standards

### Python Style (PEP8强制)
- 4空格缩进，函数/变量 `snake_case`，类名 `PascalCase`
- 关键逻辑必须写**中文注释**
- 函数最大嵌套层级 ≤3（Linus规则）
- 魔法数字定义在 `src/common/constants.py`

### Scoring Constants Example
```python
# src/common/constants.py
ACTIVITY_WEIGHT = 0.25
REPRODUCIBILITY_WEIGHT = 0.30
LICENSE_WEIGHT = 0.20
NOVELTY_WEIGHT = 0.15
RELEVANCE_WEIGHT = 0.10

SCORE_THRESHOLD = 6.0  # 低于6分直接过滤
```

### Testing Requirements
- 修改评分逻辑前必须运行 `scripts/manual_review.py` 并提交测试报告
- 新评分维度需提供最小可复现脚本（放在 `scripts/`）
- 飞书/Notion交互必须手动验证并截图

### Commit Convention
```bash
feat: add arxiv collector with rate limiting
fix(scorer): correct activity score calculation for repos with <100 stars
chore: update config/sources.yaml with new GitHub topics
docs: add manual test report for scoring changes
```

PR必须包含：
- 问题背景
- 运行的命令
- 手动测试结果（截图/日志）
- 相关Issue/飞书讨论链接

## Configuration Files

### `config/sources.yaml` - 数据源配置
```yaml
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

### `config/weights.yaml` - 评分权重
```yaml
scoring:
  activity:
    weight: 0.25
    thresholds:
      stars: [100, 500, 1000]  # 分档阈值
      update_days: [7, 30, 90]

  reproducibility:
    weight: 0.30
    has_code: 6     # 有代码仓库得6分
    has_dataset: 3  # 有数据集得3分
    has_doc: 1      # 有复现文档得1分

  license:
    weight: 0.20
    approved: ["MIT", "Apache-2.0", "BSD-3-Clause"]

  novelty:
    weight: 0.15
    similarity_threshold: 0.8  # 相似度>0.8视为重复

  relevance:
    weight: 0.10
    mgx_keywords: ["multi-agent", "code generation", "web automation"]
```

## Key Design Decisions

### Why 飞书多维表格 Instead of Notion?
**技术决策时间**: 2025-11-13
**决策结果**: 飞书多维表格(主) + SQLite(降级备份)

**理由**:
1. **国内稳定性**: 飞书国内访问稳定,Notion常被墙
2. **API限额**: 飞书100请求/分钟 > Notion 3请求/秒(实际更严格)
3. **生态统一**: 团队已使用飞书,减少工具切换
4. **降级策略**: SQLite本地备份,7天自动同步,防数据丢失
5. **成本**: 飞书免费额度足够,Notion付费版才能API集成

**数据迁移计划**: 纯新项目,无历史数据迁移

### Why GitHub Actions Instead of Airflow?
- 任务依赖简单（串行采集+评分+入库）
- 免运维（不需要部署scheduler）
- 免费额度足够（每日5分钟任务 << 2000分钟/月）
- 迁移成本低（需要时改为Cron即可）

### Why gpt-4o-mini Instead of gpt-4?
- **成本**: gpt-4o-mini成本仅为gpt-4的1/10
- **性能**: 评分任务复杂度低,mini足够
- **优化**: 规则预筛选50% + Redis缓存30% → 月成本¥1 << 预算¥50

### Why LangChain for Extraction?
- 降低Prompt工程难度（内置结构化抽取链）
- 规则兜底：LLM失败时回退到正则表达式
- 可观测性：自动记录LLM调用日志

## Security & Compliance

### Secrets Management
所有API Token放入 `.env.local` 或 GitHub Secrets：
- `OPENAI_API_KEY`
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- `FEISHU_BITABLE_APP_TOKEN` / `FEISHU_BITABLE_TABLE_ID`
- `FEISHU_WEBHOOK_URL`
- `REDIS_URL`

配置文件仅引用变量名，严禁提交明文凭证。

### Rate Limiting Strategy
- arXiv API：无官方限流，建议3秒/请求
- GitHub API：5000请求/小时（认证），使用指数退避
- 飞书API：100请求/分钟，批量写入(20条/请求) + 0.6秒间隔
- OpenAI API：根据tier限制，使用tenacity重试 + Redis缓存

### Data Compliance
- 抓取任务遵守 robots.txt
- 白名单例外记录在 `config/whitelist.yaml` 并同步合规审批
- 用户数据（飞书user_id）仅用于审核记录，不外传

## Monitoring & Alerts

### Key Metrics (记录在日志中)
- 每日采集成功率（目标 >95%）
- 预筛选通过率（目标 10-30%）
- 飞书消息送达率（目标 100%）
- 候选池增长速度（目标 2-5个/周）

### Logging Format
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('BIA')
logger.info(f"采集arXiv: 发现{count}篇新论文")
logger.warning(f"GitHub API限流，等待{retry_after}秒")
logger.error(f"Notion写入失败: {error}")
```

### GitHub Actions Artifacts
每次运行上传日志到Artifacts，保留7天：
```yaml
- name: Upload logs
  uses: actions/upload-artifact@v3
  with:
    name: collection-logs
    path: logs/
```

## Implementation Phases

**当前状态**: Phase 2-5 已完成 ✅ → Phase 6 待开始 ⏭️

### Phase 0 (已完成) - 设计阶段 ✅
- [x] 仓库初始化与需求分析
- [x] PRD文档编写 (93/100质量分)
- [x] 系统架构设计 (94/100质量分)
- [x] 技术选型决策 (存储层: 飞书多维表格)
- [x] Codex开发指令文档准备

### Phase 1-2 (已完成) - MVP实施 ✅
**完成时间**: 2025-11-02 ~ 2025-11-08

- [x] 数据模型定义 (`src/models.py`)
- [x] 配置管理 (`src/config.py`)
- [x] 数据采集器
  - [x] ArxivCollector (⚠️ 存在超时问题)
  - [x] GitHubCollector (⚠️ 采集质量需优化)
  - [x] ~~PwCCollector~~ (已移除，Phase 3)
  - [x] HuggingFaceCollector
- [x] 规则预筛选 (`src/prefilter/rule_filter.py`)
- [x] 评分引擎
  - [x] LLMScorer (gpt-4o-mini)
- [x] 存储层
  - [x] SQLiteFallback
  - [x] FeishuStorage
  - [x] StorageManager (主备切换)
- [x] 飞书通知 (`src/notifier/feishu_notifier.py`)
- [x] 主编排器 (`src/main.py`)
- [x] GitHub Actions工作流 (`.github/workflows/daily_collect.yml`)
- [x] 单元测试 + 手动测试

**验收结果**:
- [x] GitHub Actions每日自动运行 ✅
- [x] 飞书多维表格自动写入 ✅
- [x] 飞书通知每日推送 ✅
- [x] 执行时间 < 20分钟 ✅ (实际79秒)
- [x] LLM月成本 < ¥50 ✅ (预计¥15/月)
- [ ] 数据采集成功率 > 95% ❌ (arXiv 0%, GitHub 100%, HF 0%)

### Phase 3 (已完成) - 核心优化 ✅
**完成时间**: 2025-11-13
**详细文档**: `.claude/specs/benchmark-intelligence-agent/CODEX-COMPREHENSIVE-PLAN.md`

- [x] 移除Papers with Code采集器
- [x] 优化GitHub预筛选规则 (stars≥10, README≥500, 90天更新)
- [x] 实现时间窗口过滤 (GitHub 30天, HuggingFace 14天, arXiv 7天)
- [x] 创建日志分析工具 (`scripts/analyze_logs.py`)
- [ ] ⏭️ 调整评分权重 (可选任务，已跳过)

### Phase 4 (已完成) - 版本跟踪 ✅
**完成时间**: 2025-11-13

- [x] GitHub Release监控 (`src/tracker/github_tracker.py`)
- [x] arXiv版本更新提醒 (`src/tracker/arxiv_tracker.py`)
- [x] GitHub Actions定时任务 (`.github/workflows/track_releases.yml`)
- [ ] ⏭️ Leaderboard SOTA追踪 (可选任务，已跳过)

### Phase 5 (已完成) - 增强功能 ✅
**完成时间**: 2025-11-13

- [x] 飞书卡片消息 (交互式卡片 + 按钮)
- [ ] ⏭️ Flask回调服务 (可选任务，已跳过)
- [ ] ⏭️ 候选池管理后台 (可选任务，已跳过)

**Phase 2-5 总结**:
- 核心任务完成率: 100% (7/7)
- 可选任务完成率: 0% (0/4)
- 代码质量: ⭐⭐⭐⭐⭐ (10/10)
- 单元测试: 19/19 通过 ✅
- 详细报告: `docs/codex-final-report.md`

### Phase 6 (待开始) - 信息源扩展与数据完善 ⏭️
**预计工期**: 2-3周
**详细PRD**: `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md`
**测试报告**: `docs/phase2-5-test-report.md`

**核心任务**:
- [ ] Task 6.1: 扩展会议论文采集 (Semantic Scholar + ACL Anthology)
- [ ] Task 6.2: 接入评测榜单 (HELM + Open LLM Leaderboard + EvalPlus)
- [ ] Task 6.3: 优化GitHub搜索策略 (排除awesome lists, 验证Benchmark特征)
- [ ] Task 6.4: 完善飞书表格字段 (新增9个字段)
- [ ] Task 6.5: 优化预筛选规则 (Benchmark特征检测)
- [ ] Task 6.6: 优化LLM评分Prompt (区分工具vs Benchmark)

**可选任务**:
- [ ] Task 7.1: Twitter/X监听
- [ ] Task 7.2: 飞书群聊集成
- [ ] Task 7.3: HuggingFace Spaces监控

**Phase 6 目标**:
- 信息源覆盖: 30% → 80% (+167%)
- 真实Benchmark占比: <20% → ≥60% (+200%)
- 预筛选过滤率: 0% → 30-50%
- 平均评分: 8.61 → 6.0-7.5
- 数据字段完整性: 13/22 → 22/22 (+69%)

## Critical Constraints

1. **手动测试强制执行**：
   - 飞书播报、飞书多维表格、外部API交互必须手动验证
   - 结果写入 `docs/test-report.md` 并附截图/日志

2. **评分逻辑变更流程**：
   - 修改 `src/scorer/llm_scorer.py` 前需提供最小可复现脚本
   - 提供样例输入和预期输出
   - PR附变更前后对比测试结果

3. **Linus哲学约束** (来自全局CLAUDE.md):
   - **Is this a real problem?** → 拒绝过度工程
   - **Is there a simpler way?** → 永远寻找最简单实现
   - **What will this break?** → MVP零破坏(纯新项目)
   - 最大嵌套层级 ≤ 3
   - 关键逻辑必须中文注释

## BMAD Workflow Integration

本项目采用BMAD (Build-Measure-Architect-Deploy) 工作流:

- **Phase 0 - Repo Scan**: ✅ 已完成 (`.claude/specs/benchmark-intelligence-agent/00-repo-scan.md`)
- **Phase 1 - PRD**: ✅ 已完成 (`.claude/specs/benchmark-intelligence-agent/01-product-requirements.md`, 93/100)
- **Phase 2 - Architecture**: ✅ 已完成 (`.claude/specs/benchmark-intelligence-agent/02-system-architecture.md`, 94/100)
- **Phase 3 - Development**: 🔄 进行中 (参考 `CODEX-DEVELOPMENT-BRIEF.md`)
- **Phase 4 - QA**: ⏭️ 待开始
- **Phase 5 - Deploy**: ⏭️ 待开始

**开发者指南**: 参考 `.claude/specs/benchmark-intelligence-agent/CODEX-DEVELOPMENT-BRIEF.md` 获取完整开发指令。

## Reference Documents

### 核心设计文档 (BMAD产出)
- `.claude/specs/benchmark-intelligence-agent/00-repo-scan.md` - 仓库扫描报告
- `.claude/specs/benchmark-intelligence-agent/01-product-requirements.md` - PRD文档 (93/100质量)
  - 14个用户故事,完整验收标准,ROI分析
- `.claude/specs/benchmark-intelligence-agent/02-system-architecture.md` - 系统架构 (94/100质量)
  - 5层架构详解,完整代码示例,错误处理策略,性能成本分析
- `.claude/specs/benchmark-intelligence-agent/CODEX-DEVELOPMENT-BRIEF.md` - Codex开发指令 (Phase 1-2)
  - MVP实施清单,代码规范,测试要求,验收标准
- `.claude/specs/benchmark-intelligence-agent/CODEX-COMPREHENSIVE-PLAN.md` - **综合开发方案 (Phase 3-5)** ✅
  - **Phase 3**: 核心优化（GitHub预筛选、时间过滤、PwC移除、日志工具、评分权重）
  - **Phase 4**: 版本跟踪（GitHub Release、arXiv版本、Leaderboard SOTA）
  - **Phase 5**: 增强功能（飞书卡片消息、交互按钮）
  - 详细代码实现、验收标准、测试流程、开发顺序
- `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md` - **Phase 6开发PRD** ⏭️
  - **信息源扩展**: Semantic Scholar、HELM、Open LLM Leaderboard、ACL Anthology
  - **采集质量优化**: GitHub搜索策略优化、Benchmark特征检测
  - **数据完善**: 新增9个飞书字段（论文URL、数据集URL、评估指标等）
  - **评分优化**: 增强预筛选规则、优化LLM评分Prompt
  - 2-3周开发计划、完整验收标准、成本估算

### 测试报告
- `docs/phase2-5-test-report.md` - **Phase 2-5完整测试报告** (2025-11-13)
  - Pipeline端到端测试结果
  - 问题诊断与分析
  - Phase 6改进建议
- `docs/codex-final-report.md` - Codex开发完成报告
  - Phase 3-5详细完成情况
  - 代码质量评估
  - Git提交记录

### 历史文档
- `PRD_FINAL.md` - 原始产品需求文档 (已被BMAD PRD取代,仅供参考)
- `AGENTS.md` - 仓库规范与约束
- `gemini.md` - Gemini相关设计（待确认用途）

### 项目规范
- `.claude/commands/arrange.md` - 文件整理规范
- `.claude/commands/deploy.md` - GitHub部署规范

## Common Pitfalls

1. **不要过度工程化**：
   - 不需要Airflow（GitHub Actions足够）
   - 不需要向量数据库（Numpy足够）
   - 不需要训练模型（规则+LLM足够）
   - MVP串行采集(5分钟够用,Phase 2再并发优化)

2. **不要忽略人工环节**：
   - 关键决策（入库确认）保留人工
   - LLM抽取结果需要规则兜底
   - 评分权重需要定期复盘调整

3. **不要破坏向后兼容**：
   - 修改飞书字段前先迁移旧数据
   - 修改飞书卡片格式前测试回调兼容性
   - 修改评分算法前对比历史候选池评分

4. **不要忽视存储降级**：
   - 飞书API失败时SQLite自动兜底
   - 7天内自动同步,不要手动干预
   - 监控SQLite大小,超过阈值告警

## Quick Start for New Contributors

```bash
# 1. Clone repo
git clone <repo-url>
cd BenchScope

# 2. Setup environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env.local
# 编辑.env.local,填入真实API密钥

# 4. Test single collector (验证环境)
python src/collectors/arxiv_collector.py --dry-run

# 5. Run full pipeline locally
python src/main.py

# 6. Check Feishu Bitable
# 访问飞书多维表格确认数据已写入

# 7. Test notification
python src/notifier/feishu_notifier.py --send-test
```

**新贡献者注意**:
- 先阅读 `CODEX-DEVELOPMENT-BRIEF.md` 了解完整开发规范
- 遵循Linus哲学: 简单优先,拒绝过度工程
- 手动测试强制执行,结果记录到 `docs/test-report.md`
- Commit遵循Conventional Commits,不添加emoji

## Success Criteria

| 指标 | 现状 | 目标 | 验收标准 |
|------|------|------|---------|
| Benchmark发现速度 | 人工2-3个/月 | 系统10-20个/月 | 持续3个月达标 |
| 信息筛选效率 | 人工阅读200篇论文 | 预筛选后阅读20篇 | 噪音过滤率90%+ |
| 入库响应时间 | 发现后1-2周 | 发现后1-3天 | 自动播报延迟<24h |
| 候选池质量 | 无评分标准 | 入库后实际使用率>50% | 追踪3个月数据 |

3个月后，团队应该能够：
- 每周自动获取10-20个高质量候选Benchmark
- 信息噪音过滤率达到90%以上
- 从"被动搜索"变为"主动推送"
- Benchmark候选池规模扩大3-5倍
