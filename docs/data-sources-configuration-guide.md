# 数据源配置指南

## 概述

BenchScope支持多源数据采集，配置方式有两种：
1. **代码级常量** (`src/common/constants.py`) - 当前使用方式
2. **YAML配置文件** (`config/sources.yaml`) - Phase 6推荐方式

---

## 已实现的数据源

### 1. 论文库 (5个已实现)

| 来源 | Collector | 配置位置 | API密钥 | 状态 |
|------|-----------|---------|--------|------|
| arXiv | `arxiv_collector.py` | `constants.py:7-17` | 不需要 | ✅ 运行中 |
| ACL | `semantic_scholar_collector.py` | `constants.py:25-46` | 需要 | ✅ 运行中 |
| NeurIPS | 同上 | 同上 | 需要 | ✅ 运行中 |
| ICLR | 同上 | 同上 | 需要 | ✅ 运行中 |
| ICML | 同上 | 同上 | 需要 | ✅ 运行中 |

**配置示例**:
```python
# src/common/constants.py
SEMANTIC_SCHOLAR_VENUES = ["NeurIPS", "ICLR", "ICML", "ACL", "EMNLP"]
SEMANTIC_SCHOLAR_LOOKBACK_YEARS = 2  # 采集最近2年论文
SEMANTIC_SCHOLAR_KEYWORDS = ["benchmark", "evaluation", "dataset"]
```

**环境变量**:
```bash
# .env.local
SEMANTIC_SCHOLAR_API_KEY=your_api_key_here  # 从https://www.semanticscholar.org/product/api获取
```

### 2. 评测榜单 (1个已实现, 2个待实现)

| 来源 | Collector | 状态 |
|------|-----------|------|
| HELM | `helm_collector.py` | ✅ 运行中 |
| Open LLM Leaderboard | - | ⏭️ Phase 6 |
| EvalPlus | - | ⏭️ Phase 6 |

**配置示例**:
```python
# src/common/constants.py
HELM_DEFAULT_RELEASE = "v0.4.0"
HELM_TIMEOUT_SECONDS = 15
```

### 3. 开源社区 (2个已实现)

| 来源 | Collector | 配置位置 | API密钥 | 状态 |
|------|-----------|---------|--------|------|
| GitHub | `github_collector.py` | `constants.py:19-23` | 可选 | ✅ 运行中 |
| HuggingFace Hub | `huggingface_collector.py` | `constants.py:69-81` | 不需要 | ✅ 运行中 |

**配置示例**:
```python
# src/common/constants.py
GITHUB_TOPICS = ["benchmark", "evaluation", "agent"]
GITHUB_LOOKBACK_DAYS = 30

HUGGINGFACE_KEYWORDS = ["benchmark", "evaluation", "leaderboard"]
HUGGINGFACE_MIN_DOWNLOADS = 100
HUGGINGFACE_LOOKBACK_DAYS = 14
```

**环境变量** (可选):
```bash
# .env.local
GITHUB_TOKEN=ghp_xxxxxxxxxxxx  # GitHub Personal Access Token，可提升API限额到5000请求/小时
```

### 4. 团队线索 (待实现)

| 来源 | 状态 | 计划 |
|------|------|------|
| 飞书群聊集成 | ⏭️ Phase 7+ | 监听关键词，自动提取Benchmark线索 |

### 5. 社交媒体 (可选，待实现)

| 来源 | 状态 | 计划 |
|------|------|------|
| Twitter/X | ⏭️ Phase 7+ | 监听AI领域KOL账号 |

---

## 配置方法

### 方法1: 修改代码常量（当前方式）

**文件**: `src/common/constants.py`

**示例：添加新的顶会**
```python
# 在第27-37行添加新会议
SEMANTIC_SCHOLAR_VENUES: Final[list[str]] = [
    "NeurIPS",
    "ICLR",
    "ICML",
    "ACL",
    "EMNLP",
    "AAAI",  # 新增
    "IJCAI",  # 新增
]
```

**示例：调整时间窗口**
```python
# 第10行：arXiv改为14天窗口
ARXIV_LOOKBACK_HOURS: Final[int] = 336  # 14天 (原168小时)

# 第26行：Semantic Scholar改为3年
SEMANTIC_SCHOLAR_LOOKBACK_YEARS: Final[int] = 3  # 原2年
```

**优点**: 类型安全、编译期检查、无需解析YAML
**缺点**: 修改需要重新部署

### 方法2: 使用YAML配置（Phase 6推荐）

**文件**: `config/sources.yaml`

**使用方式**:
1. 修改 `config/sources.yaml` 中的参数
2. 重启采集服务即可生效，无需重新部署代码

**示例：启用新数据源**
```yaml
# config/sources.yaml
evalplus:
  enabled: true  # 从false改为true
  github_repo: "evalplus/evalplus"
  api_url: "https://evalplus.github.io/leaderboard.html"
  timeout_seconds: 15
```

**示例：调整关键词**
```yaml
arxiv:
  keywords:
    - benchmark
    - agent evaluation
    - code generation
    - web automation
    - reasoning tasks  # 新增
```

**优点**: 运行时修改、无需重新部署、便于非技术人员调整
**缺点**: 需要实现YAML加载逻辑（Phase 6任务）

---

## API密钥获取

### 1. Semantic Scholar API Key
1. 访问 https://www.semanticscholar.org/product/api
2. 点击 "Get API Key"
3. 注册账号并申请API密钥
4. 将密钥添加到 `.env.local`:
   ```bash
   SEMANTIC_SCHOLAR_API_KEY=your_key_here
   ```

**限额**: 100请求/5分钟（免费）, 5000请求/5分钟（付费）

### 2. GitHub Personal Access Token (可选)
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `public_repo` 权限
4. 生成Token并复制
5. 添加到 `.env.local`:
   ```bash
   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   ```

**限额**: 无Token 60请求/小时, 有Token 5000请求/小时

### 3. HuggingFace API Token (暂不需要)
当前HuggingFace采集器不需要API密钥（使用公开API）

---

## 启用/禁用数据源

### 方法1: 代码修改（当前）
**不推荐**，因为需要修改代码并重新部署。

### 方法2: YAML配置（Phase 6后）
修改 `config/sources.yaml` 中的 `enabled` 字段：

```yaml
arxiv:
  enabled: true  # 启用

helm:
  enabled: false  # 禁用
```

### 方法3: 环境变量（临时禁用）
```bash
# .env.local
DISABLE_ARXIV=true
DISABLE_GITHUB=true
```

需要在代码中实现环境变量检查逻辑（Phase 6任务）。

---

## 数据采集流程

```
1. 主编排器 (src/main.py)
   ↓
2. 并发调用所有enabled的Collectors
   ├─ ArxivCollector.collect()
   ├─ GitHubCollector.collect()
   ├─ SemanticScholarCollector.collect()
   ├─ HelmCollector.collect()
   └─ HuggingFaceCollector.collect()
   ↓
3. 合并结果 + URL去重
   ↓
4. 规则预筛选 (src/prefilter/)
   ↓
5. LLM评分 (src/scorer/)
   ↓
6. 存储到飞书多维表格 (src/storage/)
   ↓
7. 飞书通知推送 (src/notifier/)
```

**当前运行命令**:
```bash
/mnt/d/VibeCoding_pgm/BenchScope/.venv/bin/python src/main.py
```

**GitHub Actions自动运行**: 每日UTC 2:00 (北京时间10:00)

---

## 添加新数据源

### 步骤1: 创建Collector类

**文件**: `src/collectors/new_source_collector.py`

```python
"""新数据源采集器"""
from __future__ import annotations

import logging
from typing import List

import httpx

from src.models import RawCandidate

logger = logging.getLogger(__name__)


class NewSourceCollector:
    """新数据源采集器"""

    def __init__(self) -> None:
        self.api_url = "https://api.example.com/v1/data"
        self.timeout = 15

    async def collect(self) -> List[RawCandidate]:
        """采集数据"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.api_url)
            response.raise_for_status()
            data = response.json()

        candidates = [self._parse_item(item) for item in data.get("items", [])]
        logger.info(f"新数据源采集完成,候选总数{len(candidates)}")
        return candidates

    def _parse_item(self, item: dict) -> RawCandidate:
        """解析单条数据为RawCandidate"""
        return RawCandidate(
            title=item["title"],
            url=item["url"],
            source="new_source",  # 添加到models.py的SourceType
            abstract=item.get("description"),
            # ...其他字段
        )
```

### 步骤2: 添加到SourceType

**文件**: `src/models.py:10-17`

```python
SourceType = Literal[
    "arxiv",
    "github",
    "huggingface",
    "semantic_scholar",
    "helm",
    "new_source",  # 新增
]
```

### 步骤3: 注册到主编排器

**文件**: `src/main.py`

```python
from src.collectors.new_source_collector import NewSourceCollector

async def collect_all_sources() -> List[RawCandidate]:
    collectors = [
        ArxivCollector(),
        GitHubCollector(),
        HuggingFaceCollector(),
        SemanticScholarCollector(),
        HelmCollector(),
        NewSourceCollector(),  # 新增
    ]

    tasks = [collector.collect() for collector in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ...
```

### 步骤4: 添加配置常量

**文件**: `src/common/constants.py`

```python
# New Source配置
NEW_SOURCE_API_URL: Final[str] = "https://api.example.com/v1/data"
NEW_SOURCE_TIMEOUT_SECONDS: Final[int] = 15
NEW_SOURCE_LOOKBACK_DAYS: Final[int] = 7
```

### 步骤5: 测试

```bash
# 单元测试
/mnt/d/VibeCoding_pgm/BenchScope/.venv/bin/python -m pytest tests/unit/test_new_source_collector.py -v

# 集成测试
/mnt/d/VibeCoding_pgm/BenchScope/.venv/bin/python src/main.py
```

---

## 故障排查

### 问题1: Semantic Scholar API限流
**症状**: `HTTPError: 429 Too Many Requests`
**原因**: 超过API限额（100请求/5分钟）
**解决**:
1. 申请付费API密钥（5000请求/5分钟）
2. 增加重试延迟: `SEMANTIC_SCHOLAR_TIMEOUT_SECONDS = 30`
3. 减少采集频率: `SEMANTIC_SCHOLAR_MAX_RESULTS = 50`

### 问题2: GitHub API限流
**症状**: `HTTPError: 403 Forbidden, rate limit exceeded`
**原因**: 无Token限额（60请求/小时）已耗尽
**解决**: 配置GitHub Personal Access Token

### 问题3: arXiv采集超时
**症状**: `TimeoutException` 或 采集数为0
**原因**: arXiv API响应慢或关键词匹配数过少
**解决**:
1. 增加超时: `ARXIV_TIMEOUT_SECONDS = 20`
2. 放宽关键词: 添加更多相关词
3. 扩大时间窗口: `ARXIV_LOOKBACK_HOURS = 336` (14天)

### 问题4: HELM采集失败
**症状**: 采集数为0或API错误
**原因**: HELM release更新导致URL失效
**解决**: 检查 https://crfm.stanford.edu/helm/classic/latest/config.js 获取最新release版本

---

## Phase 6扩展计划

根据 `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md`，Phase 6将新增：

1. **Open LLM Leaderboard采集器** (2周开发)
   - 抓取HuggingFace Open LLM Leaderboard
   - 提取高分模型的评测Benchmark信息

2. **EvalPlus采集器** (1周开发)
   - 抓取EvalPlus GitHub仓库
   - 提取代码生成Benchmark数据

3. **ACL Anthology采集器** (1周开发)
   - 使用ACL Anthology Python API
   - 直接采集ACL系列会议论文（更准确）

4. **YAML配置加载逻辑** (3天开发)
   - 实现运行时YAML配置加载
   - 支持环境变量替换
   - 提供配置验证工具

---

## 相关文档

- **项目PRD**: `.claude/specs/benchmark-intelligence-agent/01-product-requirements.md`
- **系统架构**: `.claude/specs/benchmark-intelligence-agent/02-system-architecture.md`
- **Phase 6扩展PRD**: `.claude/specs/benchmark-intelligence-agent/PHASE6-EXPANSION-PRD.md`
- **测试报告**: `docs/phase2-5-test-report.md`
- **分层推送优化**: `docs/layered-notification-test-report.md`

---

**最后更新**: 2025-11-13
**负责人**: Claude Code
