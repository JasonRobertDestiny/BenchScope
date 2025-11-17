# Phase 7: MGX场景聚焦优化 PRD

**文档版本**: v1.0
**创建时间**: 2025-11-16
**负责人**: Claude Code
**执行人**: Codex
**预计工期**: 1-2周

---

## 1. 问题背景

### 1.1 当前痛点（数据驱动）

**运行数据（2025-11-14最新执行）**:
```
采集总数: 115条
高优先级: 4条（命中率3.5%）
平均分: 5.86/10（低于及格线6分）

采集源分布:
- HELM: 59条（51%）← 占比过高，且大部分是通用NLP评测
- HuggingFace: 40条（35%）
- GitHub: 15条（13%）
- arXiv: 1条（1%）
```

**核心问题**:
1. **泛化采集浪费资源**: 115条候选 → 仅4条高质量 → 浪费111条的LLM调用和人工审核
2. **场景不聚焦**: 大量通用NLP benchmark（对话/阅读理解/常识推理）与MGX核心场景（coding/webdev/GUI/Agent）无关
3. **HELM噪音过高**: HELM包含200+ benchmark，当前无过滤机制，采集了59条综合评测
4. **评分阶段才筛选**: 应该在采集阶段就聚焦，而不是等到评分后再发现无关

### 1.2 MGX核心场景定义

**MGX (https://mgx.dev)** = 多智能体协作框架，专注Vibe Coding（AI原生编程）

**核心技术方向**（优先级从高到低）:
1. **P0 - 编程与代码**
   - 代码生成/理解/补全
   - 程序修复/重构
   - 测试生成
   - 代码库理解

2. **P0 - Web自动化**
   - 浏览器操作（Selenium/Playwright）
   - Web UI测试
   - 网页信息抽取
   - Web Agent交互

3. **P1 - GUI自动化**
   - 桌面应用操作
   - 屏幕理解
   - UI元素识别

4. **P1 - 多智能体协作**
   - Agent任务规划
   - 工具调用/API使用
   - 多Agent协同决策

5. **P2 - 通用推理**（作为辅助能力）
   - 数学推理
   - 逻辑推理
   - 问题分解

**明确排除的领域**:
- ❌ 图像/视觉任务（ImageNet, COCO等）
- ❌ 语音/音频任务（LibriSpeech等）
- ❌ 纯NLP任务（情感分析/文本分类/机器翻译）
- ❌ 对话/聊天任务（除非与Agent协作相关）
- ❌ 阅读理解/常识推理（除非与代码理解相关）

---

## 2. 优化目标

### 2.1 核心目标

**提升采集精准度**:
- 命中率: 3.5% → **20-30%**（高优先级占比）
- 平均分: 5.86 → **6.5-7.5**
- 采集量: 115条 → **40-60条**（减少噪音，提升质量）

**降低人工审核成本**:
- 无关候选过滤率: 0% → **50-70%**（采集阶段过滤）
- LLM调用成本: ¥15/月 → **¥8-10/月**（减少无关候选的评分）

**聚焦MGX场景**:
- coding/web/GUI相关占比: <20% → **≥60%**
- 通用NLP占比: >50% → **<20%**

### 2.2 成功指标

| 指标 | 现状 | 目标 | 验收方式 |
|------|------|------|----------|
| 高优先级命中率 | 3.5% | ≥20% | 连续3次运行平均值 |
| 平均评分 | 5.86 | ≥6.5 | 连续3次运行平均值 |
| coding/web相关占比 | <20% | ≥60% | 人工标注100条样本 |
| HELM采集噪音 | 59条 | ≤15条 | 日志统计 |
| 月LLM成本 | ¥15 | ≤¥10 | GitHub Actions日志 |

---

## 3. 技术方案

### 3.1 方案概览

采用**三层过滤策略**:
```
Layer 1: 数据源关键词聚焦（修改config/sources.yaml）
  ↓ 过滤30-40%泛化内容
Layer 2: 采集器内置任务过滤（修改collectors/）
  ↓ 过滤20-30%无关任务
Layer 3: 预筛选规则增强（修改prefilter/rule_filter.py）
  ↓ 过滤10-20%边缘候选
───────────────────────
最终: 40-60条高质量候选 → LLM评分
```

### 3.2 Layer 1: 数据源关键词聚焦

**文件**: `config/sources.yaml`

**arXiv采集器优化**:
```yaml
# 修改前（泛化关键词）
keywords:
  - benchmark
  - agent evaluation
  - code generation
  - web automation

# 修改后（聚焦关键词组合）
keywords:
  # P0: 编程与代码
  - code generation benchmark
  - code evaluation
  - programming benchmark
  - software engineering benchmark
  - program synthesis evaluation
  - code completion benchmark

  # P0: Web自动化
  - web agent benchmark
  - browser automation benchmark
  - web navigation evaluation
  - GUI automation benchmark

  # P1: 多智能体
  - multi-agent benchmark
  - agent collaboration evaluation
  - tool use benchmark
  - API usage benchmark

# 新增类别过滤
categories:
  - cs.SE  # Software Engineering（新增）
  - cs.AI
  - cs.CL  # 保留（可能包含code-related NLP）
  # 移除: cs.CV, cs.MM（视觉/多媒体）
```

**GitHub采集器优化**:
```yaml
# 修改前（泛化topics）
topics:
  - benchmark
  - evaluation
  - agent

# 修改后（聚焦topics）
topics:
  # P0: 编程
  - code-generation
  - code-benchmark
  - program-synthesis
  - coding-challenge
  - software-testing

  # P0: Web自动化
  - web-automation
  - browser-automation
  - web-agent
  - selenium-testing
  - playwright

  # P1: GUI & Agent
  - gui-automation
  - agent-benchmark
  - multi-agent
  - llm-agent

# 新增语言过滤（可选）
languages:
  - Python
  - JavaScript
  - TypeScript
  # 排除: C++（可能是系统/图形相关）, Java（可能是企业应用）

# 提高stars门槛（减少低质量项目）
min_stars: 50  # 从0提升到50
```

**HuggingFace采集器优化**:
```yaml
# 修改前（泛化任务）
task_categories:
  - text-generation
  - question-answering
  - code

# 修改后（仅保留code）
task_categories:
  - code  # 代码相关数据集

# 新增关键词过滤
keywords:
  - code
  - programming
  - software
  - web
  - agent
  # 排除: dialogue, summarization, translation
```

**HELM采集器优化**（最关键）:
```yaml
# 新增配置项
helm:
  enabled: true
  base_url: "https://crfm.stanford.edu/helm/classic/latest/"
  timeout_seconds: 15

  # 新增：允许的任务类型（白名单）
  allowed_scenarios:
    - code  # 代码生成
    - reasoning  # 推理（数学/逻辑）
    - tool_use  # 工具使用
    - agent  # Agent任务

  # 新增：排除的任务类型（黑名单）
  excluded_scenarios:
    - qa  # 问答
    - reading_comprehension  # 阅读理解
    - summarization  # 摘要
    - dialogue  # 对话
    - common_sense  # 常识推理
    - translation  # 翻译
    - classification  # 分类
```

### 3.3 Layer 2: 采集器内置过滤

**HELM采集器代码增强** (`src/collectors/helm_collector.py`):

```python
class HelmCollector(BaseCollector):
    """HELM Leaderboard采集器（增强版）"""

    # 新增：任务类型白名单
    ALLOWED_TASKS = {
        "code", "coding", "program",  # 代码
        "math", "reasoning", "logic",  # 推理
        "tool", "api", "agent",       # 工具/Agent
        "web", "browser", "gui"       # Web/GUI
    }

    # 新增：任务类型黑名单
    EXCLUDED_TASKS = {
        "qa", "question", "answer",   # 问答
        "reading", "comprehension",   # 阅读
        "dialogue", "conversation",   # 对话
        "summarization", "summary",   # 摘要
        "translation", "translate",   # 翻译
        "sentiment", "classification", # 分类
        "image", "vision", "video"    # 视觉
    }

    def _is_relevant_scenario(self, scenario_name: str, description: str) -> bool:
        """判断HELM scenario是否与MGX场景相关"""
        text = f"{scenario_name} {description}".lower()

        # 1. 黑名单优先（包含任一排除词则过滤）
        if any(excluded in text for excluded in self.EXCLUDED_TASKS):
            logger.debug(f"过滤HELM scenario（黑名单）: {scenario_name}")
            return False

        # 2. 白名单验证（必须包含至少一个允许词）
        if not any(allowed in text for allowed in self.ALLOWED_TASKS):
            logger.debug(f"过滤HELM scenario（未命中白名单）: {scenario_name}")
            return False

        return True

    async def collect(self) -> List[RawCandidate]:
        """采集HELM benchmark（带任务过滤）"""
        # ... 原有采集逻辑 ...

        # 新增：在构建候选前过滤
        filtered_scenarios = [
            s for s in scenarios
            if self._is_relevant_scenario(s['name'], s.get('description', ''))
        ]

        logger.info(f"HELM过滤结果: {len(scenarios)}条 → {len(filtered_scenarios)}条")

        # 构建候选列表
        candidates = [self._build_candidate(s) for s in filtered_scenarios]
        return candidates
```

**GitHub采集器代码增强** (`src/collectors/github_collector.py`):

```python
class GitHubCollector(BaseCollector):
    """GitHub采集器（增强版）"""

    # 新增：README关键词白名单（至少包含一个）
    README_REQUIRED_KEYWORDS = {
        "benchmark", "evaluation", "dataset", "leaderboard",
        "test set", "eval", "metric", "baseline"
    }

    # 新增：README关键词黑名单（包含任一则过滤）
    README_EXCLUDED_KEYWORDS = {
        "awesome list", "curated", "collection", "resources",
        "tutorial", "course", "guide", "learning",
        "framework", "library", "tool", "sdk", "api wrapper"
    }

    async def _is_benchmark_repo(self, repo: Dict) -> bool:
        """判断仓库是否为真Benchmark（而非工具/教程）"""
        # 1. 获取README内容
        readme_text = await self._fetch_readme(repo['full_name'])
        if not readme_text:
            return False

        readme_lower = readme_text.lower()

        # 2. 黑名单过滤（awesome list/教程/工具）
        if any(excluded in readme_lower for excluded in self.README_EXCLUDED_KEYWORDS):
            logger.debug(f"过滤GitHub仓库（黑名单）: {repo['name']}")
            return False

        # 3. 白名单验证（必须包含benchmark相关词汇）
        if not any(keyword in readme_lower for keyword in self.README_REQUIRED_KEYWORDS):
            logger.debug(f"过滤GitHub仓库（非Benchmark）: {repo['name']}")
            return False

        return True

    async def collect(self) -> List[RawCandidate]:
        """采集GitHub（带Benchmark验证）"""
        repos = await self._search_repos()

        # 新增：并发验证是否为真Benchmark
        verification_tasks = [self._is_benchmark_repo(repo) for repo in repos]
        is_benchmark_list = await asyncio.gather(*verification_tasks)

        filtered_repos = [
            repo for repo, is_benchmark in zip(repos, is_benchmark_list)
            if is_benchmark
        ]

        logger.info(f"GitHub过滤结果: {len(repos)}条 → {len(filtered_repos)}条")

        candidates = [self._build_candidate(repo) for repo in filtered_repos]
        return candidates
```

### 3.4 Layer 3: 预筛选规则增强

**文件**: `src/prefilter/rule_filter.py`

```python
class RuleFilter:
    """规则预筛选器（增强版）"""

    # 新增：标题/摘要必需关键词（至少包含一个）
    REQUIRED_KEYWORDS = {
        # P0: 编程
        "code", "coding", "program", "programming", "software",
        # P0: Web
        "web", "browser", "gui", "ui", "frontend",
        # P1: Agent
        "agent", "tool", "api", "task",
        # P2: 推理
        "reasoning", "math", "logic"
    }

    # 新增：标题/摘要排除关键词（包含任一则过滤）
    EXCLUDED_KEYWORDS = {
        # 视觉/音频
        "image", "vision", "video", "speech", "audio",
        # 纯NLP
        "translation", "summarization", "sentiment", "classification",
        "dialogue", "conversation", "chatbot"
        # 资源汇总
        "awesome", "curated", "collection", "list of",
        # 工具/框架
        "framework", "library", "sdk", "wrapper"
    }

    def _check_keyword_relevance(self, candidate: RawCandidate) -> bool:
        """检查关键词相关性"""
        text = f"{candidate.title} {candidate.abstract or ''}".lower()

        # 1. 排除无关领域
        if any(excluded in text for excluded in self.EXCLUDED_KEYWORDS):
            logger.debug(f"过滤候选（排除关键词）: {candidate.title[:50]}")
            return False

        # 2. 必须命中MGX场景关键词
        if not any(required in text for required in self.REQUIRED_KEYWORDS):
            logger.debug(f"过滤候选（未命中场景关键词）: {candidate.title[:50]}")
            return False

        return True

    def prefilter_batch(
        self,
        candidates: List[RawCandidate]
    ) -> List[RawCandidate]:
        """批量预筛选（增强版）"""
        # 1. URL去重（保留）
        unique_candidates = self._deduplicate_by_url(candidates)

        # 2. 新增：关键词相关性过滤
        keyword_filtered = [
            c for c in unique_candidates
            if self._check_keyword_relevance(c)
        ]

        logger.info(
            f"关键词过滤: {len(unique_candidates)}条 → {len(keyword_filtered)}条 "
            f"(过滤{len(unique_candidates) - len(keyword_filtered)}条)"
        )

        # 3. GitHub特定规则（保留）
        github_filtered = [
            c for c in keyword_filtered
            if c.source != "GitHub" or self._check_github_quality(c)
        ]

        # 4. HuggingFace特定规则（保留）
        final_filtered = [
            c for c in github_filtered
            if c.source != "HuggingFace" or self._check_hf_quality(c)
        ]

        logger.info(
            f"预筛选完成: {len(candidates)}条 → {len(final_filtered)}条 "
            f"(总过滤率{(1 - len(final_filtered)/len(candidates))*100:.1f}%)"
        )

        return final_filtered
```

### 3.5 LLM评分Prompt增强（可选）

**文件**: `src/scorer/llm_scorer.py`

在system prompt中强化MGX场景判断：

```python
system_prompt = """你是一名AI Benchmark评审专家,专注于**编程/Web自动化/GUI/多智能体**领域。

MGX核心场景（高相关性 7-10分）:
- P0: 代码生成/理解/补全/修复 (如HumanEval, MBPP, CodeXGLUE)
- P0: Web自动化/浏览器操作 (如WebArena, Mind2Web)
- P1: GUI自动化/桌面应用 (如OSWorld, UIBert)
- P1: Agent工具调用/任务规划 (如ToolBench, AgentBench)

边缘场景（中相关性 4-6分）:
- P2: 数学/逻辑推理 (如GSM8K, MATH) ← 仅作为辅助能力
- P2: 通用推理 (如MMLU, HellaSwag) ← 需与代码/Agent结合

无关场景（低相关性 0-3分）:
- ❌ 纯NLP任务（情感分析/文本分类/翻译/摘要）
- ❌ 对话/聊天（除非是Agent交互）
- ❌ 阅读理解/常识推理（除非是代码理解）
- ❌ 图像/视觉/语音

**评分时必须明确说明与MGX场景的关联度**，不要仅凭"AI benchmark"就打高分。
"""
```

---

## 4. 实施计划

### 4.1 开发任务拆解

**Task 1: 数据源配置优化**（1天）
- [ ] 修改 `config/sources.yaml`
  - [ ] arXiv关键词聚焦（10 → 12个聚焦关键词组合）
  - [ ] GitHub topics聚焦（3 → 12个聚焦topics）
  - [ ] GitHub提高min_stars（0 → 50）
  - [ ] HuggingFace任务类别收窄（3 → 1）
  - [ ] HELM新增allowed/excluded_scenarios配置
- [ ] 编写配置变更文档（说明修改理由）

**Task 2: HELM采集器增强**（2天）
- [ ] 修改 `src/collectors/helm_collector.py`
  - [ ] 新增 `ALLOWED_TASKS` / `EXCLUDED_TASKS` 常量
  - [ ] 实现 `_is_relevant_scenario()` 任务过滤方法
  - [ ] 在 `collect()` 中集成任务过滤
  - [ ] 添加详细日志（过滤前后数量）
- [ ] 单元测试（测试场景过滤逻辑）

**Task 3: GitHub采集器增强**（2天）
- [ ] 修改 `src/collectors/github_collector.py`
  - [ ] 新增 `README_REQUIRED_KEYWORDS` / `README_EXCLUDED_KEYWORDS`
  - [ ] 实现 `_fetch_readme()` 方法（获取README内容）
  - [ ] 实现 `_is_benchmark_repo()` Benchmark验证方法
  - [ ] 在 `collect()` 中集成验证逻辑
  - [ ] 添加详细日志
- [ ] 单元测试（测试Benchmark识别）

**Task 4: 预筛选规则增强**（1.5天）
- [ ] 修改 `src/prefilter/rule_filter.py`
  - [ ] 新增 `REQUIRED_KEYWORDS` / `EXCLUDED_KEYWORDS`
  - [ ] 实现 `_check_keyword_relevance()` 关键词过滤方法
  - [ ] 在 `prefilter_batch()` 中集成关键词过滤
  - [ ] 优化日志输出（显示各阶段过滤率）
- [ ] 单元测试

**Task 5: LLM Prompt优化**（可选，0.5天）
- [ ] 修改 `src/scorer/llm_scorer.py`
  - [ ] 强化system prompt中的MGX场景定义
  - [ ] 更新示例（添加边缘场景示例）
- [ ] 测试评分准确性（抽样10条验证）

**Task 6: 集成测试与调优**（2天）
- [ ] 完整流程测试
  - [ ] 运行完整pipeline（采集→预筛→评分→入库）
  - [ ] 记录各层过滤效果（Layer 1/2/3过滤率）
  - [ ] 人工标注100条样本（验证场景相关性）
- [ ] 调优
  - [ ] 根据测试结果调整关键词/阈值
  - [ ] 优化过滤策略（平衡精准率和召回率）
- [ ] 文档更新
  - [ ] 更新CLAUDE.md（新增Phase 7说明）
  - [ ] 编写测试报告

### 4.2 时间线

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| Task 1 | Day 1 | 配置文件 + 变更文档 |
| Task 2 | Day 2-3 | HELM采集器代码 + 单元测试 |
| Task 3 | Day 4-5 | GitHub采集器代码 + 单元测试 |
| Task 4 | Day 6-7 | 预筛选规则代码 + 单元测试 |
| Task 5 | Day 7 | LLM Prompt优化（可选） |
| Task 6 | Day 8-9 | 集成测试 + 调优 + 文档 |
| **总计** | **9天** | **完整优化版本** |

---

## 5. 风险与应对

### 5.1 风险识别

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|----------|
| 过度过滤导致遗漏优质benchmark | 中 | 高 | 保留详细日志，定期复盘过滤掉的候选 |
| GitHub API限流（频繁获取README） | 中 | 中 | 添加缓存机制，控制并发请求速率 |
| HELM任务分类不准确 | 低 | 中 | 人工验证前50条，调整分类规则 |
| 关键词列表维护成本高 | 低 | 低 | 支持动态配置（yaml），无需改代码 |

### 5.2 降级方案

如果优化后命中率反而下降：
1. **快速回滚**: 保留旧配置为 `sources.yaml.backup`，一键恢复
2. **渐进式调整**: 先启用Layer 1（配置优化），验证后再启用Layer 2/3
3. **AB测试**: 保留旧流程7天，对比优化前后数据

---

## 6. 验收标准

### 6.1 功能验收

- [ ] **配置生效**: 修改 `config/sources.yaml` 后，下次运行立即生效
- [ ] **HELM过滤**: 采集数从59条降至≤15条
- [ ] **GitHub过滤**: 能识别并排除awesome list/教程/工具类仓库
- [ ] **关键词过滤**: 能过滤纯NLP/视觉/音频等无关候选
- [ ] **日志完整**: 各层过滤结果清晰记录在日志中
- [ ] **零破坏**: 不影响现有飞书存储/通知功能

### 6.2 性能验收

运行3次完整pipeline，验证以下指标：

| 指标 | 基线（优化前） | 目标（优化后） | 验收方式 |
|------|---------------|---------------|----------|
| 采集总数 | 115条 | 40-60条 | 日志统计 |
| 高优先级命中率 | 3.5% | ≥20% | (高优先级数/采集总数) × 100% |
| 平均评分 | 5.86 | ≥6.5 | sum(scores) / count |
| coding/web相关占比 | <20% | ≥60% | 人工标注100条样本 |
| HELM采集数 | 59条 | ≤15条 | 日志统计 |
| 月LLM成本 | ¥15 | ≤¥10 | 月总token消耗 × 单价 |

### 6.3 代码质量验收

- [ ] **PEP8合规**: 运行 `black .` 和 `ruff check .` 无错误
- [ ] **单元测试覆盖**: 新增代码单元测试覆盖率≥80%
- [ ] **中文注释**: 关键逻辑必须有中文注释
- [ ] **常量管理**: 魔法数字定义在 `src/common/constants.py`
- [ ] **错误处理**: API调用有超时/重试机制

---

## 7. 后续优化方向（Phase 8+）

1. **动态关键词学习**: 基于历史高分候选，自动学习有效关键词
2. **专用采集源接入**: 接入EvalPlus, CodeXGLUE等专注coding的平台
3. **用户反馈闭环**: 飞书卡片添加"不相关"按钮，自动调整过滤策略
4. **相似度去重**: 使用embedding检测重复benchmark（如HumanEval-X vs HumanEval）

---

## 8. 参考文档

- `.claude/specs/benchmark-intelligence-agent/01-product-requirements.md` - 原始PRD
- `.claude/specs/benchmark-intelligence-agent/02-system-architecture.md` - 系统架构
- `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md` - Phase 6 PRD
- `config/sources.yaml` - 当前数据源配置
- `docs/phase2-5-test-report.md` - Phase 2-5测试报告

---

**文档结束**
**下一步**: 交付Codex执行 → 编写 `CODEX-PHASE7-DETAILED.md`
