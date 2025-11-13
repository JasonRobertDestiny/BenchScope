# 2025-11-13 Bug修复总结

## 修复的问题

### 1. requirements.txt重复依赖
**问题**: Flask和gunicorn在requirements.txt中出现两次
- 行 11-12: 首次添加
- 行 17-18: 重复添加

**修复**: 移除重复条目，保留行 15-16

**提交**: `d01fe6e` - fix: 修复requirements.txt重复依赖并移除HuggingFace时间过滤

---

### 2. HuggingFace时间过滤过严
**问题**: HuggingFace采集器使用14天时间窗口过滤数据集，导致0结果

**用户反馈**:
> "HuggingFace没有数据，我们是日更新，但是数据可以是很久以前呀，符合我们的要求就行了呀"

**修复**: 移除时间过滤逻辑
- 删除 `_to_candidate()` 中的时间检查（行 109-110）
- 添加详细docstring解释原因

**理由**:
- 优质Benchmark数据集即使发布较早也有价值
- 时间过滤更适合GitHub（活跃维护）和arXiv（最新研究）
- HuggingFace数据集应依据：下载量 + 关键词匹配

**提交**: `d01fe6e` - fix: 修复requirements.txt重复依赖并移除HuggingFace时间过滤

---

### 3. HuggingFace采集器返回0结果（重大Bug）
**问题**: 即使移除时间过滤，HuggingFace采集器仍返回0个候选项

**根本原因诊断**:
1. **API搜索语法问题**: HuggingFace API不支持OR操作符
   - `"benchmark OR evaluation"` → 0个结果 ❌
   - `"benchmark"` → 5个结果 ✅
   - 空格表示AND逻辑，不是OR

2. **task_categories过滤过严**: 多个task_categories使用AND逻辑
   - 要求数据集同时属于所有3个类别
   - 实际很少有数据集同时属于"text-generation" AND "question-answering" AND "code"

3. **嵌套字典访问bug**: `data.get("cardData", {})` 如果cardData为None会失败
   - `AttributeError: 'NoneType' object has no attribute 'get'`

4. **时间戳格式多样**: API返回多种格式导致解析失败
   - ISO 8601字符串: `"2024-11-13T12:00:00Z"`
   - Unix时间戳: 整数
   - datetime对象

**修复措施**:
1. **移除task_categories过滤** - 避免AND逻辑
2. **修改搜索策略** - 轮询每个关键词并合并去重
   ```python
   for keyword in self.cfg.keywords:
       datasets = self.api.list_datasets(search=keyword, ...)
       # 合并去重
   ```
3. **安全访问嵌套字典**
   ```python
   card_data = data.get("cardData") or data.get("card_data") or {}
   authors = card_data.get("authors")
   ```
4. **增强时间戳解析** - 支持多种格式
   ```python
   def _parse_datetime(value: str | int | datetime | None):
       if isinstance(value, datetime): return value
       if isinstance(value, int): return datetime.fromtimestamp(value, tz=timezone.utc)
       if isinstance(value, str): return datetime.fromisoformat(...)
   ```

**测试结果**:
- 修复前: **0个候选项** ❌
- 修复后: **136个候选项** ✅
- 示例:
  - `gaia-benchmark/results_public` (2,161下载量)
  - `hf-benchmarks/transformers` (543下载量)
  - `miromind-ai/MiroFlow-Benchmarks` (872下载量)

**提交**: `a948801` - fix(huggingface): 修复采集器返回0结果的问题

---

### 4. Twitter/X API凭证存储
**任务**: 为Phase 6 可选任务（Twitter监听）准备API凭证

**操作**:
1. 添加Twitter凭证到 `.env.local`:
   - Bearer Token (API v2只读)
   - OAuth 1.0a凭证（完整权限）
2. 更新 `.env.example` 添加占位符和说明

**凭证类型**:
- `TWITTER_BEARER_TOKEN`: 用于Twitter API v2只读访问
- `TWITTER_API_KEY` + `TWITTER_API_KEY_SECRET`: OAuth 1.0a应用凭证
- `TWITTER_ACCESS_TOKEN` + `TWITTER_ACCESS_TOKEN_SECRET`: 用户级别访问令牌

**状态**: 凭证已安全存储，Phase 6实施时可直接使用

---

## 提交记录

```
d01fe6e - fix: 修复requirements.txt重复依赖并移除HuggingFace时间过滤
a948801 - fix(huggingface): 修复采集器返回0结果的问题
```

## 测试验证

### HuggingFace采集器测试
```bash
source .venv/bin/activate
python -c "
import asyncio
from src.collectors.huggingface_collector import HuggingFaceCollector

async def test():
    collector = HuggingFaceCollector()
    candidates = await collector.collect()
    print(f'采集结果: {len(candidates)}个候选项')

asyncio.run(test())
"
```

**预期输出**: `采集结果: 136个候选项`

---

## 下一步工作

1. **部署Flask回调服务**:
   ```bash
   pip install -r requirements.txt
   ./scripts/start_callback_service.sh
   ```

2. **测试新字段自动填充**:
   ```bash
   python src/main.py
   # 检查飞书表格中的新字段是否有数据
   ```

3. **Phase 6开发启动** (可选):
   - Task 6.1: 扩展会议论文采集 (Semantic Scholar + ACL Anthology)
   - Task 6.2: 接入评测榜单 (HELM + Open LLM Leaderboard)
   - Task 6.3: 优化GitHub搜索策略
   - Task 6.4: 完善飞书表格字段（9个新字段）
   - Task 6.5: 优化预筛选规则
   - Task 6.6: 优化LLM评分Prompt

---

**文档生成时间**: 2025-11-13
**修复人**: Claude Code
**相关Issue**: 用户报告HuggingFace采集器返回0结果
