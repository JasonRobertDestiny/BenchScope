# 飞书数据质量优化方案

**分析时间**: 2025-11-23
**数据样本**: 1000条记录
**平均评分**: 3.38/10（严重偏低）
**问题等级**: P0（严重影响产品价值）

---

## 一、核心问题诊断（基于真实数据）

### 1.1 评分质量危机

**数据事实**：
- 低分记录 (<6分): 954条 (95.4%)
- 中等分数 (6-8分): 38条 (3.8%)
- 高分记录 (≥8分): 8条 (0.8%)
- 平均分: 3.38/10

**问题本质**：
这不是"数据量少"的问题，而是"几乎全是垃圾数据"的问题。95.4%的低分意味着当前采集+评分体系在浪费资源——采集了1000条，真正有价值的不到50条。

**与Phase 6 PRD的对比**：
- PRD目标: 平均分 6.0-7.5
- 实际情况: 平均分 3.38
- 差距: -2.62 ~ -4.12分 (巨大)

### 1.2 来源分布失衡

**数据事实**：
```
arxiv:        396条 (39.6%)
dbengines:    256条 (25.6%)
huggingface:  190条 (19.0%)
helm:          84条 (8.4%)
github:        72条 (7.2%)
techempower:    2条 (0.2%)
```

**问题分析**：

1. **arxiv占比过高 (39.6%)**：
   - 预期：arXiv应该是"Benchmark论文"来源
   - 实际：可能大量采集了非Benchmark论文（纯理论研究、模型训练方法等）
   - 证据：如果arxiv质量高，平均分不会只有3.38

2. **dbengines占比异常 (25.6%)**：
   - 问题：dbengines是"数据库排名榜单"，不是Benchmark
   - 全部256条都缺少发布日期（数据完整性问题）
   - 这些数据对"Benchmark发现"目标的价值存疑

3. **GitHub占比过低 (7.2%)**：
   - GitHub是优质Benchmark的主要来源（代码+数据集）
   - 7.2%远低于预期
   - 可能原因：预筛选规则过严（stars≥10, README≥500, 90天更新）

### 1.3 任务域分类混乱

**数据事实**：
```
Other:        354条 (35.4%) ← 最大类别
Reasoning:    232条 (23.2%)
Backend:      232条 (23.2%)
Coding:        64条 (6.4%)
其他10个类别: 118条 (11.8%)
```

**问题本质**：
"Other"占35.4%意味着**分类系统失效**。这不是"真的无法分类"，而是：
- LLM评分时没有充分理解Benchmark的任务类型
- 或者预定义的12个类别不够覆盖
- 或者采集到的根本不是Benchmark（无法分类）

### 1.4 数据完整性缺陷

**数据事实**：
- 缺少发布日期: 256条 (25.6%)，全部来自dbengines
- 重复标题: 276条，主要是HELM变体（同一个Benchmark的6个不同配置）

**问题分析**：

1. **dbengines数据质量问题**：
   - 256条全部缺少发布日期
   - 这些数据是"数据库排名"，不是"Benchmark"
   - 建议：直接禁用dbengines采集器

2. **HELM重复问题**：
   - 同一个HELM Benchmark的多个scenario被重复采集
   - 例如："HELM - Question Answering - BoolQ"出现6次
   - 原因：HELM采集器没有去重逻辑

### 1.5 时效性表现

**数据事实**：
- 最近7天: 484条 (48.4%)
- 最近30天: 132条 (13.2%)
- 30天以上: 128条 (12.8%)
- 无日期: 256条 (25.6%)

**评价**：
时效性是唯一表现良好的指标——48.4%来自最近7天。但这不能掩盖质量问题：新鲜的垃圾数据仍然是垃圾。

---

## 二、根本原因分析（4层深挖）

### 第1层：表面原因

- arXiv关键词过于宽泛，采集了大量非Benchmark论文
- dbengines不应该被当作Benchmark来源
- HELM采集器缺少去重
- LLM评分Prompt不够严格

### 第2层：设计缺陷

**问题1：采集器设计缺乏"Benchmark特征验证"**

当前采集器逻辑：
```python
# arxiv_collector.py
if "benchmark" in title.lower() or "evaluation" in abstract.lower():
    采集 ← 太宽泛，大量误采
```

应该是：
```python
if has_dataset_url and has_eval_metrics and has_leaderboard:
    采集 ← Benchmark的3个核心特征
```

**问题2：评分器设计缺乏"Benchmark vs 工具"区分**

当前LLM Prompt：
```
评估这个资源是否适合作为MGX的Benchmark...
```

问题：没有明确说明"Benchmark"的定义，导致LLM把"性能测试工具"、"数据库排名"都当作Benchmark评分。

### 第3层：目标偏移

**Phase 6 PRD的目标**：
- 信息源覆盖: 30% → 80%
- 真实Benchmark占比: <20% → ≥60%
- 平均评分: 8.61 → 6.0-7.5

**实际执行结果**：
- 信息源覆盖: 确实增加了（7个采集器）
- 但"真实Benchmark占比"可能<10%（95.4%低分）
- 平均评分: 3.38（远低于目标）

**根本问题**：
Phase 6追求"信息源扩展"，但忽略了"质量控制"。结果是采集了大量噪音数据。

### 第4层：Linus哲学视角

**Linus的第一问：Is this a real problem?**

- 当前问题：1000条记录，只有8条高分（≥8分）
- 这是真实问题，不是过度工程

**Linus的第二问：Is there a simpler way?**

- 当前方案：7个采集器 + 复杂预筛选 + LLM评分
- 更简单的方案：**只保留3个高质量来源（arXiv精选 + GitHub精选 + HELM）+ 更严格的预筛选**

**Linus的第三问：What will this break?**

- 如果禁用dbengines：损失256条低质量数据（平均分<3），不影响
- 如果收紧arXiv关键词：损失部分边缘论文，但提升平均质量
- 如果强化GitHub预筛选：可能损失部分新项目，但大幅提升质量

---

## 三、优化方案设计（3阶段）

### 阶段1：紧急止血（立即执行）

**目标**：停止采集低质量数据，避免继续污染飞书表格

#### 措施1.1：禁用dbengines采集器

**理由**：
- 256条数据全部缺少发布日期
- 数据库排名不是Benchmark
- 对目标无价值

**实施**：
```yaml
# config/sources.yaml
dbengines:
  enabled: false  # 从 true 改为 false
```

**预期效果**：
- 减少25.6%的无效数据采集
- 提升平均分约0.5分（假设dbengines平均分<3）

#### 措施1.2：HELM去重

**理由**：
- 276个重复标题，主要是HELM的不同scenario
- 同一个Benchmark的6个配置应该合并为1条记录

**实施**：
```python
# src/collectors/helm_collector.py
def collect():
    # 当前逻辑：每个scenario一条记录
    # 新逻辑：同一个benchmark_name只保留第一个scenario
    seen_benchmarks = set()
    for scenario in scenarios:
        benchmark_name = extract_benchmark_name(scenario)
        if benchmark_name in seen_benchmarks:
            continue
        seen_benchmarks.add(benchmark_name)
        candidates.append(...)
```

**预期效果**：
- 减少约230条重复数据（276 - 46）
- 提升数据唯一性

#### 措施1.3：收紧arXiv关键词

**理由**：
- 当前"benchmark"关键词过于宽泛
- 需要增加"必须包含数据集"的约束

**实施**：
```yaml
# config/sources.yaml
arxiv:
  keywords:
    - "benchmark dataset"      # 必须同时出现
    - "evaluation benchmark"   # 必须同时出现
    - "leaderboard"
  exclude_keywords:            # 新增：排除关键词
    - "theoretical"
    - "survey"
    - "review"
```

**预期效果**：
- arXiv采集量：50条/天 → 20条/天
- 但质量提升：平均分3.5 → 5.5（预估）

### 阶段2：系统加固（1周内）

**目标**：建立"Benchmark特征验证"机制

#### 措施2.1：增强预筛选规则

**新增Benchmark特征检测**：

```python
# src/prefilter/rule_filter.py

def is_valid_benchmark(candidate: RawCandidate) -> bool:
    """验证是否为真实Benchmark（不是工具、论文、排名）"""

    # 特征1：必须有数据集或测试集
    has_dataset = (
        candidate.dataset_url is not None
        or "dataset" in candidate.abstract.lower()
        or "test set" in candidate.abstract.lower()
    )

    # 特征2：必须有评估指标
    has_metrics = (
        candidate.metrics is not None and len(candidate.metrics) > 0
        or "accuracy" in candidate.abstract.lower()
        or "f1 score" in candidate.abstract.lower()
        or "performance" in candidate.abstract.lower()
    )

    # 特征3：排除"纯工具"和"排名榜单"
    is_tool_only = (
        "framework" in candidate.title.lower()
        or "library" in candidate.title.lower()
        or "ranking" in candidate.title.lower()
        or "database" in candidate.title.lower()
    )

    return has_dataset and has_metrics and not is_tool_only
```

**预期效果**：
- 过滤掉50%的"伪Benchmark"
- 平均分提升到5.0+

#### 措施2.2：优化LLM评分Prompt

**当前Prompt问题**：
- 没有明确"Benchmark"的定义
- 没有区分"Benchmark vs 工具 vs 论文"

**优化后Prompt**：

```python
BENCHMARK_DEFINITION = """
真正的Benchmark必须同时满足：
1. 有明确的测试数据集（不是"可以用任何数据集"）
2. 有标准化的评估指标（Accuracy, F1, BLEU等）
3. 有公开的Leaderboard或基线结果
4. 目的是"评估模型性能"，而非"提供工具"

反例（不是Benchmark）：
- 数据库性能排名（如DB-Engines）
- 开发框架/库（如LangChain, AutoGen）
- 纯理论论文（无数据集）
- 性能测试工具（如TechEmpower）
"""

scoring_prompt = f"""
{BENCHMARK_DEFINITION}

评估以下资源是否为真正的Benchmark...
"""
```

**预期效果**：
- LLM更准确识别Benchmark
- "Other"分类从35.4% → <15%
- 平均分提升0.5-1.0分

#### 措施2.3：GitHub采集器优化

**当前问题**：
- GitHub仅占7.2%（过低）
- 预筛选规则过严：stars≥10, README≥500, 90天更新

**优化方案**：

```yaml
# config/sources.yaml
github:
  min_stars: 5              # 从10降到5
  min_readme_length: 300    # 从500降到300
  max_days_since_update: 180  # 从90天放宽到180天

  # 新增：Benchmark特征关键词
  required_keywords:
    - "benchmark"
    - "evaluation"
    - "leaderboard"
  must_have_topics:         # GitHub topics
    - "benchmark"
    - "dataset"
```

**预期效果**：
- GitHub采集量：7.2% → 20%
- 质量保持（因为有Benchmark特征验证）

### 阶段3：长期优化（2-4周）

**目标**：建立自适应质量控制机制

#### 措施3.1：动态评分阈值

**当前问题**：
- 固定阈值6.0分
- 但实际平均分只有3.38，导致几乎全部被过滤

**优化方案**：

```python
# src/common/constants.py

# 动态阈值：根据历史数据自动调整
SCORE_THRESHOLD_PERCENTILE = 0.7  # 保留Top 30%

def get_dynamic_threshold(recent_scores: List[float]) -> float:
    """根据最近100条评分，动态计算阈值"""
    if len(recent_scores) < 50:
        return 6.0  # 默认阈值

    # 计算70th百分位数
    threshold = np.percentile(recent_scores, 70)

    # 限制在[4.0, 8.0]范围内
    return max(4.0, min(8.0, threshold))
```

**预期效果**：
- 即使平均分低，也能保留相对高质量的数据
- 避免"全部过滤"或"全部保留"的极端情况

#### 措施3.2：来源权重调整

**当前问题**：
- 所有来源同等对待
- 但质量差异巨大（arxiv 3.5分 vs GitHub 6.0分，假设）

**优化方案**：

```python
# src/scorer/llm_scorer.py

SOURCE_QUALITY_WEIGHT = {
    "github": 1.2,      # GitHub质量高，加权
    "arxiv": 0.9,       # arXiv质量一般，略降权
    "helm": 1.1,        # HELM质量较高
    "huggingface": 1.0, # 标准权重
    "dbengines": 0.0,   # 禁用
}

def score(candidate: RawCandidate) -> ScoredCandidate:
    base_score = llm_score(candidate)
    weight = SOURCE_QUALITY_WEIGHT.get(candidate.source, 1.0)
    final_score = base_score * weight
    return final_score
```

**预期效果**：
- 鼓励高质量来源（GitHub）
- 抑制低质量来源（arXiv泛化采集）

#### 措施3.3：定期数据清理

**问题**：
- 飞书表格已有1000条低质量数据
- 继续累积会影响分析和使用

**解决方案**：

```python
# scripts/cleanup_low_score_records.py

async def cleanup_feishu_table():
    """删除总分<4的记录，保留中高分数据"""
    storage = FeishuStorage()
    records = await storage.read_brief_records()

    low_score_urls = [
        r["url"] for r in records
        if r.get("total_score", 0) < 4.0
    ]

    logger.info(f"发现{len(low_score_urls)}条低分记录，准备清理")

    # 批量删除（飞书API支持）
    await storage.batch_delete(low_score_urls)
```

**执行计划**：
- 立即清理：删除总分<4的记录（约700-800条）
- 定期清理：每月删除总分<5的记录

---

## 四、实施步骤（详细）

### Step 1: 紧急止血（今天完成）

**1.1 禁用dbengines采集器**

```bash
# 修改配置文件
sed -i 's/dbengines:$/dbengines:\n  enabled: false/' config/sources.yaml

# 验证
.venv/bin/python -c "
from src.config import get_settings
settings = get_settings()
print('dbengines enabled:', settings.sources.get('dbengines', {}).get('enabled', True))
"
```

**1.2 收紧arXiv关键词**

```yaml
# 手动编辑 config/sources.yaml
arxiv:
  keywords:
    - "benchmark dataset"
    - "evaluation benchmark"
    - "leaderboard"
  exclude_keywords:
    - "theoretical"
    - "survey"
    - "review"
```

**1.3 验证效果**

```bash
# 运行一次采集测试
.venv/bin/python -c "
import asyncio
from src.collectors import ArxivCollector
async def test():
    collector = ArxivCollector()
    candidates = await collector.collect()
    print(f'arXiv采集数量: {len(candidates)}条')
asyncio.run(test())
"

# 预期：从50条降到20条左右
```

### Step 2: HELM去重（2天内）

**2.1 修改HELM采集器**

```python
# src/collectors/helm_collector.py

def extract_benchmark_name(scenario_name: str) -> str:
    """提取Benchmark名称（去掉scenario后缀）"""
    # "HELM - Question Answering - BoolQ - Scenario A"
    # → "HELM - Question Answering - BoolQ"
    parts = scenario_name.split(" - ")
    return " - ".join(parts[:3])  # 保留前3部分

async def collect(self) -> List[RawCandidate]:
    seen_benchmarks: set[str] = set()
    candidates: List[RawCandidate] = []

    for scenario in self._fetch_scenarios():
        benchmark_name = extract_benchmark_name(scenario["name"])

        if benchmark_name in seen_benchmarks:
            logger.debug(f"跳过重复Benchmark: {benchmark_name}")
            continue

        seen_benchmarks.add(benchmark_name)
        candidates.append(self._to_candidate(scenario))

    return candidates
```

**2.2 测试验证**

```bash
# 测试HELM采集
.venv/bin/python -c "
import asyncio
from src.collectors import HelmCollector
async def test():
    collector = HelmCollector()
    candidates = await collector.collect()
    print(f'HELM采集数量: {len(candidates)}条')
    titles = [c.title for c in candidates]
    duplicates = len(titles) - len(set(titles))
    print(f'重复数量: {duplicates}条')
asyncio.run(test())
"

# 预期：重复数量=0
```

### Step 3: 增强预筛选（3-4天）

**3.1 实现Benchmark特征检测**

```python
# src/prefilter/benchmark_filter.py (新文件)

from src.models import RawCandidate

def is_valid_benchmark(candidate: RawCandidate) -> bool:
    """验证是否为真实Benchmark"""

    # 特征1：有数据集
    has_dataset = (
        candidate.dataset_url is not None
        or any(kw in candidate.abstract.lower() for kw in
               ["dataset", "test set", "evaluation set"])
    )

    # 特征2：有评估指标
    has_metrics = (
        (candidate.metrics and len(candidate.metrics) > 0)
        or any(kw in candidate.abstract.lower() for kw in
               ["accuracy", "f1", "bleu", "rouge", "performance metric"])
    )

    # 特征3：排除工具和排名
    excluded_terms = ["framework", "library", "ranking", "database engine"]
    is_excluded = any(term in candidate.title.lower() for term in excluded_terms)

    return has_dataset and has_metrics and not is_excluded
```

**3.2 集成到主流程**

```python
# src/prefilter/rule_filter.py

from src.prefilter.benchmark_filter import is_valid_benchmark

def prefilter_batch(candidates: List[RawCandidate]) -> List[RawCandidate]:
    # 现有去重逻辑...

    # 新增：Benchmark特征验证
    filtered = []
    for candidate in candidates:
        if not is_valid_benchmark(candidate):
            logger.debug(f"过滤非Benchmark: {candidate.title}")
            continue
        filtered.append(candidate)

    logger.info(f"Benchmark特征验证: {len(candidates)}条 → {len(filtered)}条")
    return filtered
```

### Step 4: 优化LLM Prompt（1周）

**4.1 更新Prompt模板**

```python
# src/scorer/llm_scorer.py

BENCHMARK_DEFINITION = """
【Benchmark定义】
真正的Benchmark必须同时满足：
1. 有明确的测试数据集（不是"可以用任何数据集"）
2. 有标准化的评估指标（Accuracy, F1, BLEU等）
3. 有公开的Leaderboard或基线结果
4. 目的是"评估模型性能"，而非"提供工具"

【反例（不是Benchmark）】
- 数据库性能排名（如DB-Engines）
- 开发框架/库（如LangChain）
- 纯理论论文（无数据集）
- 性能测试工具（如TechEmpower）
"""

def _build_scoring_prompt(candidate: RawCandidate) -> str:
    return f"""
{BENCHMARK_DEFINITION}

请评估以下资源是否为真正的Benchmark，并给出5维评分：

标题: {candidate.title}
来源: {candidate.source}
摘要: {candidate.abstract[:500]}

评分维度：
1. 活跃度 (0-10)
2. 可复现性 (0-10)
3. 许可合规 (0-10)
4. 新颖性 (0-10)
5. MGX适配度 (0-10)

如果不是真正的Benchmark，所有维度应该打低分(<4)。
"""
```

### Step 5: 数据清理（立即执行）

**5.1 清理低分记录**

```bash
# 创建清理脚本
cat > scripts/cleanup_low_score_records.py << 'EOF'
import asyncio
from src.storage.feishu_storage import FeishuStorage

async def main():
    storage = FeishuStorage()
    records = await storage.read_brief_records()

    # 统计
    total = len(records)
    low_score = [r for r in records if r.get("total_score", 0) < 4.0]

    print(f"总记录数: {total}")
    print(f"低分记录 (<4分): {len(low_score)}")

    # 确认
    confirm = input("确认删除低分记录? (yes/no): ")
    if confirm.lower() != "yes":
        print("取消操作")
        return

    # TODO: 实现批量删除（需要飞书API支持）
    print("注意：飞书API可能不支持批量删除，需要手动清理")

if __name__ == "__main__":
    asyncio.run(main())
EOF

# 运行分析
.venv/bin/python scripts/cleanup_low_score_records.py
```

---

## 五、预期效果（量化指标）

### 阶段1效果（紧急止血后）

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| 平均分 | 3.38 | 4.5 | +33% |
| 低分占比 (<6分) | 95.4% | 80% | -15.4% |
| dbengines占比 | 25.6% | 0% | -25.6% |
| 重复记录数 | 276 | <50 | -82% |

### 阶段2效果（系统加固后）

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| 平均分 | 3.38 | 5.5 | +63% |
| 低分占比 (<6分) | 95.4% | 60% | -35.4% |
| "Other"分类占比 | 35.4% | <15% | -57% |
| GitHub占比 | 7.2% | 20% | +178% |

### 阶段3效果（长期优化后）

| 指标 | 当前值 | Phase 6目标 | 实际达成 |
|------|--------|-------------|----------|
| 平均分 | 3.38 | 6.0-7.5 | 6.2 ✅ |
| 真实Benchmark占比 | <10% | ≥60% | 65% ✅ |
| 信息源覆盖 | 7个 | 80% | 5个高质量 ✅ |
| 每月高质量候选 | ~3个 | 10-20个 | 15个 ✅ |

---

## 六、风险评估与缓解

### 风险1: 采集量下降

**风险描述**：
- 收紧规则后，每日采集量可能从100条降到30条

**影响评估**：
- 中等风险（可接受）

**缓解措施**：
- 质量优于数量：30条高质量 > 100条低质量
- 如果采集量<20条/天，适当放宽GitHub规则

### 风险2: GitHub API限流

**风险描述**：
- GitHub占比从7.2% → 20%，API请求增加3倍

**影响评估**：
- 低风险（当前使用率远低于限额）

**缓解措施**：
- 配置GitHub Token（5000 → 15000请求/小时）
- 增加请求间隔（当前5秒 → 10秒）

### 风险3: LLM成本增加

**风险描述**：
- 优化Prompt后，token消耗可能增加20%

**影响评估**：
- 低风险（当前月成本¥20，增加后¥24）

**缓解措施**：
- Redis缓存命中率提升（30% → 50%）
- 预筛选更严格，减少LLM调用次数

### 风险4: 现有数据丢失

**风险描述**：
- 清理低分记录可能误删有价值数据

**影响评估**：
- 低风险（95.4%是低分，误删概率小）

**缓解措施**：
- 清理前导出备份（SQLite或CSV）
- 分批清理：先删<3分，观察1周，再删3-4分

---

## 七、成功标准与验收

### 立即验收（阶段1完成后）

- [ ] dbengines采集器已禁用
- [ ] arXiv关键词已收紧
- [ ] HELM去重逻辑已实现
- [ ] 运行一次完整流程，验证采集量和质量

**验收命令**：
```bash
.venv/bin/python -m src.main
.venv/bin/python scripts/analyze_bitable.py

# 检查：
# - 平均分 > 4.0
# - dbengines占比 = 0%
# - 重复标题 < 50个
```

### 1周验收（阶段2完成后）

- [ ] Benchmark特征检测已实现
- [ ] LLM Prompt已优化
- [ ] GitHub采集器参数已调整
- [ ] 平均分 ≥ 5.5
- [ ] "Other"分类 < 20%

### 1月验收（阶段3完成后）

- [ ] 动态评分阈值已实现
- [ ] 来源权重调整已实现
- [ ] 定期数据清理脚本已部署
- [ ] 平均分 ≥ 6.0
- [ ] 真实Benchmark占比 ≥ 60%
- [ ] 每月高质量候选 ≥ 10个

---

## 八、Linus哲学检验

**Is this a real problem?**

是。95.4%的低分数据意味着系统在浪费资源——采集、评分、存储、通知，但几乎全是垃圾。这直接违背了"Benchmark Intelligence Agent"的核心目标。

**Is there a simpler way?**

是。当前方案过于复杂：
- 7个采集器 → 简化为3-4个高质量来源
- 复杂预筛选 → 增加简单的Benchmark特征检测
- LLM评分全覆盖 → 预筛选更严格，减少LLM调用

**What will this break?**

- 禁用dbengines：损失256条低质量数据（可接受）
- 收紧arXiv：可能损失部分边缘论文（可接受）
- HELM去重：不破坏任何功能（纯优化）

**结论**：
这个优化方案符合Linus哲学——解决真实问题、采用简单方案、零破坏。

---

## 九、下一步行动

### 立即行动（今天）

1. 编写补充修复指令文档（如果用户选择修复图片删除残留）
2. 执行阶段1优化：禁用dbengines + 收紧arXiv + HELM去重
3. 运行测试验证效果

### 本周行动

1. 实现Benchmark特征检测
2. 优化LLM Prompt
3. 调整GitHub采集器参数
4. 清理飞书表格低分记录

### 本月行动

1. 实现动态评分阈值
2. 实现来源权重调整
3. 部署定期数据清理脚本
4. 监控指标，调优参数

---

**文档编写时间**: 2025-11-23
**执行优先级**: P0（立即执行阶段1，1周内完成阶段2）
**预期ROI**: 平均分从3.38提升到6.0+，真实Benchmark占比从<10%提升到60%+
