# Codex紧急修复指令

## 问题严重程度: P0 (阻塞Phase 2验收)

当前Phase 2实现与设计文档严重偏离，必须立即修复以下问题：

---

## 问题1: 评分模型错误 (P0)

**错误现状**:
- `src/scorer/llm_scorer.py` 返回 `BenchmarkScore` (Phase 1模型)
- `src/models.py` 中 `ScoredCandidate` 使用 `raw: RawCandidate` + `score: BenchmarkScore` 嵌套结构

**强制要求**:
必须完全按照 `CODEX-PHASE2-DETAILED.md` 第365-611行的实现代码重写：

### Step 1: 更新 `src/models.py`

删除现有的`ScoredCandidate`定义(第62-68行)，替换为：

```python
@dataclass(slots=True)
class ScoredCandidate:
    """Phase 2评分后的候选项 (5维度评分模型)"""

    # RawCandidate基本字段
    title: str
    url: str
    source: SourceType
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    publish_date: Optional[datetime] = None
    github_stars: Optional[int] = None
    github_url: Optional[str] = None
    dataset_url: Optional[str] = None
    raw_metadata: Dict[str, str] = field(default_factory=dict)

    # Phase 2评分字段 (0-10分制)
    activity_score: float = 0.0  # 活跃度 (25%权重)
    reproducibility_score: float = 0.0  # 可复现性 (30%权重)
    license_score: float = 0.0  # 许可合规 (20%权重)
    novelty_score: float = 0.0  # 任务新颖性 (15%权重)
    relevance_score: float = 0.0  # MGX适配度 (10%权重)
    reasoning: str = ""  # LLM评分依据

    @property
    def total_score(self) -> float:
        """加权总分 (0-10)"""
        return (
            self.activity_score * 0.25
            + self.reproducibility_score * 0.30
            + self.license_score * 0.20
            + self.novelty_score * 0.15
            + self.relevance_score * 0.10
        )

    @property
    def priority(self) -> str:
        """自动分级: high(>=8.0), medium(6.0-7.9), low(<6.0)"""
        total = self.total_score
        if total >= 8.0:
            return "high"
        if total >= 6.0:
            return "medium"
        return "low"
```

### Step 2: 完全重写 `src/scorer/llm_scorer.py`

直接复制 `CODEX-PHASE2-DETAILED.md` 第372-611行的完整代码，覆盖现有文件。

**关键修改点**:
1. 导入改为 `from src.models import RawCandidate, ScoredCandidate`
2. `score()` 方法返回 `ScoredCandidate`
3. Prompt必须要求LLM返回Phase 2的5个字段
4. `_fallback_score()` 返回Phase 2格式的字典

**验证命令**:
```bash
python << 'EOF'
from src.models import ScoredCandidate
print(ScoredCandidate.__annotations__)
# 必须包含: activity_score, reproducibility_score, license_score, novelty_score, relevance_score
EOF
```

---

## 问题2: 预筛选规则错误 (P0)

**错误现状**:
`src/prefilter/rule_filter.py` 使用自定义规则,完全不符合Phase 2规范

**强制要求**:
必须实现以下5条规则 (见 `CODEX-PHASE2-DETAILED.md` 第101-169行):

```python
"""规则预筛选引擎"""
from __future__ import annotations

import logging
from typing import List

from src.common import constants
from src.models import RawCandidate

logger = logging.getLogger(__name__)


def prefilter(candidate: RawCandidate) -> bool:
    """
    预筛选规则（过滤低质量候选）:
    1. 标题长度 >= 10字符
    2. 摘要非空 (>= 20字符)
    3. URL有效 (http/https开头)
    4. 来源在白名单 (arxiv/github/pwc/huggingface)
    5. 关键词匹配（至少1个benchmark相关词）

    返回: True=保留, False=过滤
    """
    # 规则1: 标题长度检查
    if not candidate.title or len(candidate.title.strip()) < 10:
        logger.debug(f"过滤: 标题过短 - {candidate.title}")
        return False

    # 规则2: 摘要检查
    if not candidate.abstract or len(candidate.abstract.strip()) < 20:
        logger.debug(f"过滤: 摘要过短 - {candidate.title}")
        return False

    # 规则3: URL检查
    if not candidate.url or not candidate.url.startswith(('http://', 'https://')):
        logger.debug(f"过滤: URL无效 - {candidate.url}")
        return False

    # 规则4: 来源白名单
    valid_sources = ['arxiv', 'github', 'pwc', 'huggingface']
    if candidate.source not in valid_sources:
        logger.debug(f"过滤: 来源不在白名单 - {candidate.source}")
        return False

    # 规则5: 关键词匹配
    text = f"{candidate.title} {candidate.abstract}".lower()
    matched_keywords = [kw for kw in constants.BENCHMARK_KEYWORDS if kw in text]

    if not matched_keywords:
        logger.debug(f"过滤: 无关键词匹配 - {candidate.title}")
        return False

    logger.debug(f"通过: {candidate.title[:50]}... (匹配关键词: {matched_keywords[:3]})")
    return True


def prefilter_batch(candidates: List[RawCandidate]) -> List[RawCandidate]:
    """批量预筛选候选"""
    if not candidates:
        return []

    filtered = [c for c in candidates if prefilter(c)]
    filter_rate = 100 * (1 - len(filtered) / len(candidates)) if candidates else 0

    logger.info(f"预筛选完成,输入{len(candidates)}条,输出{len(filtered)}条,过滤率{filter_rate:.1f}%")

    return filtered
```

**验证命令**:
```bash
# 使用真实数据测试
python << 'EOF'
import json
from src.models import RawCandidate
from src.prefilter.rule_filter import prefilter

with open('docs/samples/collected_data.json') as f:
    data = json.load(f)[0]

candidate = RawCandidate(
    title=data['title'],
    url=data['url'],
    source=data['source'],
    abstract=data['abstract'],
    authors=data['authors'],
    publish_date=None
)

result = prefilter(candidate)
print(f"预筛选结果: {'通过' if result else '被过滤'}")
assert result is True, "真实数据应该通过预筛选"
EOF
```

---

## 问题3: 缺少单元测试 (P0)

**强制要求**:
创建 `tests/unit/test_prefilter.py`,完全复制 `CODEX-PHASE2-DETAILED.md` 第206-325行代码。

**验收命令**:
```bash
pytest tests/unit/test_prefilter.py -v
# 必须7/7通过
```

---

## 修复顺序 (强制)

1. **Step 1** (5分钟): 修复 `src/models.py` 中的 `ScoredCandidate`
2. **Step 2** (10分钟): 完全重写 `src/scorer/llm_scorer.py`
3. **Step 3** (5分钟): 完全重写 `src/prefilter/rule_filter.py`
4. **Step 4** (5分钟): 创建 `tests/unit/test_prefilter.py`
5. **Step 5** (2分钟): 运行测试验证: `pytest tests/unit/test_prefilter.py -v`
6. **Step 6** (3分钟): 手动测试真实数据 (见上面验证命令)

**总时间预算**: 30分钟

---

## 验收标准 (必须全部通过)

- [ ] `src/models.py` 中 `ScoredCandidate` 有Phase 2的5个评分字段
- [ ] `src/scorer/llm_scorer.py` 返回 `ScoredCandidate` 类型
- [ ] `src/prefilter/rule_filter.py` 实现5条Phase 2规则
- [ ] `tests/unit/test_prefilter.py` 7个测试全部通过
- [ ] 真实数据 (`docs/samples/collected_data.json`) 通过预筛选

---

## Linus哲学提醒

这些错误违反了三大原则:

1. **"Is this a real problem?"** - Codex自作主张修改了设计,但设计文档明确规定了实现
2. **"Is there a simpler way?"** - 不应该创造新的评分模型,直接用Phase 2规范即可
3. **"What will this break?"** - 当前实现与后续Task 3-7完全不兼容

**立即按文档重写，不要自己发明**。
