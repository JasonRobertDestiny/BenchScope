# BenchScope Phase 2完成后 - 下一步行动指南

**文档创建日期**: 2025-11-13
**当前状态**: Phase 2 Task 1-7 全部完成并验收通过 (14/14单元测试通过)

---

## 当前成果总结

✅ **Phase 2核心功能已完成**:
1. **数据采集**: ArxivCollector, GitHubCollector, PwCCollector, HuggingFaceCollector
2. **规则预筛选**: 5条规则过滤50%噪音
3. **LLM评分**: 5维度评分 + Redis缓存 + 兜底评分
4. **飞书存储**: 批量写入(20条/批) + 主备切换 + 自动降级
5. **飞书通知**: Top 5卡片消息推送
6. **主流程**: 5步骤编排 + 日志配置 + 统计输出
7. **GitHub Actions**: 定时任务 + 环境变量 + Artifacts上传

✅ **质量保证**:
- 14个单元测试全部通过
- 代码符合PEP8规范
- 完整的错误处理与降级机制
- 详细的测试报告文档

---

## Option A: 手动测试与生产部署准备 (推荐优先)

**目标**: 验证完整流程，配置真实API，准备上线

### A.1 GitHub Secrets配置 (必须)

在GitHub仓库设置中配置以下Secrets:

```bash
# OpenAI API配置
OPENAI_API_KEY=sk-xxx  # 真实的OpenAI API密钥
OPENAI_MODEL=gpt-4o-mini  # 可选，默认gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，默认OpenAI官方

# 飞书API配置
FEISHU_APP_ID=cli_xxx  # 飞书应用ID
FEISHU_APP_SECRET=xxx  # 飞书应用密钥
FEISHU_BITABLE_APP_TOKEN=xxx  # 飞书多维表格app_token
FEISHU_BITABLE_TABLE_ID=tbl_xxx  # 飞书表格table_id
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx  # 飞书Webhook URL

# HuggingFace配置 (可选)
HUGGINGFACE_TOKEN=hf_xxx  # 仅当HuggingFace采集器需要认证时配置
```

**如何获取飞书凭证**:
1. 飞书开放平台创建企业自建应用
2. 开通"多维表格"权限
3. 创建Webhook机器人并获取URL
4. 创建多维表格并获取app_token和table_id

**验证命令**:
```bash
# 本地测试（需先创建.env.local）
echo 'OPENAI_API_KEY=sk-xxx
FEISHU_APP_ID=cli_xxx
# ... 其他配置
' > .env.local

PYTHONPATH=. python -m src.main
```

### A.2 手动测试清单

**测试步骤**:
1. **GitHub Actions手动触发**
   - 访问 Actions → BenchScope Daily Collection → Run workflow
   - 等待执行完成（预计5-20分钟）

2. **检查执行日志**
   - 下载Artifacts: `benchscope-logs` 和 `sqlite-backup`
   - 查看日志: `logs/benchscope.log`
   - 验证5个步骤都成功执行

3. **验证飞书多维表格**
   - 打开飞书多维表格
   - 检查是否有新数据写入
   - 验证字段映射正确: 标题、来源、总分、优先级等

4. **验证飞书通知**
   - 检查飞书群是否收到通知消息
   - 验证卡片格式正确
   - 验证Top 5排序正确

5. **验证降级机制**（可选）
   - 故意使用错误的飞书凭证触发失败
   - 检查日志是否显示"降级到SQLite"
   - 下载sqlite-backup验证数据完整性

**预期结果**:
```
============================================================
BenchScope Phase 2 完成
  采集: XX条
  预筛选: XX条
  高优先级: XX条
  中优先级: XX条
  平均分: X.XX/10
============================================================
```

### A.3 生产部署检查清单

- [ ] GitHub Secrets全部配置正确
- [ ] 手动触发GitHub Actions成功运行
- [ ] 飞书多维表格有数据写入
- [ ] 飞书群收到通知消息
- [ ] 日志上传到Artifacts
- [ ] SQLite备份正常
- [ ] 定时任务cron表达式正确 (UTC 2:00 = 北京10:00)
- [ ] 监控指标设置（可选，如飞书告警）

**部署后监控建议**:
1. 每周检查一次Artifacts日志
2. 每周检查飞书多维表格数据增长
3. 每月复盘候选池质量（实际使用率）

---

## Option B: Phase 3增强功能 (可选优化)

**目标**: 提升性能、用户体验、数据质量

### B.1 性能优化 (预计2-3天)

#### 1. 并发采集优化
**当前状态**: 串行采集（for循环）
**优化方案**: 使用`asyncio.gather`并发采集

**实现示例**:
```python
# src/main.py
async def main():
    # Step 1: 并发数据采集
    logger.info("[1/5] 数据采集...")
    collectors = [
        ArxivCollector(),
        GitHubCollector(),
        PwCCollector(),
        HuggingFaceCollector(settings=settings),
    ]

    # 并发执行
    results = await asyncio.gather(*[c.collect() for c in collectors], return_exceptions=True)

    all_candidates = []
    for collector, result in zip(collectors, results):
        if isinstance(result, Exception):
            logger.error("  ✗ %s失败: %s", collector.__class__.__name__, result)
        else:
            all_candidates.extend(result)
            logger.info("  ✓ %s: %d条", collector.__class__.__name__, len(result))
```

**预期收益**: 采集耗时从15秒降至5秒（3倍提速）

#### 2. 并发评分优化
**当前状态**: `score_batch`内部已并发，但可加限流

**优化方案**: 使用`asyncio.Semaphore`限制并发数

**实现示例**:
```python
# src/scorer/llm_scorer.py
async def score_batch(self, candidates: List[RawCandidate]) -> List[ScoredCandidate]:
    semaphore = asyncio.Semaphore(constants.LLM_MAX_CONCURRENT)  # 默认5

    async def score_with_limit(candidate: RawCandidate) -> ScoredCandidate:
        async with semaphore:
            return await self.score(candidate)

    tasks = [score_with_limit(c) for c in candidates]
    results = await asyncio.gather(*tasks)
    return list(results)
```

**预期收益**: 防止LLM API限流，提升稳定性

### B.2 飞书卡片消息增强 (预计1天)

**当前状态**: 纯文本卡片
**优化方案**: 增加交互按钮

**功能**:
- "👍 一键添加到候选池" 按钮
- "👎 忽略此候选" 按钮
- "📌 稍后查看" 按钮

**技术实现**:
1. 飞书卡片增加`actions`字段
2. Flask接收飞书回调 (POST `/feishu/callback`)
3. 更新飞书多维表格状态字段

**代码示例**:
```python
# src/notifier/feishu_notifier.py
def _build_card(self, candidates: List[ScoredCandidate]) -> dict:
    elements = [...]

    # 增加交互按钮
    actions = {
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "👍 添加"},
                "type": "primary",
                "value": {"action": "approve", "url": candidate.url}
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "👎 忽略"},
                "type": "default",
                "value": {"action": "reject", "url": candidate.url}
            }
        ]
    }
    elements.append(actions)

    return {...}
```

### B.3 数据源扩展 (预计2-3天)

#### 1. HuggingFace数据集监控
**实现内容**:
- 监控HuggingFace Datasets trending
- 监控带"benchmark"标签的新数据集

#### 2. AgentBench/HELM榜单跟踪
**实现内容**:
- 爬取AgentBench官网更新
- 爬取HELM榜单变化

#### 3. Twitter关键词监控 (可选)
**实现内容**:
- 使用Twitter API搜索关键词
- 过滤高质量推文（高follower账号）

### B.4 版本跟踪功能 (预计1周)

#### 1. GitHub Release监控
**功能**: 已入库的Benchmark如果发布新版本，自动通知

**实现方案**:
```python
# src/tracker/github_tracker.py
async def check_updates(self) -> List[BenchmarkUpdate]:
    # 从飞书多维表格读取已入库候选
    existing = await self.fetch_existing_benchmarks()

    updates = []
    for benchmark in existing:
        if not benchmark.github_url:
            continue

        latest_release = await self.fetch_latest_release(benchmark.github_url)
        if latest_release and latest_release > benchmark.version:
            updates.append(BenchmarkUpdate(
                title=benchmark.title,
                old_version=benchmark.version,
                new_version=latest_release,
                url=benchmark.github_url
            ))

    return updates
```

#### 2. arXiv版本更新提醒
**功能**: arXiv论文更新到v2/v3时通知

#### 3. Leaderboard SOTA变化追踪
**功能**: Papers with Code榜单排名变化通知

---

## Option C: 前端开发 (独立项目)

**目标**: 构建BenchScope Web界面，替代飞书多维表格

**技术栈**: FastAPI + Jinja2 + HTMX + TailwindCSS + Chart.js

**已完成**: 完整的前端设计方案 (`docs/frontend-design.md`)

**实施时间**: 2-3周

**关键功能**:
1. Dashboard (统计概览)
2. Candidate List (候选列表 + 过滤器)
3. Candidate Detail (详情Modal + 5维雷达图)
4. Review Actions (Approve/Reject/Defer)
5. Statistics Page (趋势图表)

**是否推荐**: 根据团队需求决定
- 如果飞书多维表格已满足需求 → 暂缓
- 如果需要更灵活的界面/权限控制 → 推进

---

## 决策建议

**推荐路径** (基于Linus简单哲学):

### 第一优先级: Option A - 手动测试与部署
**理由**:
1. 验证Phase 2核心功能可用
2. 开始产生实际价值（每日自动采集）
3. 低成本（仅需配置Secrets）

**执行时间**: 1-2小时

### 第二优先级: Option B.1 - 性能优化
**理由**:
1. 技术成熟（asyncio.gather）
2. 收益明显（3倍提速）
3. 不破坏现有功能

**执行时间**: 1天

### 第三优先级: Option B.2 - 飞书卡片增强
**理由**:
1. 显著提升用户体验
2. 减少人工操作
3. 技术难度中等

**执行时间**: 1-2天

### 可选项: Option B.3/B.4 - 数据源扩展/版本跟踪
**理由**:
- 先验证现有数据源价值
- 根据3个月实际使用情况决定

### 待定项: Option C - 前端开发
**理由**:
- 飞书多维表格已满足基本需求
- 前端投入大（2-3周）
- 建议等Phase 2稳定运行3个月后再评估

---

## 下一步开发Prompt模板

根据上述决策，选择对应的Prompt交给Codex:

### Prompt A: 手动测试准备 (人工执行，无需Codex)
```
用户: 我需要配置GitHub Secrets并手动测试BenchScope。

Claude: 请按照以下步骤配置...
```

### Prompt B1: 并发采集优化
```
Codex开发指令:

目标: 优化BenchScope数据采集性能，使用asyncio.gather并发执行4个采集器。

要求:
1. 修改src/main.py中的Step 1数据采集部分
2. 使用asyncio.gather并发执行所有采集器
3. 使用return_exceptions=True捕获单个采集器异常
4. 保留原有日志输出格式
5. 新增"总采集耗时"日志

验收标准:
- 采集器并发执行（不再串行）
- 单个采集器失败不影响其他
- 日志清晰显示每个采集器结果
- 单元测试通过: pytest tests/unit -v
```

### Prompt B2: 飞书卡片交互按钮
```
Codex开发指令:

目标: 为飞书卡片消息增加交互按钮（Approve/Reject/Defer）。

要求:
1. 修改src/notifier/feishu_notifier.py的_build_card()
2. 增加actions字段，包含3个按钮
3. 新建src/api/feishu_callback.py处理回调
4. 使用Flask框架 (轻量级)
5. 更新飞书多维表格状态字段

技术细节:
- 飞书卡片actions格式参考官方文档
- Flask接收POST /feishu/callback
- 验证飞书签名（防伪造）
- 异步更新飞书表格

验收标准:
- 飞书卡片显示3个按钮
- 点击按钮触发回调
- 飞书表格状态字段更新
- 单元测试通过
```

---

**决策建议**: 优先执行 Option A (手动测试) → Option B.1 (并发优化) → 根据实际需求决定后续

**文档维护**: 本文档随项目进展更新，记录每个Option的执行状态。
