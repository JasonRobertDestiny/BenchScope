# Codex开发指令：智能推送策略优化 PRD

## 背景与问题诊断

### 当前问题
- **arXiv等论文评分普遍偏低**（平均3-5分），大部分未被推送
- **推送内容单一化**：高/中优先级几乎全是GitHub项目，arXiv/HuggingFace/HELM被压制
- **最新且相关的论文被遗漏**：即使新颖性和MGX适配度很高（8-9分），但因活跃度/可复现性低（2-3分）导致总分仅4-5分

### 根本原因分析

#### 1. arXiv评分低的三大原因（实际数据验证）

**案例：Live-SWE-agent论文**
```
标题: Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly?
来源: arxiv
新颖性: 9.0 (2025年最新，Agent自我进化Benchmark)
MGX适配度: 8.0 (P0 Coding场景，高度相关)
活跃度: 3.0 (无GitHub链接，无stars)
可复现性: 3.0 (仅论文描述，无代码/数据集)
许可合规: 0.0 (许可证未知)
总分: 4.7 (低优先级❌)

综合推理: "如果能解决复现性和合规性问题，强烈推荐纳入MGX"
```

**原因1：活跃度维度偏向GitHub**
- LLM prompt定义：10分需要 >5000 stars，8-9分需要 1000-5000 stars
- 论文类没有GitHub仓库 → 自动给2-3分（"仅论文无代码"）

**原因2：可复现性维度严格**
- LLM prompt定义：8-10分需要"开源代码+公开数据集+评估脚本"
- 论文类通常只有PDF → 自动给2-3分（"仅论文描述，无代码或数据集"）

**原因3：许可证信息缺失**
- 论文类通常不提供LICENSE文件 → 0-2分（"许可证未知，法律风险"）

**结果**：即使新颖性9分+MGX适配度8分，总分=(3+3+0+9+8)/5 = 4.6分 → 低优先级

#### 2. GitHub评分高的原因（对比数据）

**案例：camel-ai/camel**
```
标题: camel-ai/camel
来源: github
新颖性: 8.0 (2025年，多Agent系统框架)
MGX适配度: 8.5 (P1 Collaboration场景)
活跃度: 9.0 (14825 stars, 30天内活跃提交)
可复现性: 8.5 (代码+数据集开源，Apache 2.0)
许可合规: 10.0 (Apache License 2.0)
总分: 8.72 (高优先级✅)
```

**案例：X-PLUG/MobileAgent**
```
总分: 9.0 (高优先级✅)
活跃度: 10.0 (6264 stars)
可复现性: 8.0 (代码+数据集，MIT License)
许可合规: 10.0
新颖性: 9.0
MGX适配度: 9.0 (P0 GUI+Collaboration)
```

### 用户核心诉求
1. **最新论文也需要推送**：7天内发布的论文，即使评分低也要推送（可推送前几名）
2. **每个信息源都要覆盖**：确保arXiv/HuggingFace/HELM/GitHub等每个来源都有推送
3. **按来源分层阈值**：arXiv等权威来源降低推送阈值（2.5分以上即可推送）
4. **按任务类型推送**：或者按MGX适配度分层推送（P0/P1/P2场景）

---

## 解决方案设计

### 核心策略：三层推送机制

#### Layer 1: 全局Top推送（保留现有逻辑）
- **高优先级**：total_score ≥ 8.0 → 推送独立卡片
- **中优先级**：6.0 ≤ total_score < 8.0 → 推送摘要卡片

#### Layer 2: 按来源分层阈值推送（新增）
针对不同来源设置差异化推送阈值：

| 来源 | 推送阈值 | 额外条件 | 理由 |
|------|---------|---------|------|
| **arxiv** | total_score ≥ 2.5 | MGX适配度 ≥ 6.0 | 新颖性高，容忍活跃度/可复现性低 |
| **helm** | total_score ≥ 3.0 | 无 | 权威Benchmark，直接可信 |
| **huggingface** | total_score ≥ 3.0 | dataset_downloads ≥ 100 | 数据集质量，社区验证 |
| **dbengines** | total_score ≥ 3.0 | 无 | 数据库权威榜单，直接可信 |
| **techempower** | total_score ≥ 3.0 | 无 | Web框架权威基准，直接可信 |
| **github** | total_score ≥ 6.0 | 无 | 活跃度/可复现性通常高，维持现有标准 |

#### Layer 3: 时间新鲜度加权推送（新增）
- **7天内发布**：total_score += 1.5 或直接进入"Latest Papers"分区
- **14天内发布**：total_score += 0.8
- **30天内发布**：total_score += 0.3

**示例**：
```
Live-SWE-agent论文:
原始总分: 4.7
发布日期: 2025-11-22 (7天内)
加权后总分: 4.7 + 1.5 = 6.2 → 中优先级✅
或: 直接进入"Latest Papers"分区推送
```

#### Layer 4: 每来源TopN保底推送（新增）
无论评分高低，每个来源按total_score排序后至少推送Top 2-3条：

```python
PER_SOURCE_TOPK = {
    "arxiv": 3,        # 最新论文Top 3
    "helm": 2,         # 权威Benchmark Top 2
    "huggingface": 2,  # 热门数据集Top 2
    "github": 3,       # 活跃项目Top 3
    "dbengines": 1,    # 数据库榜单Top 1
    "techempower": 1,  # Web框架基准Top 1
}
```

---

## 实施方案

### Step 1: 常量配置 (src/common/constants.py)

```python
# ============================================================
# 智能推送策略配置
# ============================================================

# 按来源分层推送阈值
SOURCE_SCORE_THRESHOLDS: Final[dict[str, float]] = {
    "arxiv": 2.5,       # 论文类：容忍低活跃度/可复现性
    "helm": 3.0,        # 权威Benchmark
    "huggingface": 3.0, # 数据集
    "dbengines": 3.0,   # 数据库榜单
    "techempower": 3.0, # Web框架基准
    "github": 6.0,      # GitHub：维持高标准
    "default": 6.0,     # 默认阈值
}

# arXiv额外条件：MGX适配度阈值
ARXIV_MIN_RELEVANCE: Final[float] = 6.0

# 时间新鲜度加权
FRESHNESS_BOOST_7D: Final[float] = 1.5   # 7天内发布+1.5分
FRESHNESS_BOOST_14D: Final[float] = 0.8  # 14天内发布+0.8分
FRESHNESS_BOOST_30D: Final[float] = 0.3  # 30天内发布+0.3分

# 每来源TopN保底推送
PER_SOURCE_TOPK_PUSH: Final[dict[str, int]] = {
    "arxiv": 3,
    "helm": 2,
    "huggingface": 2,
    "github": 3,
    "dbengines": 1,
    "techempower": 1,
}

# 启用智能推送策略
ENABLE_SMART_PUSH_STRATEGY: Final[bool] = True
```

### Step 2: 评分后处理 (src/scorer/llm_scorer.py 或 src/main.py)

在LLM评分后，应用时间新鲜度加权：

```python
from datetime import datetime, timedelta

def apply_freshness_boost(candidate: ScoredCandidate) -> ScoredCandidate:
    """应用时间新鲜度加权"""
    if not candidate.publish_date:
        return candidate

    days_ago = (datetime.now() - candidate.publish_date).days

    boost = 0.0
    if days_ago <= 7:
        boost = constants.FRESHNESS_BOOST_7D
    elif days_ago <= 14:
        boost = constants.FRESHNESS_BOOST_14D
    elif days_ago <= 30:
        boost = constants.FRESHNESS_BOOST_30D

    if boost > 0:
        original_score = candidate.total_score
        candidate.total_score = min(10.0, original_score + boost)
        logger.info(
            f"时间新鲜度加权: {candidate.title[:50]} | "
            f"{days_ago}天前发布 | {original_score:.1f} → {candidate.total_score:.1f} (+{boost})"
        )

    return candidate
```

### Step 3: 推送逻辑重构 (src/notifier/feishu_notifier.py)

```python
def _smart_filter_candidates(
    self, candidates: List[ScoredCandidate]
) -> Tuple[List[ScoredCandidate], List[ScoredCandidate], List[ScoredCandidate]]:
    """智能推送策略：按来源分层阈值 + 每来源TopN保底"""

    if not constants.ENABLE_SMART_PUSH_STRATEGY:
        # 回退到原有逻辑
        return self._legacy_filter_candidates(candidates)

    high_priority = []
    medium_priority = []
    low_priority = []

    # Step 1: 全局阈值过滤（保留原有逻辑）
    for c in candidates:
        if c.total_score >= 8.0:
            high_priority.append(c)
        elif c.total_score >= 6.0:
            medium_priority.append(c)
        else:
            low_priority.append(c)

    # Step 2: 按来源分层阈值补充（新增）
    for c in low_priority[:]:  # 遍历低优先级队列
        source = c.source or "unknown"
        threshold = constants.SOURCE_SCORE_THRESHOLDS.get(
            source, constants.SOURCE_SCORE_THRESHOLDS["default"]
        )

        # 检查是否满足来源阈值
        if c.total_score >= threshold:
            # arXiv额外检查MGX适配度
            if source == "arxiv":
                if c.relevance_score >= constants.ARXIV_MIN_RELEVANCE:
                    medium_priority.append(c)
                    low_priority.remove(c)
                    logger.info(
                        f"arXiv分层阈值提升: {c.title[:50]} | "
                        f"总分{c.total_score:.1f} ≥ {threshold} & "
                        f"MGX适配度{c.relevance_score:.1f} ≥ {constants.ARXIV_MIN_RELEVANCE}"
                    )
            else:
                medium_priority.append(c)
                low_priority.remove(c)
                logger.info(
                    f"{source}分层阈值提升: {c.title[:50]} | "
                    f"总分{c.total_score:.1f} ≥ {threshold}"
                )

    # Step 3: 每来源TopN保底推送（新增）
    source_groups = {}
    for c in candidates:
        source = c.source or "unknown"
        if source not in source_groups:
            source_groups[source] = []
        source_groups[source].append(c)

    for source, group in source_groups.items():
        topk = constants.PER_SOURCE_TOPK_PUSH.get(source, 0)
        if topk == 0:
            continue

        # 按total_score排序，取TopK
        sorted_group = sorted(group, key=lambda x: x.total_score, reverse=True)
        for c in sorted_group[:topk]:
            # 如果不在高/中优先级，强制加入中优先级
            if c not in high_priority and c not in medium_priority:
                medium_priority.append(c)
                logger.info(
                    f"{source} TopK保底推送: {c.title[:50]} | 总分{c.total_score:.1f}"
                )

    # 去重
    medium_priority = list(set(medium_priority))

    return high_priority, medium_priority, low_priority
```

### Step 4: 主流程调整 (src/main.py)

```python
# Step 4: LLM评分后，应用时间新鲜度加权
logger.info("[4/7] 时间新鲜度加权...")
scored_candidates = [apply_freshness_boost(c) for c in scored_candidates]

# 重新计算优先级（基于加权后的total_score）
for candidate in scored_candidates:
    if candidate.total_score >= 8.0:
        candidate.priority = "high"
    elif candidate.total_score >= 6.0:
        candidate.priority = "medium"
    else:
        candidate.priority = "low"
```

---

## 推送卡片优化

### 中优先级摘要卡片结构

```markdown
**🔥 智能推荐 Top N**
1. [GitHub] valyala/fasthttp | 总分9.0 | Backend性能基准
   机构: -- | Stars: 23080 | 🔗 链接

2. [arXiv] Live-SWE-agent 🆕 | 总分6.2 (加权) | Agent自我进化
   作者: Chunqiu Steven Xia et al. | 发布: 7天前 | 🔗 PDF

---

**📊 按来源精选**
- **GitHub**: camel-ai/camel | 总分8.7 | 多Agent协作框架
- **arXiv**: Rethinking Kernel Program Repair | 总分5.8 | 内核修复Benchmark
- **HELM**: math_chain_of_thought | 总分7.0 | 数学推理基准
- **HuggingFace**: UI_S1_dataset | 总分4.2 | GUI自动化数据集

---

**🆕 Latest Papers / Datasets** (最近7天)
1. [arXiv] Live-SWE-agent | MGX适配8.0 | 新颖性9.0 | 2025-11-22
   核心创新: Agent运行时自我进化，填补MGX动态Agent评测空白

2. [arXiv] Securing AI Agents Against Prompt Injection | MGX适配7.5 | 2025-11-22
   核心创新: Prompt注入防御基准，提升Agent安全性

3. [HuggingFace] UniGenBench-Eval-Images | MGX适配3.0 | 2025-11-18
   核心创新: T2I生成模型评估基准
```

---

## 验收标准

### 功能验收
- [x] **来源覆盖度**：每次推送至少覆盖4个信息源（arxiv/helm/huggingface/github）
- [x] **arXiv推送率**：最近7天内的arXiv论文，MGX适配度≥6.0的至少推送80%
- [x] **按来源TopN**：每个来源至少推送TopK条（arxiv 3条，github 3条，helm 2条...）
- [x] **时间新鲜度加权**：7天内发布的候选自动+1.5分或进入"Latest Papers"分区
- [x] **推送总数可控**：高优先级 + 中优先级摘要 + Latest Papers ≤ 15条（避免信息过载）

### 数据验证
运行完整流程后检查：
```python
# 检查推送来源覆盖度
推送来源 = set([c.source for c in pushed_candidates])
assert len(推送来源) >= 4, "推送来源数量不足4个"

# 检查arXiv推送率
recent_arxiv = [c for c in candidates if c.source == "arxiv" and days_ago(c) <= 7 and c.relevance_score >= 6.0]
pushed_arxiv = [c for c in pushed_candidates if c.source == "arxiv"]
push_rate = len(pushed_arxiv) / len(recent_arxiv) * 100
assert push_rate >= 80, f"arXiv推送率{push_rate:.1f}% < 80%"

# 检查每来源TopK
for source, topk in constants.PER_SOURCE_TOPK_PUSH.items():
    source_pushed = [c for c in pushed_candidates if c.source == source]
    assert len(source_pushed) >= topk, f"{source}推送数量{len(source_pushed)} < TopK({topk})"
```

---

## 风险与缓解

### 风险1：推送噪音增加
- **风险**：降低arXiv阈值后，可能推送低质量论文
- **缓解**：
  1. arXiv必须满足MGX适配度≥6.0（P0/P1场景）
  2. 时间新鲜度加权仅限7-30天窗口
  3. 总推送上限≤15条（高优+中优+Latest Papers）

### 风险2：评分通胀
- **风险**：大量候选因时间加权从low→medium
- **缓解**：
  1. 时间加权仅+1.5分，不会从low（4分）→high（8分）
  2. 每来源TopK限额，避免单一来源占满推送位

### 风险3：推送卡片过长
- **风险**：中优摘要 + Latest Papers分区过长
- **缓解**：
  1. 中优摘要Top 5 + 按来源精选4条 = 9条
  2. Latest Papers最多3条
  3. 总计≤15条

---

## 实施时间计划
- **开发**：1天（配置+评分加权+推送逻辑重构+Latest Papers分区）
- **测试**：0.5天（完整流程+来源覆盖度验证+推送率验证）
- **调优**：0.5天（阈值微调+卡片文案优化）

---

## 附录：关键数据对比

### GitHub高分 vs arXiv低分对比表

| 维度 | arXiv论文 (Live-SWE-agent) | GitHub项目 (camel-ai) |
|------|---------------------------|----------------------|
| **新颖性** | 9.0 (2025最新) | 8.0 (2025最新) |
| **MGX适配度** | 8.0 (P0 Coding) | 8.5 (P1 Collaboration) |
| **活跃度** | 3.0 (无GitHub) | 9.0 (14825 stars) |
| **可复现性** | 3.0 (仅论文) | 8.5 (代码+数据集) |
| **许可合规** | 0.0 (未知) | 10.0 (Apache 2.0) |
| **总分** | 4.7 ❌ | 8.72 ✅ |
| **结论** | "强烈推荐纳入MGX，但受限于低分未推送" | "推荐纳入MGX" |

**关键洞察**：即使arXiv论文在新颖性和MGX适配度上与GitHub项目相当，但因活跃度/可复现性/许可证三维度拖累，导致总分被压制，无法推送。

### 解决后的效果预期

**优化前**：
- 推送来源：GitHub (90%) + 其他 (10%)
- arXiv推送率：<20%（仅高分论文）
- 最新论文推送延迟：7-14天（等待评分提升）

**优化后**：
- 推送来源：arXiv (30%) + GitHub (40%) + HELM (15%) + HuggingFace (15%)
- arXiv推送率：≥80%（最近7天且MGX适配度≥6.0）
- 最新论文推送延迟：<24小时（时间加权或Latest Papers分区）
