# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dual-Agent Collaboration Mode

**This project uses a dual-agent workflow. Claude Code is prohibited from directly modifying code.**

| Role | Responsibilities | Prohibited |
|------|------------------|------------|
| **Claude Code** | Analysis, PRD/architecture docs, development instructions for Codex, test execution, acceptance | Direct code modification (Edit/Write on .py files) |
| **Codex** | Code implementation per Claude Code's instruction docs | Architecture decisions, deviating from specs |

**Workflow**: User request -> Claude Code analyzes & writes instruction doc -> Codex implements -> Claude Code tests & accepts

**Instruction docs location**: `.claude/specs/benchmark-intelligence-agent/CODEX-*.md`

---

## Project Overview

**BenchScope** = **Benchmark Intelligence Agent (BIA)**

一个自动化情报系统，每日采集AI/Agent领域的Benchmark资源，预筛选评分，推送到飞书，辅助研究团队高效筛选有价值的评测基准。

**服务于**: [MGX (https://mgx.dev)](https://mgx.dev) - 多智能体协作框架，专注Vibe Coding (AI原生编程)

### 核心目标

1. **系统性调研与评估**
   - 覆盖GUI/Web/Coding/DeepResearch/Agent协作等领域的新Benchmarks
   - 判断是否适合纳入现有Benchmark池以扩充覆盖面

2. **自动化情报流**
   - 建立"可定期更新"的自动化情报流
   - 降低人工维护成本，减少信息遗漏

3. **一键添加到候选池**
   - 提供完整Benchmark基础信息：论文地址、数据集地址、复现脚本、评估指标、开源时间等
   - 支持快速决策是否纳入Benchmark池

### 工作流（Workflow）

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 自动发现（Auto Discovery）                                 │
│    - 论文库: arXiv, Semantic Scholar                          │
│    - 评测榜单: HELM                                           │
│    - 开源社区: GitHub, HuggingFace Hub                        │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. 预筛与评分（Pre-filter & Scoring）                        │
│    快速指标:                                                  │
│    - 活跃度 25%: GitHub stars/commits                         │
│    - 可复现性 30%: 代码/数据集开源状态                        │
│    - 许可合规 20%: MIT/Apache/BSD                             │
│    - 任务新颖性 15%: 与已有任务重叠度                         │
│    - MGX适配度 10%: LLM判断业务相关性                         │
│                                                               │
│    输出: 评分依据（说明为何作为候选Benchmark）                │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. 一键添加到Benchmark候选池（Feishu Bitable）               │
│    必需字段（支撑快速决策）:                                  │
│    ✅ 标题、来源、URL、摘要                                    │
│    ✅ 论文URL、数据集URL、复现脚本链接                        │
│    ✅ 评估指标摘要、开源时间、任务类型、License类型           │
│    ✅ GitHub Stars、作者信息                                  │
│    ✅ 5维评分 + 总分 + 优先级 + 评分依据                      │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. 飞书播报与人工审核（Human Review）                        │
│    - 每日自动推送Top候选项（交互式卡片）                       │
│    - 研究团队快速审核、标记状态（待评估/已采纳/已拒绝）        │
│    - 重要更新通知（GitHub Release、arXiv版本更新）            │
└──────────────────────────────────────────────────────────────┘
```

**当前项目状态**:
- 设计阶段: ✅ 完成 (PRD 93/100, 架构 94/100)
- 开发阶段: ✅ Phase 1-5 已完成, 🔄 Phase 6 进行中
- 关键决策: 存储层从Notion改为飞书多维表格(主) + SQLite(降级备份)
- 核心功能: arXiv/GitHub/HuggingFace/HELM/TechEmpower/DBEngines采集 + URL去重 + LLM评分(GPT-4o, 50并发) + 飞书存储/通知

**不做的事**：
- 不做SEO优化（纯内部系统）
- 不训练深度模型（规则+LLM抽取足够）
- 不追求100%自动化（关键决策保留人工）

## Architecture

### Core Modules

```
src/
├── collectors/              # 数据采集器
│   ├── arxiv_collector.py        # arXiv API
│   ├── github_collector.py       # GitHub Search API
│   ├── huggingface_collector.py  # HuggingFace Hub API
│   ├── helm_collector.py         # HELM Leaderboard scraper
│   ├── semantic_scholar_collector.py  # Semantic Scholar API
│   ├── techempower_collector.py  # TechEmpower Web框架基准
│   ├── dbengines_collector.py    # DB-Engines数据库排名
│   └── twitter_collector.py      # Twitter/X采集
│
├── prefilter/              # 规则预筛选
│   └── rule_filter.py          # URL去重 + Benchmark特征检测 (40-60%过滤)
│
├── scorer/                 # 评分引擎
│   ├── llm_scorer.py           # GPT-4o-mini评分 + Redis缓存 + 规则兜底
│   └── backend_scorer.py       # 后端Benchmark专项评分
│
├── enhancer/               # 数据增强
│   └── pdf_enhancer.py         # PDF结构化解析 (GROBID集成)
│
├── extractors/             # 信息抽取 (预留)
│
├── storage/                # 存储层
│   ├── feishu_storage.py       # 飞书多维表格 (主存储)
│   ├── sqlite_fallback.py      # SQLite降级备份
│   └── storage_manager.py      # 主备切换管理器
│
├── notifier/               # 通知引擎
│   └── feishu_notifier.py      # 飞书Webhook + 交互式卡片
│
├── api/                    # Web服务
│   └── feishu_callback.py      # 飞书回调处理
│
├── common/constants.py     # 常量配置
├── models.py               # 数据模型 (RawCandidate, ScoredCandidate)
├── config.py               # 配置管理
└── main.py                 # 流程编排器

config/sources.yaml         # 数据源配置 (关键词、超时、时间窗口)
```

### Data Flow

```
GitHub Actions (每日UTC 2:00 / 北京时间10:00)
  ↓
main.py → 并发采集 → 规则预筛选 → LLM评分 → 飞书存储 → 飞书通知
  ↓              ↓                  ↓             ↓
 arXiv/GitHub   URL去重          GPT-4o-mini    批量写入
 HuggingFace    Benchmark特征    5维评分       (主) 飞书表格
 HELM/等        40-60%过滤       Redis缓存      (备) SQLite
```

## Development Commands

**虚拟环境**: 所有Python命令使用 `.venv/bin/python`

### Initial Setup

```bash
# 创建虚拟环境
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 系统依赖 (PDF处理)
# Ubuntu: sudo apt-get install -y poppler-utils
# macOS: brew install poppler

# 配置环境变量
cp .env.example .env.local
# 必填: OPENAI_API_KEY, FEISHU_APP_ID, FEISHU_APP_SECRET,
#       FEISHU_BITABLE_APP_TOKEN, FEISHU_BITABLE_TABLE_ID
# 可选: REDIS_URL, GITHUB_TOKEN, SEMANTIC_SCHOLAR_API_KEY
```

### Common Commands

```bash
# 完整流程
.venv/bin/python -m src.main

# 日志分析
.venv/bin/python scripts/analyze_logs.py

# 飞书表格操作
.venv/bin/python scripts/deduplicate_feishu_table.py  # 去重
.venv/bin/python scripts/clear_feishu_table.py        # 清空 (危险!)

# 代码质量
black . && ruff check .

# 查看最新日志
tail -100 logs/$(ls -t logs/ | head -n1)
```

## Configuration

### `config/sources.yaml` - 数据源配置

主要配置项: `enabled`, `max_results`, `lookback_hours/days`, `keywords`, `categories`

修改后无需重新部署，下次运行自动生效。

### `.env.local` - 环境变量

| 变量 | 必填 | 说明 |
|-----|------|------|
| OPENAI_API_KEY | Y | GPT-4o-mini评分 |
| FEISHU_APP_ID / FEISHU_APP_SECRET | Y | 飞书应用凭证 |
| FEISHU_BITABLE_APP_TOKEN / TABLE_ID | Y | 飞书多维表格 |
| REDIS_URL | N | 缓存LLM评分 (+30%性能) |
| GITHUB_TOKEN | N | 提升速率限制 |

## Code Quality Standards

- PEP8: 4空格缩进, `snake_case` 函数/变量, `PascalCase` 类名
- 关键逻辑必须写**中文注释**
- 函数嵌套 ≤3层 (Linus规则)
- 魔法数字定义在 `src/common/constants.py`
- Commit格式: `type(scope): summary` (feat/fix/refactor/docs/chore)

## Critical Constraints

1. **手动测试**: 飞书播报、飞书表格、外部API必须手动验证
2. **评分变更**: 修改 `llm_scorer.py` 需提供样例输入/输出和对比测试
3. **向后兼容**: 修改飞书字段先迁移旧数据，修改评分算法先对比历史评分

## Key Design Decisions

- **飞书多维表格 vs Notion**: 国内稳定、API限额高、SQLite降级
- **GPT-4o-mini vs GPT-4**: 成本1/10，评分任务复杂度低，规则预筛+缓存优化调用量
- **GitHub Actions vs Airflow**: 任务依赖简单，免运维，免费额度充足

## Project Status

- **Version**: v1.6.0
- **Phase 1-6**: 完成 (MVP + 优化 + 信息源扩展)
- **GitHub Actions**: 每日UTC 02:00自动运行

## Reference Documents

- PRD: `.claude/specs/benchmark-intelligence-agent/01-product-requirements.md`
- 架构: `.claude/specs/benchmark-intelligence-agent/02-system-architecture.md`
- 测试报告: `docs/phase2-5-test-report.md`
- 开发指令示例: `.claude/specs/benchmark-intelligence-agent/CODEX-PHASE9-URGENT-FIX.md`
