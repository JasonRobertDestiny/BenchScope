# Codex Phase 3 开发指令：优化与功能增强

**执行时间**: 2025-11-13
**前置条件**: Phase 1-2 MVP已完成,核心功能运行正常

---

## 背景与目标

### Phase 1-2 已完成功能 ✅
- 数据采集: arXiv(7天) + GitHub(30天) + HuggingFace(14天)
- URL去重: 查询飞书Bitable,过滤已推送候选
- LLM评分: GPT-4o评分,月成本<$1
- 飞书存储: 主存储+SQLite降级备份
- 飞书通知: Webhook推送,完整reasoning显示

### Phase 3 优化目标 🎯
1. **提升GitHub候选质量**: 当前100%被预筛选过滤
2. **移除失效采集器**: Papers with Code API已永久重定向
3. **实现时间过滤**: GitHub/HuggingFace采集器使用时间窗口常量
4. **优化评分权重**: 提升MGX适配度权重
5. **增加运维工具**: 日志分析、表格管理

---

## Task 1: 优化GitHub预筛选规则

### 问题诊断

**当前问题**:
```python
# src/common/constants.py
PREFILTER_MIN_GITHUB_STARS: Final[int] = 50  # 过高,导致100%过滤

# 实际情况:
# - GitHub采集器已按stars排序,只取Top 5
# - 再用50 stars过滤导致大量有价值repo被过滤
```

**解决方案**:
1. 降低stars阈值: `50 → 10`
2. 增加README长度检查: `>500字符`
3. 增加最近更新检查: `90天内有commit`

### 代码修改

**文件1**: `src/common/constants.py`

```python
# 在 "# ---- Prefilter 配置 ----" 部分修改:

PREFILTER_MIN_GITHUB_STARS: Final[int] = 10  # 降低到10 stars
PREFILTER_MIN_README_LENGTH: Final[int] = 500  # README最少500字符
PREFILTER_RECENT_DAYS: Final[int] = 90  # 90天内有更新
```

**文件2**: `src/prefilter/rule_filter.py`

在`_is_quality_github_repo`方法中增加多维度检查:

```python
def _is_quality_github_repo(self, candidate: RawCandidate) -> bool:
    """GitHub仓库质量检查（多维度）"""

    # 1. Stars检查（降低阈值到10）
    stars = candidate.github_stars or 0
    if stars < constants.PREFILTER_MIN_GITHUB_STARS:
        logger.debug(f"GitHub stars不足: {candidate.title} ({stars} < {constants.PREFILTER_MIN_GITHUB_STARS})")
        return False

    # 2. 最近更新检查（90天内）
    if candidate.publish_date:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        days_since_update = (now - candidate.publish_date).days

        if days_since_update > constants.PREFILTER_RECENT_DAYS:
            logger.debug(f"GitHub更新时间过久: {candidate.title} ({days_since_update}天前)")
            return False

    # 3. README长度检查（避免空repo）
    abstract_length = len(candidate.abstract or "")
    if abstract_length < constants.PREFILTER_MIN_README_LENGTH:
        logger.debug(f"GitHub README过短: {candidate.title} ({abstract_length}字符)")
        return False

    return True
```

### 验收标准

```bash
# 运行pipeline
python src/main.py 2>&1 | grep -A5 "预筛选完成"

# 预期输出:
# 预筛选完成: 保留X条 (过滤率Y%)
# 其中 Y 应该在 70-90% 范围（当前100%）
# X 应该有 1-5 条GitHub候选通过
```

---

## Task 2: 实现GitHub/HuggingFace时间过滤

### 问题诊断

**当前状态**:
- `constants.py`已定义时间窗口: `GITHUB_LOOKBACK_DAYS=30`, `HUGGINGFACE_LOOKBACK_DAYS=14`
- **采集器未使用**,采集所有历史数据

### 代码修改

**文件1**: `src/collectors/github_collector.py`

在`_fetch_topic`方法的搜索query中增加时间过滤:

```python
from datetime import datetime, timedelta, timezone

async def _fetch_topic(self, client: httpx.AsyncClient, topic: str) -> List[RawCandidate]:
    """调用GitHub搜索API（增加时间过滤）"""

    # 计算时间窗口
    lookback_date = datetime.now(timezone.utc) - timedelta(days=constants.GITHUB_LOOKBACK_DAYS)
    date_filter = lookback_date.strftime("%Y-%m-%d")  # 格式: 2025-10-14

    params = {
        "q": f"{topic} benchmark in:name,description,readme pushed:>{date_filter}",  # 增加时间过滤
        "sort": "stars",
        "order": "desc",
        "per_page": self.per_page,
    }

    # ... 其余逻辑不变
```

**文件2**: `src/collectors/huggingface_collector.py`

在`collect`方法中增加后处理过滤:

```python
from datetime import datetime, timedelta, timezone

async def collect(self) -> List[RawCandidate]:
    """采集HuggingFace数据集（增加时间过滤）"""

    # ... 原有采集逻辑 ...

    # 时间窗口过滤
    lookback_date = datetime.now(timezone.utc) - timedelta(days=constants.HUGGINGFACE_LOOKBACK_DAYS)

    filtered_candidates = []
    for candidate in all_candidates:
        if candidate.publish_date and candidate.publish_date >= lookback_date:
            filtered_candidates.append(candidate)

    logger.info("HuggingFace采集完成,候选数%d (时间过滤后)", len(filtered_candidates))
    return filtered_candidates
```

### 验收标准

```bash
# 运行pipeline,检查采集日志
python src/main.py 2>&1 | grep -E "(GitHub|HuggingFace)采集完成"

# 预期: 采集数量应该比之前少（只采30天/14天内的）
```

---

## Task 3: 移除Papers with Code采集器

### 问题诊断

Papers with Code API已永久301重定向到HuggingFace:
```
https://paperswithcode.com/api/v1/tasks/ → https://huggingface.co/papers/trending
```

### 代码修改

**Step 1**: 删除文件
```bash
rm src/collectors/pwc_collector.py
```

**Step 2**: 更新`src/collectors/__init__.py`
```python
from src.collectors.arxiv_collector import ArxivCollector
from src.collectors.github_collector import GitHubCollector
from src.collectors.huggingface_collector import HuggingFaceCollector
# 移除: from src.collectors.pwc_collector import PwCCollector

__all__ = [
    "ArxivCollector",
    "GitHubCollector",
    "HuggingFaceCollector",
    # 移除: "PwCCollector",
]
```

**Step 3**: 更新`src/main.py`
```python
from src.collectors import ArxivCollector, GitHubCollector, HuggingFaceCollector
# 移除: PwCCollector

collectors = [
    ArxivCollector(),
    GitHubCollector(),
    # 移除: PwCCollector(),
    HuggingFaceCollector(settings=settings),
]
```

**Step 4**: 清理`src/common/constants.py`

删除以下行:
```python
PWC_API_BASE: Final[str] = "https://paperswithcode.com/api/v1"
PWC_TIMEOUT_SECONDS: Final[int] = 15
PWC_QUERY_KEYWORDS: Final[list[str]] = ["coding", "agent", "reasoning"]
PWC_MIN_TASK_PAPERS: Final[int] = 3
PWC_PAGE_SIZE: Final[int] = 20
```

### 验收标准

```bash
# 运行pipeline,不应该看到PwC错误日志
python src/main.py 2>&1 | grep -i pwc

# 预期: 无输出（或只有删除前的历史日志）
```

---

## Task 4: 调整评分权重（可选）

### 当前权重分析

**问题**:
- 活跃度25%权重过高（GitHub stars波动大）
- MGX适配度10%权重过低（核心业务相关性）

**建议调整**:
```
活跃度:     25% → 20%
可复现性:   30% → 30%（保持）
许可合规:   20% → 15%
任务新颖性: 15% → 15%（保持）
MGX适配度:  10% → 20%（提高）
```

### 代码修改

**文件**: `src/scorer/llm_scorer.py`

在`_build_prompt`方法中更新权重说明:

```python
请基于以下维度评分(0-10分):

1. 活跃度(20%): GitHub stars/近期commits/社区参与度
2. 可复现性(30%): 代码/数据集开源状态,复现文档完整性
3. 许可合规(15%): MIT/Apache/BSD等商业友好许可
4. 任务新颖性(15%): 与已有Benchmark的差异度,创新性
5. MGX适配度(20%): 与MetaGPT多agent/代码生成/工具使用的相关性

请输出JSON,示例:
{{
  "activity_score": 8.0,
  "reproducibility_score": 9.0,
  "license_score": 10.0,
  "novelty_score": 7.0,
  "relevance_score": 8.5,
  "reasoning": "【活跃度】GitHub stars较高/近期有更新；【可复现性】代码/数据开源情况；【许可合规】MIT/Apache/BSD等；【新颖性】相比已有任务的独特性；【MGX适配度】与多agent/代码生成的相关性"
}}
```

**注意**: 权重调整会影响总分计算,需要清空Redis缓存重新评分。

### 验收标准

```bash
# 清空Redis缓存
redis-cli FLUSHALL

# 运行pipeline
python src/main.py

# 观察平均分是否有变化（MGX相关候选分数应该提升）
```

---

## Task 5: 增加日志分析工具

### 需求

创建`scripts/analyze_logs.py`,分析每日采集效果。

### 代码实现

```python
"""日志分析工具

用法: python scripts/analyze_logs.py logs/benchscope.log
"""
import re
import sys
from collections import Counter
from pathlib import Path


def parse_log_file(log_path: Path) -> dict:
    """解析日志文件"""
    stats = {
        "采集统计": {},
        "去重统计": {},
        "预筛选统计": {},
        "评分统计": {},
        "优先级统计": {},
    }

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            # 采集统计
            if match := re.search(r"✓ (\w+Collector): (\d+)条", line):
                collector, count = match.groups()
                stats["采集统计"][collector] = int(count)

            # 去重统计
            if match := re.search(r"去重完成: 过滤(\d+)条重复,保留(\d+)条新发现", line):
                duplicate, new = match.groups()
                stats["去重统计"] = {"重复": int(duplicate), "新发现": int(new)}

            # 预筛选统计
            if match := re.search(r"预筛选完成: 保留(\d+)条 \(过滤率([\d.]+)%\)", line):
                output, filter_rate = match.groups()
                stats["预筛选统计"] = {"输出": int(output), "过滤率": float(filter_rate)}

            # 评分统计
            if match := re.search(r"平均分: ([\d.]+)/10", line):
                stats["评分统计"]["平均分"] = float(match.group(1))

            # 优先级统计
            if match := re.search(r"(高|中|低)优先级: (\d+)条", line):
                priority, count = match.groups()
                stats["优先级统计"][priority] = int(count)

    return stats


def generate_report(stats: dict) -> str:
    """生成报告"""
    lines = [
        "=" * 60,
        "BenchScope 日志分析报告",
        "=" * 60,
        "",
        "## 数据采集",
    ]

    for collector, count in stats["采集统计"].items():
        lines.append(f"  {collector}: {count}条")

    if stats["去重统计"]:
        lines.extend([
            "",
            "## 去重",
            f"  重复过滤: {stats['去重统计']['重复']}条",
            f"  新发现: {stats['去重统计']['新发现']}条",
        ])

    if stats["预筛选统计"]:
        lines.extend([
            "",
            "## 预筛选",
            f"  输出: {stats['预筛选统计']['输出']}条",
            f"  过滤率: {stats['预筛选统计']['过滤率']:.1f}%",
        ])

    if stats["评分统计"]:
        lines.extend([
            "",
            "## 评分",
            f"  平均分: {stats['评分统计'].get('平均分', 0):.2f}/10",
        ])

    if stats["优先级统计"]:
        lines.extend([
            "",
            "## 优先级",
        ])
        for priority, count in stats["优先级统计"].items():
            lines.append(f"  {priority}: {count}条")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/analyze_logs.py <日志文件>")
        sys.exit(1)

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"错误: 日志文件不存在 - {log_path}")
        sys.exit(1)

    stats = parse_log_file(log_path)
    report = generate_report(stats)
    print(report)


if __name__ == "__main__":
    main()
```

### 验收标准

```bash
# 运行分析
python scripts/analyze_logs.py logs/benchscope.log

# 预期: 输出格式化的统计报告
```

---

## 测试流程

### 完整测试流程

```bash
# 1. 激活环境
source .venv/bin/activate
export PYTHONPATH=.

# 2. 清空Redis缓存（如果修改了评分权重）
redis-cli FLUSHALL

# 3. 运行pipeline
python src/main.py 2>&1 | tee logs/test_$(date +%Y%m%d_%H%M%S).log

# 4. 分析日志
python scripts/analyze_logs.py logs/test_*.log

# 5. 检查GitHub候选通过率
grep "GitHub" logs/test_*.log | grep -E "(采集|预筛选)"
```

### 预期结果

- GitHub采集数量: 5-15条（30天窗口）
- GitHub预筛选通过: 1-5条（10-30%通过率）
- 无PwC错误日志
- 日志分析工具正常输出

---

## 提交规范

**Commit格式**:
```
<type>(scope): <description>

<body>
```

**类型**:
- `feat`: 新功能
- `fix`: Bug修复
- `refactor`: 重构
- `perf`: 性能优化

**示例**:
```bash
git commit -m "feat(prefilter): 优化GitHub预筛选规则

- 降低stars阈值到10
- 增加README长度检查(500字符)
- 增加最近更新检查(90天)
- GitHub候选通过率提升到10-30%
"
```

---

## 完成检查清单

### Task完成标准

- [ ] Task 1: GitHub预筛选规则优化完成,通过率10-30%
- [ ] Task 2: GitHub/HuggingFace时间过滤实现
- [ ] Task 3: PwC采集器完全移除,无错误日志
- [ ] Task 4: 评分权重调整完成（可选）
- [ ] Task 5: 日志分析工具创建并可用

### 代码质量

- [ ] 所有修改符合PEP8规范
- [ ] 关键逻辑有中文注释
- [ ] 无硬编码魔法数字
- [ ] 异常处理完善

### 测试验证

- [ ] 本地pipeline运行成功
- [ ] 去重功能正常工作
- [ ] GitHub预筛选通过率符合预期
- [ ] 日志分析工具输出正确

### 文档与提交

- [ ] 代码提交message符合规范
- [ ] 重要修改有commit说明
- [ ] 通知Claude Code验收

---

## 开始执行

**Codex,请按以下顺序执行Phase 3任务**:

1. **Task 3优先**: 移除PwC采集器（最简单,立即见效）
2. **Task 1核心**: 优化GitHub预筛选规则（解决100%过滤问题）
3. **Task 2重要**: 实现时间过滤（优化采集效率）
4. **Task 5工具**: 创建日志分析工具（运维支持）
5. **Task 4可选**: 调整评分权重（根据实际效果决定是否执行）

每完成一个Task,提交代码并运行测试验证,确保功能正常后再进行下一个Task。

**祝开发顺利！** 🚀
