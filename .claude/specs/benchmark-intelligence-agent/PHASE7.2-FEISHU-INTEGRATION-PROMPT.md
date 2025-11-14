# Phase 7.2 开发指令：飞书集成与测试补充

## 执行者：Codex

## 背景

Phase 7.1已完成三域评分模型的核心实现（AgentCapabilityScores/RiskDomainScores/OperationalScores），但飞书存储和通知模块尚未同步更新。**当前用户无法在飞书中看到三域评分数据，导致改进对业务不可见**。

## 核心问题

1. **飞书多维表缺失字段**：14个新字段（capability_scores 5个 + risk_scores 4个 + 汇总字段5个）未写入
2. **飞书通知卡片未展示**：推送消息仍使用旧版total_score，三域评分细节完全不可见
3. **测试覆盖不足**：关键逻辑（_normalize_scores、priority判定、SQLite序列化）无单元测试

## 任务目标

本阶段完成飞书集成与测试补充，确保三域评分对业务可见，并通过测试防止后续回退。

---

## Task 7.2.1：飞书多维表字段映射

### 需求说明

当前`FeishuStorage`仅写入旧版5维评分（activity_score等），需新增14个字段以支持v2三域评分。

### 新增字段清单

**能力域（5个）**：
- `planning_score` (数字) - 规划能力
- `tool_use_score` (数字) - 工具使用能力
- `memory_score` (数字) - 记忆能力
- `collaboration_score` (数字) - 协作能力
- `reasoning_score` (数字) - 推理能力

**风险域（4个）**：
- `security_score` (数字) - 安全性
- `robustness_score` (数字) - 鲁棒性
- `hallucination_risk` (数字) - 幻觉风险
- `compliance_score` (数字) - 合规性

**汇总字段（5个）**：
- `capability_total` (数字) - 能力域总分
- `risk_total` (数字) - 风险域总分
- `operational_total` (数字) - 运营域总分
- `risk_level` (单选) - 风险等级（critical/high/moderate/safe/unknown）
- `evaluation_version` (文本) - 评估版本（v1.0/v2.0）

### 实施步骤

#### Step 1：检查飞书表格现有字段

```python
# 文件位置：scripts/check_feishu_fields.py（新建）

import asyncio
from src.storage.feishu_storage import FeishuStorage
from src.config import get_settings

async def check_fields():
    settings = get_settings()
    storage = FeishuStorage(settings=settings)

    # 调用飞书API获取表格字段列表
    # 参考：https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/list

    print("当前飞书表格字段：")
    # TODO: 列出所有字段名称和类型

if __name__ == "__main__":
    asyncio.run(check_fields())
```

#### Step 2：创建飞书字段（如不存在）

```python
# 文件位置：scripts/create_feishu_fields_v2.py（新建）

import asyncio
from lark_oapi.api.bitable.v1 import *
from src.config import get_settings

FIELD_DEFINITIONS = [
    # 能力域
    {"field_name": "planning_score", "type": 2, "description": "规划能力评分（0-10）"},
    {"field_name": "tool_use_score", "type": 2, "description": "工具使用能力评分（0-10）"},
    {"field_name": "memory_score", "type": 2, "description": "记忆能力评分（0-10）"},
    {"field_name": "collaboration_score", "type": 2, "description": "协作能力评分（0-10）"},
    {"field_name": "reasoning_score", "type": 2, "description": "推理能力评分（0-10）"},

    # 风险域
    {"field_name": "security_score", "type": 2, "description": "安全性评分（0-10）"},
    {"field_name": "robustness_score", "type": 2, "description": "鲁棒性评分（0-10）"},
    {"field_name": "hallucination_risk", "type": 2, "description": "幻觉风险评分（0-10）"},
    {"field_name": "compliance_score", "type": 2, "description": "合规性评分（0-10）"},

    # 汇总字段
    {"field_name": "capability_total", "type": 2, "description": "能力域总分"},
    {"field_name": "risk_total", "type": 2, "description": "风险域总分"},
    {"field_name": "operational_total", "type": 2, "description": "运营域总分"},
    {"field_name": "risk_level", "type": 3, "description": "风险等级",
     "options": ["critical", "high", "moderate", "safe", "unknown"]},
    {"field_name": "evaluation_version", "type": 1, "description": "评估版本（v1.0/v2.0）"},
]

async def create_fields():
    settings = get_settings()
    # TODO: 使用lark_oapi创建字段
    # 参考：https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/create
    pass

if __name__ == "__main__":
    asyncio.run(create_fields())
```

**重要**：
- 字段类型：1=文本, 2=数字, 3=单选
- 单选字段需提前定义options
- 字段创建后获取field_id，后续写入时需要

#### Step 3：更新FeishuStorage写入逻辑

```python
# 文件位置：src/storage/feishu_storage.py

# 找到 _build_record 方法（当前约80-120行）

def _build_record(self, candidate: ScoredCandidate) -> dict:
    """构建飞书表格记录（包含v2三域评分）"""

    # 基础字段（保持不变）
    record = {
        "标题": candidate.title,
        "URL": candidate.url,
        # ... 其他现有字段
    }

    # 旧版5维评分（保持兼容）
    record.update({
        "activity_score": candidate.activity_score,
        "reproducibility_score": candidate.reproducibility_score,
        "license_score": candidate.license_score,
        "novelty_score": candidate.novelty_score,
        "relevance_score": candidate.relevance_score,
    })

    # 新增：能力域评分
    if candidate.capability_scores:
        record.update({
            "planning_score": candidate.capability_scores.planning_score,
            "tool_use_score": candidate.capability_scores.tool_use_score,
            "memory_score": candidate.capability_scores.memory_score,
            "collaboration_score": candidate.capability_scores.collaboration_score,
            "reasoning_score": candidate.capability_scores.reasoning_score,
        })

    # 新增：风险域评分
    if candidate.risk_scores:
        record.update({
            "security_score": candidate.risk_scores.security_score,
            "robustness_score": candidate.risk_scores.robustness_score,
            "hallucination_risk": candidate.risk_scores.hallucination_risk,
            "compliance_score": candidate.risk_scores.compliance_score,
        })

    # 新增：汇总字段
    record.update({
        "capability_total": candidate.capability_total,
        "risk_total": candidate.risk_total,
        "operational_total": candidate.operational_total,
        "risk_level": candidate.risk_level or "unknown",
        "evaluation_version": candidate.evaluation_version or "v1.0",
    })

    return record
```

**验证要点**：
- 旧版候选（无三域评分）：仅写入operational_total和v1.0版本
- 新版候选（有三域评分）：写入完整14个字段
- 字段缺失时使用默认值（0.0或"unknown"）

---

## Task 7.2.2：飞书通知卡片展示三域评分

### 需求说明

当前飞书通知仅显示total_score，用户无法看到三域评分细节。需在卡片消息中展示能力/风险/运营三域得分。

### 设计方案

**推送策略**：
- High优先级：完整三域评分 + 风险等级 + reasoning摘要
- Medium优先级：三域总分 + 风险等级
- Low优先级：仅总分（保持现有格式）

### 实施步骤

#### Step 1：更新_build_card_content方法

```python
# 文件位置：src/notifier/feishu_notifier.py

# 找到 _build_card_content 方法（当前约140-250行）

def _build_card_content(self, candidates: List[ScoredCandidate], priority: str) -> dict:
    """构建飞书卡片消息（展示三域评分）"""

    if priority == "high":
        return self._build_high_priority_card(candidates)
    elif priority == "medium":
        return self._build_medium_priority_card(candidates)
    else:
        return self._build_low_priority_card(candidates)

def _build_high_priority_card(self, candidates: List[ScoredCandidate]) -> dict:
    """高优先级卡片：完整三域评分"""

    elements = []

    for candidate in candidates:
        # 标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{candidate.title[:constants.TITLE_TRUNCATE_MEDIUM]}**"
            }
        })

        # 来源和总分
        source_name = constants.FEISHU_SOURCE_NAME_MAP.get(candidate.source, candidate.source)
        elements.append({
            "tag": "div",
            "fields": [
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**来源**: {source_name}"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**总分**: {candidate.total_score:.1f}/10"}},
            ]
        })

        # 新增：三域评分
        if candidate.capability_scores and candidate.risk_scores:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**能力域**: {candidate.capability_total:.1f} "
                        f"(规划{candidate.capability_scores.planning_score:.1f} "
                        f"工具{candidate.capability_scores.tool_use_score:.1f} "
                        f"推理{candidate.capability_scores.reasoning_score:.1f})\n"
                        f"**风险域**: {candidate.risk_total:.1f} "
                        f"(安全{candidate.risk_scores.security_score:.1f} "
                        f"鲁棒{candidate.risk_scores.robustness_score:.1f})\n"
                        f"**运营域**: {candidate.operational_total:.1f}"
                    )
                }
            })

            # 新增：风险等级标识
            risk_emoji = {
                "safe": "🟢",
                "moderate": "🟡",
                "high": "🟠",
                "critical": "🔴",
                "unknown": "⚪"
            }
            risk_text = f"{risk_emoji.get(candidate.risk_level, '⚪')} 风险等级: {candidate.risk_level}"
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": risk_text}
            })

        # Reasoning摘要（前200字）
        if candidate.reasoning:
            reasoning_preview = candidate.reasoning[:200] + ("..." if len(candidate.reasoning) > 200 else "")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**评分依据**: {reasoning_preview}"
                }
            })

        # 按钮
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看详情"},
                    "type": "primary",
                    "url": candidate.url
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "飞书多维表"},
                    "url": constants.FEISHU_BENCH_TABLE_URL
                }
            ]
        })

        elements.append({"tag": "hr"})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": f"🔥 高优先级Benchmark候选 ({len(candidates)}条)"}
        },
        "elements": elements
    }

def _build_medium_priority_card(self, candidates: List[ScoredCandidate]) -> dict:
    """中优先级卡片：三域总分"""

    elements = []

    for candidate in candidates:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{candidate.title[:constants.TITLE_TRUNCATE_MEDIUM]}**"
            }
        })

        # 三域总分（v2）或旧版总分（v1）
        if candidate.capability_scores and candidate.risk_scores:
            score_text = (
                f"总分 {candidate.total_score:.1f}/10 = "
                f"能力{candidate.capability_total:.1f} + "
                f"风险{candidate.risk_total:.1f} + "
                f"运营{candidate.operational_total:.1f}"
            )
            risk_label = f" | 风险: {candidate.risk_level}"
        else:
            score_text = f"总分 {candidate.total_score:.1f}/10"
            risk_label = ""

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": score_text + risk_label
            }
        })

        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看详情"},
                "url": candidate.url
            }]
        })

        elements.append({"tag": "hr"})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"📌 中优先级Benchmark候选 ({len(candidates)}条)"}
        },
        "elements": elements
    }

def _build_low_priority_card(self, candidates: List[ScoredCandidate]) -> dict:
    """低优先级卡片：保持简洁（仅总分）"""
    # 保持现有实现不变
    pass
```

**展示效果预期**：

**High优先级卡片**：
```
🔥 高优先级Benchmark候选 (3条)

**AgentBench: Evaluating LLMs as Agents**
来源: arXiv | 总分: 8.2/10

能力域: 8.5 (规划8.5 工具9.0 推理8.0)
风险域: 7.8 (安全8.0 鲁棒7.5)
运营域: 8.0

🟡 风险等级: moderate

评分依据: 【能力域分析】该Benchmark系统性评估了LLM的规划、工具使用、推理能力，覆盖8个场景...

[查看详情] [飞书多维表]
```

**Medium优先级卡片**：
```
📌 中优先级Benchmark候选 (5条)

**WebArena: Realistic Web Environment**
总分 7.3/10 = 能力7.0 + 风险6.8 + 运营8.0 | 风险: moderate

[查看详情]
```

---

## Task 7.2.3：补充单元测试

### 需求说明

当前关键逻辑无测试覆盖，存在回退风险。需补充：
1. `_normalize_scores` 测试（新旧格式兼容）
2. `priority` 属性测试（风险等级影响优先级）
3. SQLite序列化往返测试

### 实施步骤

#### Test 1：LLMScorer._normalize_scores测试

```python
# 文件位置：tests/test_scorer.py（新建或扩展）

import pytest
from src.scorer.llm_scorer import LLMScorer
from src.models import AgentCapabilityScores, RiskDomainScores, OperationalScores

class TestLLMScorer:

    def test_normalize_scores_v2_format(self):
        """测试v2格式（三域完整）正常化"""
        scorer = LLMScorer()

        input_scores = {
            "capability_scores": {
                "planning_score": 8.5,
                "tool_use_score": 7.5,
                "memory_score": 6.0,
                "collaboration_score": 5.5,
                "reasoning_score": 7.0
            },
            "risk_scores": {
                "security_score": 7.5,
                "robustness_score": 6.5,
                "hallucination_risk": 6.0,
                "compliance_score": 8.0
            },
            "operational_scores": {
                "activity_score": 8.0,
                "reproducibility_score": 7.5,
                "license_score": 9.0,
                "novelty_score": 6.5,
                "relevance_score": 8.5
            },
            "reasoning": "测试reasoning"
        }

        normalized = scorer._normalize_scores(input_scores)

        assert "capability_scores" in normalized
        assert "risk_scores" in normalized
        assert "operational_scores" in normalized
        assert normalized["capability_scores"]["planning_score"] == 8.5
        assert normalized["reasoning"] == "测试reasoning"

    def test_normalize_scores_v1_compat(self):
        """测试v1扁平格式自动转换"""
        scorer = LLMScorer()

        input_scores = {
            "activity_score": 7.5,
            "reproducibility_score": 8.0,
            "license_score": 7.0,
            "novelty_score": 6.5,
            "relevance_score": 8.5,
            "reasoning": "旧版评分"
        }

        normalized = scorer._normalize_scores(input_scores)

        # 应自动补全三域结构
        assert "operational_scores" in normalized
        assert normalized["operational_scores"]["activity_score"] == 7.5
        assert "capability_scores" in normalized
        assert "risk_scores" in normalized

    def test_normalize_scores_clamp(self):
        """测试分数范围限制（0-10）"""
        scorer = LLMScorer()

        input_scores = {
            "capability_scores": {
                "planning_score": 15.0,  # 超出范围
                "tool_use_score": -2.0,  # 低于0
                "memory_score": 5.0,
                "collaboration_score": "invalid",  # 非数字
                "reasoning_score": 7.0
            },
            "risk_scores": {},
            "operational_scores": {},
            "reasoning": ""
        }

        normalized = scorer._normalize_scores(input_scores)

        assert normalized["capability_scores"]["planning_score"] == 10.0  # 限制到10
        assert normalized["capability_scores"]["tool_use_score"] == 0.0   # 限制到0
        assert normalized["capability_scores"]["collaboration_score"] == 0.0  # 无效值归0
```

#### Test 2：ScoredCandidate.priority测试

```python
# 文件位置：tests/test_models.py（新建或扩展）

import pytest
from src.models import ScoredCandidate, AgentCapabilityScores, RiskDomainScores, OperationalScores

class TestScoredCandidate:

    def test_priority_v2_high_with_safe_risk(self):
        """测试v2高优先级：高分+低风险"""
        cap = AgentCapabilityScores(
            planning_score=9.0, tool_use_score=8.5, memory_score=7.5,
            collaboration_score=7.0, reasoning_score=8.0
        )
        risk = RiskDomainScores(
            security_score=8.0, robustness_score=7.5,
            hallucination_risk=7.0, compliance_score=8.5
        )
        ops = OperationalScores(
            activity_score=8.0, reproducibility_score=8.5,
            license_score=9.0, novelty_score=7.0, relevance_score=8.5
        )

        candidate = ScoredCandidate(
            title="Test", url="https://test.com", source="arxiv",
            capability_scores=cap, risk_scores=risk, operational_scores=ops,
            risk_level="safe"
        )

        # total_score应该>8.0 且 risk_level=safe → high
        assert candidate.total_score >= 8.0
        assert candidate.priority == "high"

    def test_priority_v2_medium_with_high_risk(self):
        """测试v2中优先级：高分但高风险"""
        cap = AgentCapabilityScores(
            planning_score=9.0, tool_use_score=8.5, memory_score=7.5,
            collaboration_score=7.0, reasoning_score=8.0
        )
        risk = RiskDomainScores(
            security_score=4.0,  # 低安全分
            robustness_score=4.5,
            hallucination_risk=5.0,
            compliance_score=5.5
        )
        ops = OperationalScores(
            activity_score=8.0, reproducibility_score=8.5,
            license_score=9.0, novelty_score=7.0, relevance_score=8.5
        )

        candidate = ScoredCandidate(
            title="Test", url="https://test.com", source="github",
            capability_scores=cap, risk_scores=risk, operational_scores=ops,
            risk_level="high"  # 高风险
        )

        # 虽然总分高，但风险高 → 不能是high优先级
        assert candidate.total_score >= 8.0
        assert candidate.priority != "high"
        assert candidate.priority in ["medium", "low"]

    def test_priority_v1_fallback(self):
        """测试v1兼容模式（无三域评分）"""
        candidate = ScoredCandidate(
            title="Old Test", url="https://test.com", source="arxiv",
            activity_score=8.5, reproducibility_score=8.0,
            license_score=7.5, novelty_score=7.0, relevance_score=8.0
        )

        # 应使用旧版逻辑（仅看total_score）
        assert candidate.total_score >= 8.0
        assert candidate.priority == "high"

    def test_total_score_v2_calculation(self):
        """测试v2三域加权计算"""
        cap = AgentCapabilityScores(
            planning_score=8.0, tool_use_score=8.0, memory_score=8.0,
            collaboration_score=8.0, reasoning_score=8.0
        )  # capability_total = 8.0

        risk = RiskDomainScores(
            security_score=6.0, robustness_score=6.0,
            hallucination_risk=6.0, compliance_score=6.0
        )  # risk_total = 6.0

        ops = OperationalScores(
            activity_score=7.0, reproducibility_score=7.0,
            license_score=7.0, novelty_score=7.0, relevance_score=7.0
        )  # operational_total = 7.0

        candidate = ScoredCandidate(
            title="Test", url="https://test.com", source="github",
            capability_scores=cap, risk_scores=risk, operational_scores=ops
        )

        # total = 8.0*0.4 + 6.0*0.3 + 7.0*0.3 = 3.2 + 1.8 + 2.1 = 7.1
        assert abs(candidate.total_score - 7.1) < 0.01
```

#### Test 3：SQLite序列化往返测试

```python
# 文件位置：tests/test_sqlite_fallback.py（新建或扩展）

import pytest
from datetime import datetime
from src.storage.sqlite_fallback import SQLiteFallback
from src.models import ScoredCandidate, AgentCapabilityScores, RiskDomainScores, OperationalScores

class TestSQLiteFallback:

    def test_serialize_deserialize_v2_roundtrip(self):
        """测试v2候选序列化往返"""
        original = ScoredCandidate(
            title="Test Benchmark",
            url="https://github.com/test/benchmark",
            source="github",
            abstract="Test abstract",
            capability_scores=AgentCapabilityScores(
                planning_score=8.5, tool_use_score=7.5,
                memory_score=6.5, collaboration_score=5.5,
                reasoning_score=7.0
            ),
            risk_scores=RiskDomainScores(
                security_score=7.5, robustness_score=6.5,
                hallucination_risk=6.0, compliance_score=8.0
            ),
            operational_scores=OperationalScores(
                activity_score=8.0, reproducibility_score=7.5,
                license_score=9.0, novelty_score=6.5,
                relevance_score=8.5
            ),
            reasoning="Test reasoning",
            risk_level="moderate",
            last_evaluated_at=datetime.now(),
            evaluation_version="v2.0"
        )

        # 序列化
        raw_dict = SQLiteFallback._serialize_raw(original)
        scores_dict = SQLiteFallback._serialize_scores(original)

        # 反序列化
        raw_restored = SQLiteFallback._deserialize_raw(raw_dict)
        scores_restored = SQLiteFallback._deserialize_scores(scores_dict)

        # 重建对象
        restored = ScoredCandidate(**raw_restored, **scores_restored)

        # 验证往返一致性
        assert restored.title == original.title
        assert restored.url == original.url
        assert restored.capability_scores.planning_score == 8.5
        assert restored.risk_scores.security_score == 7.5
        assert restored.operational_scores.activity_score == 8.0
        assert restored.risk_level == "moderate"
        assert restored.evaluation_version == "v2.0"
        assert abs(restored.total_score - original.total_score) < 0.01

    def test_serialize_deserialize_v1_compat(self):
        """测试v1候选兼容"""
        original = ScoredCandidate(
            title="Old Benchmark",
            url="https://arxiv.org/abs/1234.5678",
            source="arxiv",
            activity_score=7.5,
            reproducibility_score=8.0,
            license_score=7.0,
            novelty_score=6.5,
            relevance_score=8.5,
            reasoning="Old reasoning",
            evaluation_version="v1.0"
        )

        raw_dict = SQLiteFallback._serialize_raw(original)
        scores_dict = SQLiteFallback._serialize_scores(original)

        raw_restored = SQLiteFallback._deserialize_raw(raw_dict)
        scores_restored = SQLiteFallback._deserialize_scores(scores_dict)

        restored = ScoredCandidate(**raw_restored, **scores_restored)

        # v1候选应自动构建operational_scores
        assert restored.operational_scores is not None
        assert restored.operational_scores.activity_score == 7.5
        assert restored.evaluation_version == "v1.0"
```

**运行测试**：
```bash
.venv/bin/python -m pytest tests/test_scorer.py -v
.venv/bin/python -m pytest tests/test_models.py -v
.venv/bin/python -m pytest tests/test_sqlite_fallback.py -v
```

---

## 验收标准

### 功能验收

**1. 飞书多维表字段**：
- [ ] 14个新字段成功创建（或已存在）
- [ ] v2候选写入时所有字段有值（非空）
- [ ] v1候选写入时仅operational_total有值，三域字段为0或空
- [ ] 手动检查飞书表格：打开1条v2记录，验证capability_total/risk_level等字段可见

**2. 飞书通知卡片**：
- [ ] High优先级显示完整三域评分 + 风险等级 + reasoning摘要
- [ ] Medium优先级显示三域总分 + 风险等级
- [ ] Low优先级保持简洁（仅总分）
- [ ] 手动测试：运行`scripts/test_layered_notification.py`，检查飞书收到的卡片格式

**3. 单元测试**：
- [ ] `test_normalize_scores_v2_format` 通过
- [ ] `test_normalize_scores_v1_compat` 通过
- [ ] `test_normalize_scores_clamp` 通过
- [ ] `test_priority_v2_high_with_safe_risk` 通过
- [ ] `test_priority_v2_medium_with_high_risk` 通过
- [ ] `test_serialize_deserialize_v2_roundtrip` 通过
- [ ] 所有测试覆盖率 ≥ 80%

### 性能验收

- [ ] 飞书写入时间增加 < 10%（新增字段不应显著降低性能）
- [ ] 飞书通知推送时间 < 3秒（卡片内容更复杂不应超时）

### 兼容性验收

- [ ] 旧版候选（v1.0）在新系统中正常显示（不报错）
- [ ] 新版候选（v2.0）在飞书中正确展示三域评分
- [ ] SQLite降级备份正常（v2候选写入后可恢复）

---

## 强制约束

### 代码规范

1. **PEP8强制遵守**：
   ```bash
   black src/storage/feishu_storage.py src/notifier/feishu_notifier.py
   ruff check src/storage/ src/notifier/ --fix
   ```

2. **关键逻辑必须中文注释**：
   ```python
   # 兼容v1扁平结构：将旧版5维评分转换为operational_scores
   if operational is None and all(key in scores for key in [...]):
       operational = {...}
   ```

3. **魔法数字必须常量化**：
   ```python
   # Bad
   reasoning_preview = candidate.reasoning[:200]

   # Good
   REASONING_PREVIEW_LENGTH: Final[int] = 200
   reasoning_preview = candidate.reasoning[:constants.REASONING_PREVIEW_LENGTH]
   ```

### 测试要求

1. **关键路径必须测试**：
   - `_normalize_scores` (3个测试)
   - `priority` 属性 (4个测试)
   - SQLite序列化 (2个测试)

2. **测试必须独立**：
   - 不依赖外部API（mock飞书API调用）
   - 不依赖环境变量（使用fixture提供配置）

3. **测试必须可重复**：
   - 固定随机种子
   - 固定时间戳（用freezegun）

### 向后兼容

1. **绝对禁止破坏v1数据**：
   - v1候选必须能正常读取、显示、推送
   - 飞书旧记录不得因新字段而报错

2. **降级策略**：
   - 新字段缺失时使用默认值
   - Pydantic对象为None时回退到扁平字段

3. **版本标识**：
   - 所有新评分必须标记`evaluation_version="v2.0"`
   - 飞书卡片显示版本号（可选）

---

## 实施时间线

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| 7.2.1 | 飞书字段映射 | 2小时 |
| 7.2.2 | 通知卡片更新 | 3小时 |
| 7.2.3 | 单元测试补充 | 2小时 |
| **总计** | | **7小时** |

---

## 交付物清单

### 新增文件

- [ ] `scripts/check_feishu_fields.py` - 飞书字段检查脚本
- [ ] `scripts/create_feishu_fields_v2.py` - 飞书字段创建脚本
- [ ] `tests/test_scorer.py` - LLMScorer单元测试
- [ ] `tests/test_models.py` - ScoredCandidate单元测试
- [ ] `tests/test_sqlite_fallback.py` - SQLite序列化测试

### 修改文件

- [ ] `src/storage/feishu_storage.py` - 新增14字段写入逻辑
- [ ] `src/notifier/feishu_notifier.py` - 三域评分卡片展示
- [ ] `src/common/constants.py` - 新增常量（如有）

### 文档更新

- [ ] `.claude/CLAUDE.md` - 更新Phase 7进度（7.1完成 → 7.2完成）
- [ ] `docs/phase7-test-report.md` - 手动测试报告（飞书截图）

---

## 后续计划（Phase 7.3-7.5）

完成本阶段后，Phase 7剩余任务：

- **Phase 7.3** (Week 4): Task 3安全验证器 + Task 2自进化样本池
- **Phase 7.4** (Week 5): Task 4持续学习调度 + Task 5双轨信息抽取
- **Phase 7.5** (Week 6): 集成测试 + 上线部署

---

## 注意事项

### Codex执行要求

1. **严格按照本文档实施**，不得自行修改设计
2. **文档不清晰时先询问**，不得猜测
3. **完成后通知Claude Code验收**，提供：
   - 改动文件清单
   - 编译验证结果
   - 测试运行截图
   - 飞书推送截图（手动测试）

### Claude Code验收要求

1. **代码review**：检查PEP8、魔法数字、中文注释
2. **功能测试**：运行`src/main.py`完整流程
3. **飞书验证**：检查多维表字段和通知卡片
4. **测试执行**：运行pytest确认覆盖率

---

**预期完成时间**：2025-11-14 18:00前

**优先级**：🔴 Critical（阻塞Phase 7后续任务）
