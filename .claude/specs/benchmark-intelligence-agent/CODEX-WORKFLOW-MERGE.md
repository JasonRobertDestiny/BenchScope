# Codex开发指令：合并GitHub Actions Workflows

**任务类型**：架构重构（消除冗余）
**优先级**：P1（核心架构优化）
**预计工时**：1-2小时
**创建时间**：2025-11-19

---

## 一、问题诊断

### 1.1 当前架构问题

**重复工作流**：
```
.github/workflows/
├── daily_collect.yml      # 每天09:00，采集新Benchmark
└── track_releases.yml     # 每天09:30，监控版本更新
```

**冗余分析**（违反Linus"Is there a simpler way?"原则）：

| 维度 | daily_collect.yml | track_releases.yml | 冗余程度 |
|------|-------------------|-------------------|----------|
| 运行时间 | 09:00 | 09:30 | ❌ 30分钟延迟无必要 |
| Python环境 | setup-python@v5 | setup-python@v5 | ❌ 重复安装 |
| 依赖安装 | pip install | pip install | ❌ 重复安装 |
| 飞书存储访问 | FeishuStorage | FeishuStorage | ❌ 重复连接 |
| 飞书通知 | FeishuNotifier | FeishuNotifier | ❌ 分散推送 |
| Secret配置 | 9个环境变量 | 6个环境变量 | ❌ 配置分散 |

**效率损失**：
- CI/CD执行时间：2次 × 3分钟 = 6分钟/天 → 180分钟/月
- GitHub Actions配额：2次运行 → 浪费50%
- 飞书通知：2次推送 → 用户需要查看2次消息
- 维护成本：2个workflow文件 → 修改需要同步

### 1.2 根本原因

**设计时的历史遗留**：
- Phase 1-2: 实现daily_collect.yml（主流程）
- Phase 4: 新增版本跟踪功能，**图方便**创建了独立的track_releases.yml
- 违反了"Good programmers worry about data structures"原则 → 应该统一数据流

### 1.3 Linus哲学验证

**三问检验**：
1. **Is this a real problem?** → ✅ 是真问题（浪费CI资源、分散用户注意力）
2. **Is there a simpler way?** → ✅ 有更简单方案（合并成1个workflow）
3. **What will this break?** → ✅ 零破坏（纯架构优化，不影响功能）

---

## 二、解决方案设计

### 2.1 统一架构

**合并后的workflow**：
```
.github/workflows/
└── daily_intelligence.yml  # 统一的智能采集workflow
    ├── Job 1: collect-and-score  (主流程)
    │   ├── Step 1: 数据采集 (7个collectors)
    │   ├── Step 2: URL去重
    │   ├── Step 3: 规则预筛选
    │   ├── Step 4: PDF内容增强
    │   ├── Step 5: LLM评分
    │   ├── Step 6: 存储入库
    │   ├── Step 7: 版本跟踪 (新增)
    │   │   ├── GitHub Release监控
    │   │   └── arXiv版本监控
    │   └── Step 8: 统一飞书通知 (改造)
    │       ├── 新发现Benchmark (High/Medium/Low)
    │       ├── GitHub Release更新
    │       └── arXiv版本更新
    └── Artifacts
        ├── logs/ (保留7天)
        └── fallback.db (保留7天)
```

### 2.2 关键设计决策

#### 决策1：版本跟踪集成到主流程 Step 7

**理由**：
- 共享飞书存储连接（避免重复初始化）
- 共享Redis缓存（避免重复连接）
- 统一错误处理和日志记录
- 减少CI/CD资源消耗

**实现位置**：`src/main.py` 的主流程末尾

#### 决策2：统一飞书通知

**当前问题**：
```python
# daily_collect.yml 执行后
await notifier.notify(scored_candidates)  # 只推送新Benchmark

# track_releases.yml 执行后（30分钟后）
await notifier.send_text(f"GitHub Release更新...")  # 单独推送
```

**优化后**：
```python
# 统一推送（1次消息，3个section）
await notifier.notify_daily_report(
    new_benchmarks=scored_candidates,  # 新发现Benchmark
    github_releases=new_releases,      # GitHub更新
    arxiv_updates=arxiv_updates        # arXiv更新
)
```

#### 决策3：保留独立脚本，但改为库函数

**当前**：
```
scripts/
├── track_github_releases.py  # 独立脚本，main()函数
└── track_arxiv_versions.py   # 独立脚本，main()函数
```

**优化后**：
```
scripts/
├── track_github_releases.py  # 保留作为独立工具（手动调试用）
└── track_arxiv_versions.py   # 保留作为独立工具（手动调试用）

src/tracker/
├── github_tracker.py         # 核心逻辑（供main.py和脚本共用）
└── arxiv_tracker.py          # 核心逻辑（供main.py和脚本共用）
```

**理由**：
- 独立脚本保留便于手动调试和测试
- 核心逻辑提取到`src/tracker/`模块供main.py调用
- 遵循DRY原则（Don't Repeat Yourself）

---

## 三、实施步骤

### Step 1: 增强FeishuNotifier支持统一播报

**文件**：`src/notifier/feishu_notifier.py`

**当前代码**（仅支持新Benchmark推送）：
```python
class FeishuNotifier:
    async def notify(
        self,
        candidates: List[ScoredCandidate],
        batch_size: int = 5,
        delay: float = 1.0,
    ) -> None:
        """分层推送策略：High优先，Medium次之，Low补充"""
        # ...
```

**新增方法**（统一播报）：
```python
from typing import Dict, Any

class FeishuNotifier:
    # ... 保留现有notify()方法 ...

    async def notify_daily_report(
        self,
        new_benchmarks: List[ScoredCandidate],
        github_releases: List[Dict[str, Any]],
        arxiv_updates: List[Dict[str, Any]],
    ) -> None:
        """
        每日智能播报（统一推送）

        消息结构：
        ┌────────────────────────────────────┐
        │ 📊 BenchScope每日智能播报           │
        ├────────────────────────────────────┤
        │ 🆕 新发现Benchmark (5条)            │
        │   - [High] xxx (9.2分)             │
        │   - [Medium] yyy (7.8分)           │
        ├────────────────────────────────────┤
        │ 🔄 GitHub Release更新 (2条)        │
        │   - repo/name v2.0.0               │
        ├────────────────────────────────────┤
        │ 📄 arXiv版本更新 (1条)             │
        │   - 2401.12345 v3 → v4             │
        └────────────────────────────────────┘

        Args:
            new_benchmarks: 新发现的Benchmark候选项
            github_releases: GitHub Release更新列表
            arxiv_updates: arXiv版本更新列表
        """
        sections = []

        # Section 1: 新发现Benchmark
        if new_benchmarks:
            high_pri = [c for c in new_benchmarks if c.priority == "High"]
            medium_pri = [c for c in new_benchmarks if c.priority == "Medium"]
            low_pri = [c for c in new_benchmarks if c.priority == "Low"]

            benchmark_text = f"🆕 **新发现Benchmark ({len(new_benchmarks)}条)**\n\n"

            if high_pri:
                benchmark_text += "**High Priority:**\n"
                for c in high_pri[:3]:  # 最多3条
                    benchmark_text += f"- [{c.title}]({c.url}) (总分{c.total_score:.1f})\n"
                benchmark_text += "\n"

            if medium_pri:
                benchmark_text += "**Medium Priority:**\n"
                for c in medium_pri[:2]:  # 最多2条
                    benchmark_text += f"- [{c.title}]({c.url}) (总分{c.total_score:.1f})\n"
                benchmark_text += "\n"

            if low_pri and len(high_pri) + len(medium_pri) < 5:
                benchmark_text += "**Low Priority:**\n"
                for c in low_pri[:1]:  # 最多1条
                    benchmark_text += f"- [{c.title}]({c.url}) (总分{c.total_score:.1f})\n"

            sections.append(benchmark_text)

        # Section 2: GitHub Release更新
        if github_releases:
            release_text = f"🔄 **GitHub Release更新 ({len(github_releases)}条)**\n\n"
            for release in github_releases[:5]:  # 最多5条
                repo = release.get("repo", "unknown")
                tag = release.get("tag_name", "unknown")
                url = release.get("html_url", "")
                release_text += f"- [{repo} {tag}]({url})\n"
            sections.append(release_text)

        # Section 3: arXiv版本更新
        if arxiv_updates:
            arxiv_text = f"📄 **arXiv版本更新 ({len(arxiv_updates)}条)**\n\n"
            for update in arxiv_updates[:5]:  # 最多5条
                arxiv_id = update.get("arxiv_id", "unknown")
                old_ver = update.get("old_version", "?")
                new_ver = update.get("new_version", "?")
                title = update.get("title", "Unknown Title")
                url = update.get("url", f"https://arxiv.org/abs/{arxiv_id}")
                arxiv_text += f"- [{arxiv_id}]({url}) v{old_ver}→v{new_ver}: {title[:50]}\n"
            sections.append(arxiv_text)

        # 合并所有section
        if not sections:
            logger.info("无新内容需要推送")
            return

        message = "📊 **BenchScope每日智能播报**\n\n"
        message += "\n\n---\n\n".join(sections)
        message += f"\n\n🕒 更新时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

        await self.send_text(message)
        logger.info("每日智能播报已推送")
```

**关键点**：
- ✅ 保持现有`notify()`方法不变（向后兼容）
- ✅ 新增`notify_daily_report()`方法处理统一播报
- ✅ 3个section分开展示，但1次推送
- ✅ 支持空section（如果某类更新为0条）

---

### Step 2: 集成版本跟踪到主流程

**文件**：`src/main.py`

**当前代码**（6步流程）：
```python
async def main() -> None:
    # Step 1: 数据采集
    # Step 2: URL去重
    # Step 3: 规则预筛选
    # Step 4: PDF内容增强
    # Step 5: LLM评分
    # Step 6: 存储入库
    # Step 7: 飞书通知 ← 需要改造
```

**修改后代码**（增加Step 7和改造Step 8）：
```python
async def main() -> None:
    logger.info("="*60)
    logger.info("BenchScope Daily Intelligence Pipeline")
    logger.info("="*60)

    # ... Step 1-6 保持不变 ...

    # [6/8] 存储入库
    logger.info(f"\n[6/8] 存储入库...")
    if scored_candidates:
        storage_manager = StorageManager()
        success = await storage_manager.save_batch(scored_candidates)
        if success:
            logger.info("  ✓ 飞书多维表格写入成功")
        else:
            logger.warning("  ⚠ 飞书写入失败，已降级到SQLite备份")
    else:
        logger.info("  ℹ 无新候选项需要存储")

    # [7/8] 版本跟踪（新增）
    logger.info(f"\n[7/8] 版本跟踪...")
    github_releases: List[Dict[str, Any]] = []
    arxiv_updates: List[Dict[str, Any]] = []

    try:
        # GitHub Release监控
        from src.tracker.github_tracker import GitHubReleaseTracker
        from src.storage.storage_manager import StorageManager

        storage = StorageManager()
        existing_urls = await storage.get_existing_urls()
        github_urls = sorted(url for url in existing_urls if "github.com" in url)

        if github_urls:
            logger.info(f"  检测到{len(github_urls)}个GitHub仓库，开始监控Release...")
            github_token = os.getenv("GITHUB_TOKEN")
            tracker = GitHubReleaseTracker(
                db_path=str(settings.sqlite_path),
                github_token=github_token
            )
            github_releases = await tracker.check_updates(github_urls)
            logger.info(f"  ✓ GitHub Release: {len(github_releases)}个更新")
        else:
            logger.info("  ℹ 暂无GitHub仓库需要监控")

        # arXiv版本监控
        from src.tracker.arxiv_tracker import ArxivVersionTracker

        arxiv_urls = sorted(url for url in existing_urls if "arxiv.org" in url)

        if arxiv_urls:
            logger.info(f"  检测到{len(arxiv_urls)}个arXiv论文，开始监控版本...")
            arxiv_tracker = ArxivVersionTracker(db_path=str(settings.sqlite_path))
            arxiv_updates = await arxiv_tracker.check_updates(arxiv_urls)
            logger.info(f"  ✓ arXiv版本: {len(arxiv_updates)}个更新")
        else:
            logger.info("  ℹ 暂无arXiv论文需要监控")

    except Exception as e:
        logger.error(f"  ✗ 版本跟踪失败: {e}", exc_info=True)
        # 版本跟踪失败不影响主流程，继续执行

    # [8/8] 统一飞书通知（改造）
    logger.info(f"\n[8/8] 飞书通知...")
    notifier = FeishuNotifier()
    try:
        await notifier.notify_daily_report(
            new_benchmarks=scored_candidates,
            github_releases=github_releases,
            arxiv_updates=arxiv_updates
        )
        logger.info("  ✓ 每日智能播报已推送")
    except Exception as e:
        logger.error(f"  ✗ 飞书通知失败: {e}", exc_info=True)

    logger.info("\n" + "="*60)
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Pipeline执行完成，总耗时{total_time:.1f}秒")
    logger.info("="*60)
```

**关键改动**：
- ✅ 新增`[7/8] 版本跟踪`步骤
- ✅ 改造`[8/8] 飞书通知` → 使用`notify_daily_report()`
- ✅ 版本跟踪失败不阻断主流程（try-except容错）
- ✅ 步骤编号从`[6/6]`改为`[8/8]`

---

### Step 3: 创建统一的GitHub Actions Workflow

**文件**：`.github/workflows/daily_intelligence.yml`（新建）

**完整代码**：
```yaml
name: BenchScope Daily Intelligence

on:
  schedule:
    - cron: '0 1 * * *'  # 北京时间 09:00 (UTC+8)
  workflow_dispatch:      # 支持手动触发

jobs:
  intelligence:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Intelligence Pipeline
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
          FEISHU_BITABLE_TABLE_ID: ${{ secrets.FEISHU_BITABLE_TABLE_ID }}
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GH_PAT }}
          HUGGINGFACE_TOKEN: ${{ secrets.HUGGINGFACE_TOKEN }}
          REDIS_URL: redis://localhost:6379/0
          LOG_LEVEL: INFO
        run: |
          python -m src.main

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: benchscope-logs
          path: logs/
          retention-days: 7

      - name: Upload SQLite backup
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sqlite-backup
          path: fallback.db
          retention-days: 7
```

**关键改进**：
- ✅ 包含`GITHUB_TOKEN`环境变量（修复速率限制）
- ✅ 统一workflow名称`BenchScope Daily Intelligence`
- ✅ 单次运行完成所有任务（采集+评分+存储+版本跟踪+通知）
- ✅ 保留Redis服务（LLM评分缓存）

---

### Step 4: 删除旧的workflows

**操作**：
```bash
# 删除冗余文件
rm .github/workflows/daily_collect.yml
rm .github/workflows/track_releases.yml
```

**理由**：
- ✅ 功能已完全迁移到`daily_intelligence.yml`
- ✅ 避免混淆和误触发
- ✅ 简化维护（1个workflow文件 vs 2个）

---

### Step 5: 更新文档

**文件1**：`.claude/CLAUDE.md`

**修改位置**：`## Architecture` section

**修改前**：
```markdown
### GitHub Actions Workflows

Daily Collection (`.github/workflows/daily_collect.yml`)
Version Tracking (`.github/workflows/track_releases.yml`)
```

**修改后**：
```markdown
### GitHub Actions Workflows

**统一Workflow** (`.github/workflows/daily_intelligence.yml`)

触发时间: 每天 UTC 01:00 (北京时间 09:00)

执行流程:
1. 数据采集 (7个collectors)
2. URL去重
3. 规则预筛选
4. PDF内容增强
5. LLM评分
6. 存储入库
7. 版本跟踪 (GitHub Release + arXiv)
8. 统一飞书通知 (新Benchmark + Release更新 + arXiv更新)

运行时间: ~60秒 (50并发LLM评分)
```

**文件2**：`README.md`

**修改位置**：`## Workflow` section

**修改后**：
```markdown
### Automated Workflow

```
GitHub Actions (每日UTC 01:00)
  ↓
daily_intelligence.yml (统一智能流程)
  ↓
[1/8] 并发采集 (7 collectors)
  ↓
[2/8] URL去重
  ↓
[3/8] 规则预筛选
  ↓
[4/8] PDF内容增强
  ↓
[5/8] LLM评分 (gpt-4o, 50并发)
  ↓
[6/8] 飞书存储 + SQLite备份
  ↓
[7/8] 版本跟踪
  ├─ GitHub Release监控
  └─ arXiv版本监控
  ↓
[8/8] 统一飞书播报
  ├─ 新发现Benchmark
  ├─ GitHub Release更新
  └─ arXiv版本更新
```
```

---

## 四、测试验证计划

### 4.1 单元测试

**测试1：FeishuNotifier.notify_daily_report()**

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
.venv/bin/python -c "
import asyncio
from src.notifier import FeishuNotifier
from src.models import ScoredCandidate, RawCandidate

async def test():
    notifier = FeishuNotifier()

    # 构造测试数据
    raw = RawCandidate(
        title='Test Benchmark',
        url='https://github.com/test/benchmark',
        source='GitHub',
        summary='测试用Benchmark',
        arxiv_id=None,
        github_stars=100,
        github_url='https://github.com/test/benchmark',
        huggingface_downloads=0,
        authors=['Test Author'],
        published_date='2025-11-19'
    )

    scored = ScoredCandidate.from_raw(
        raw,
        activity_score=8.0,
        reproducibility_score=9.0,
        license_score=10.0,
        novelty_score=7.0,
        relevance_score=8.5,
        reasoning='测试评分依据'
    )

    github_releases = [
        {
            'repo': 'owner/repo',
            'tag_name': 'v2.0.0',
            'html_url': 'https://github.com/owner/repo/releases/tag/v2.0.0'
        }
    ]

    arxiv_updates = [
        {
            'arxiv_id': '2401.12345',
            'old_version': '3',
            'new_version': '4',
            'title': 'Test Paper Title',
            'url': 'https://arxiv.org/abs/2401.12345'
        }
    ]

    await notifier.notify_daily_report(
        new_benchmarks=[scored],
        github_releases=github_releases,
        arxiv_updates=arxiv_updates
    )

    print('✅ 统一播报测试成功，请检查飞书群聊')

asyncio.run(test())
"
```

**预期结果**：
- ✅ 飞书群聊收到1条消息
- ✅ 消息包含3个section（新Benchmark、GitHub更新、arXiv更新）
- ✅ 格式清晰，链接可点击

---

**测试2：main.py完整流程**

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope

# 设置测试环境变量（如果本地没有.env.local）
export OPENAI_API_KEY="sk-xxx"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_BITABLE_APP_TOKEN="xxx"
export FEISHU_BITABLE_TABLE_ID="xxx"
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export GITHUB_TOKEN="ghp_xxx"

# 运行完整流程
.venv/bin/python -m src.main
```

**预期日志输出**：
```
============================================================
BenchScope Daily Intelligence Pipeline
============================================================

[1/8] 数据采集...
  ✓ ArxivCollector: 50条
  ✓ HelmCollector: 14条
  ✓ GitHubCollector: 150条 (🔧 修复后应该显著增加)
  ✓ HuggingFaceCollector: 43条
  ✓ TechEmpowerCollector: 46条
  ✓ DBEnginesCollector: 50条

[2/8] URL去重...
  ✓ 内部去重: 52条重复
  ✓ 飞书去重: 51条重复
  ✓ 保留: 150条新发现

[3/8] 规则预筛选...
  ✓ 保留: 60条 (60%过滤率)

[4/8] PDF内容增强...
  ✓ 增强: 45个arXiv论文

[5/8] LLM评分...
  ✓ 完成: 60条，耗时15秒

[6/8] 存储入库...
  ✓ 飞书多维表格写入成功

[7/8] 版本跟踪...
  检测到89个GitHub仓库，开始监控Release...
  ✓ GitHub Release: 3个更新
  检测到45个arXiv论文，开始监控版本...
  ✓ arXiv版本: 1个更新

[8/8] 飞书通知...
  ✓ 每日智能播报已推送

============================================================
Pipeline执行完成，总耗时65秒
============================================================
```

**验收标准**：
- ✅ [1/8] GitHub采集数量≥100（修复速率限制后）
- ✅ [7/8] 版本跟踪正常执行（不报错）
- ✅ [8/8] 飞书收到1条统一播报消息（不是2条分散消息）
- ✅ 总耗时≤90秒

---

### 4.2 集成测试

**测试3：GitHub Actions Workflow**

```bash
# 手动触发workflow测试
# 1. 访问: https://github.com/JasonRobertDestiny/BenchScope/actions
# 2. 选择 "BenchScope Daily Intelligence"
# 3. 点击 "Run workflow" → "Run workflow"
# 4. 观察执行日志
```

**验收标准**：
- ✅ Workflow执行成功（绿色✓）
- ✅ 日志显示8个步骤全部完成
- ✅ Artifacts上传成功（logs/ + fallback.db）
- ✅ 飞书群聊收到统一播报消息
- ✅ 执行时间≤20分钟（超时阈值）

---

**测试4：向后兼容性验证**

**独立脚本仍可用**：
```bash
# 测试独立运行track_github_releases.py（手动调试用）
cd /mnt/d/VibeCoding_pgm/BenchScope
.venv/bin/python scripts/track_github_releases.py

# 预期: 正常执行，独立推送GitHub Release更新
```

**理由**：保留脚本作为独立工具，便于手动调试和临时查询

---

## 五、成功标准与检查清单

### 5.1 功能完整性

- [ ] ✅ 新Benchmark发现功能保持不变
- [ ] ✅ GitHub Release监控正常工作
- [ ] ✅ arXiv版本监控正常工作
- [ ] ✅ 飞书统一播报消息格式清晰
- [ ] ✅ 独立脚本仍可手动运行（向后兼容）

### 5.2 性能指标

- [ ] ✅ 总执行时间≤90秒（vs 原2个workflow累计120秒）
- [ ] ✅ GitHub采集数量≥100（vs 原15个）
- [ ] ✅ CI/CD配额节省50%（1个workflow vs 2个）
- [ ] ✅ 飞书推送次数减少50%（1次 vs 2次）

### 5.3 代码质量

- [ ] ✅ 遵循PEP8规范（运行`ruff check .`）
- [ ] ✅ 关键逻辑有中文注释
- [ ] ✅ 函数嵌套≤3层（Linus规则）
- [ ] ✅ 无重复代码（DRY原则）

### 5.4 文档更新

- [ ] ✅ `.claude/CLAUDE.md`更新workflow说明
- [ ] ✅ `README.md`更新架构图
- [ ] ✅ Commit message遵循conventional格式

---

## 六、风险与回滚计划

### 6.1 风险识别

**风险1：版本跟踪失败阻断主流程**

- **概率**：低
- **影响**：高（整个Pipeline失败）
- **缓解措施**：Step 7用try-except包裹，失败不阻断

**风险2：统一播报消息过长被截断**

- **概率**：中
- **影响**：中（消息不完整）
- **缓解措施**：每个section限制条数（High 3条，Medium 2条，Low 1条）

**风险3：GitHub token未配置导致速率限制**

- **概率**：低（已在Step 3修复）
- **影响**：中（GitHub采集效率低）
- **缓解措施**：workflow配置`GITHUB_TOKEN`环境变量

### 6.2 回滚计划

**如果合并后出现严重问题**：

```bash
# 1. 立即恢复旧workflows
git revert <commit-hash>
git push

# 2. 或手动恢复文件
git checkout HEAD~1 .github/workflows/daily_collect.yml
git checkout HEAD~1 .github/workflows/track_releases.yml
git checkout HEAD~1 src/main.py
git checkout HEAD~1 src/notifier/feishu_notifier.py
git add .
git commit -m "revert: rollback workflow merge due to critical issue"
git push
```

**回滚标准**：
- 连续3次workflow执行失败
- 飞书通知完全失效
- 主流程执行时间>300秒（5分钟）

---

## 七、后续优化建议（可选）

**优化1：支持按需跳过版本跟踪**

```yaml
# workflow_dispatch支持输入参数
on:
  workflow_dispatch:
    inputs:
      skip_version_tracking:
        description: '跳过版本跟踪（加速调试）'
        required: false
        default: 'false'
```

**优化2：版本跟踪结果缓存**

- 避免重复检查同一个Release（24小时内）
- 使用Redis缓存已处理的Release tag

**优化3：飞书消息支持交互按钮**

```python
# 新Benchmark卡片添加按钮
await notifier.send_card_with_buttons(
    candidate=scored,
    buttons=[
        {"text": "✅ 采纳", "action": "approve"},
        {"text": "❌ 拒绝", "action": "reject"},
        {"text": "🔖 待评估", "action": "pending"}
    ]
)
```

---

## 八、提交与验收

### 8.1 Git Commit规范

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope

# Stage所有修改
git add .

# Commit（遵循conventional格式）
git commit -m "refactor(workflows): merge daily_collect and track_releases into unified workflow

- 新增: .github/workflows/daily_intelligence.yml (统一workflow)
- 删除: .github/workflows/daily_collect.yml (冗余)
- 删除: .github/workflows/track_releases.yml (冗余)
- 增强: src/notifier/feishu_notifier.py (新增notify_daily_report方法)
- 增强: src/main.py (新增Step 7版本跟踪, 改造Step 8统一播报)
- 修复: 添加GITHUB_TOKEN环境变量（解决速率限制）
- 文档: 更新.claude/CLAUDE.md和README.md

性能提升:
- CI/CD执行次数: 2次/天 → 1次/天 (-50%)
- 飞书推送次数: 2次/天 → 1次/天 (-50%)
- GitHub采集数量: 15个 → 150+个 (+900%)

向后兼容:
- 独立脚本保留（scripts/track_*.py）作为手动调试工具
- 飞书notify()方法保持不变"

# Push到GitHub
git push origin main
```

### 8.2 验收标准（Claude Code负责）

**测试任务**：

1. **单元测试**：运行测试脚本验证`notify_daily_report()`
2. **集成测试**：手动触发GitHub Actions workflow
3. **飞书验证**：检查飞书群聊收到统一播报消息
4. **性能验证**：检查workflow执行时间≤20分钟
5. **日志分析**：运行`scripts/analyze_logs.py`确认数据正常

**验收报告模板**：

```markdown
# Workflow合并验收报告

**测试时间**：2025-11-19

## 功能验证

- [x] ✅ 新Benchmark发现: 60条
- [x] ✅ GitHub Release监控: 3个更新
- [x] ✅ arXiv版本监控: 1个更新
- [x] ✅ 飞书统一播报: 已收到（附截图）

## 性能指标

- [x] ✅ GitHub采集数量: 150条（vs 原15条）
- [x] ✅ 总执行时间: 65秒（vs 原120秒）
- [x] ✅ Workflow成功率: 100%

## 问题与建议

- 无严重问题
- 建议: 后续可考虑添加版本跟踪结果缓存

## 验收结论

✅ **通过验收**，可以合并到main分支

**截图**：
![飞书统一播报](./docs/screenshots/unified-notification.png)
```

---

## 九、附录

### A. 文件清单

**新建文件**：
- `.github/workflows/daily_intelligence.yml` (统一workflow)

**修改文件**：
- `src/main.py` (新增Step 7, 改造Step 8)
- `src/notifier/feishu_notifier.py` (新增notify_daily_report方法)
- `.claude/CLAUDE.md` (更新workflow说明)
- `README.md` (更新架构图)

**删除文件**：
- `.github/workflows/daily_collect.yml` (冗余)
- `.github/workflows/track_releases.yml` (冗余)

**保留文件**（向后兼容）：
- `scripts/track_github_releases.py` (独立工具)
- `scripts/track_arxiv_versions.py` (独立工具)
- `src/tracker/github_tracker.py` (核心逻辑)
- `src/tracker/arxiv_tracker.py` (核心逻辑)

### B. 依赖关系图

```
daily_intelligence.yml
    ↓
src/main.py
    ├─ src/collectors/* (Step 1)
    ├─ src/prefilter/* (Step 3)
    ├─ src/scorer/* (Step 5)
    ├─ src/storage/* (Step 6)
    ├─ src/tracker/github_tracker.py (Step 7)
    ├─ src/tracker/arxiv_tracker.py (Step 7)
    └─ src/notifier/feishu_notifier.py (Step 8)
        └─ notify_daily_report() 🆕
```

### C. Linus哲学验证

**"Is this a real problem?"** → ✅ 是真问题
- 证据1：CI/CD配额浪费50%
- 证据2：用户需要查看2次飞书消息
- 证据3：维护2个workflow文件

**"Is there a simpler way?"** → ✅ 有更简单方案
- 方案1（复杂）：保持2个workflow，添加依赖
- 方案2（简单）：合并成1个workflow，统一数据流 ← 我们选择这个

**"What will this break?"** → ✅ 零破坏
- 向后兼容：独立脚本保留
- 向后兼容：notify()方法保持不变
- 向后兼容：所有Secret配置不变

---

**Codex执行建议**：

1. 按照Step 1→2→3→4→5顺序执行
2. 每完成一个Step，运行对应的单元测试
3. Step 3创建新workflow后，先不要删除旧workflow（保留备份）
4. 全部测试通过后，再执行Step 4删除旧workflow
5. 遇到问题立即停止，记录日志，交给Claude Code分析

**预计完成时间**：1-2小时

**交付标准**：
- ✅ 所有测试通过
- ✅ 代码质量检查通过（ruff + black）
- ✅ 文档更新完成
- ✅ Git commit提交并push
