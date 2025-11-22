# Codex开发指令：arXiv 去重窗口优化 PRD

## 文档元信息
- 创建时间：2025-11-22
- 创建者：Codex
- 执行者：Codex
- 优先级：P1（重要）
- 预计工作量：30分钟
- 关联问题：arXiv 100% 去重，零新发现

## 背景与现状
- 采集窗口：arXiv 7 天
- 去重窗口：全来源 14 天
- 现象：arXiv 100 条候选 → 0 条新发现，说明 7 天采集窗口完全被 14 天去重窗口覆盖。
- 目标：在不提高重复率的前提下，确保 arXiv 每次运行有 ≥5 条新发现。

## 根因
- 去重比对所有来源统一 14 天，导致 arXiv 近 7 天的新论文被前一天的结果挡住。

## 方案对比
| 方案 | 采集窗口 | 去重窗口 (arXiv) | 影响 | 风险 |
|---|---|---|---|---|
| A（推荐） | 7 天 | 7 天 | 避免跨日重叠，保留近 7 天去重保护；其他来源仍 14 天 | 低 |
| B | 3 天 | 14 天 | 去重不改，缩采集窗口；降低覆盖度，可能漏第 4-7 天论文 | 中 |
| C | 7 天 | 5 天 | 加大召回，去重更宽松 | 重复率略升 |
| D | 自适应 | 7 天 | 按每日新增自动调去重窗 | 需更多开发 |

## 推荐方案（A）
- 引入按来源去重窗口配置，arXiv 使用 7 天，默认 14 天。
- 不改采集窗口，保留 7 天抓取。

## 实施步骤
1) **新增配置**
   - 文件：`src/common/constants.py`
   - 新增：
     ```python
     DEDUP_LOOKBACK_DAYS_BY_SOURCE: Final[dict[str, int]] = {
         "arxiv": 7,
         "default": DEDUP_LOOKBACK_DAYS,  # 14
     }
     ```
2) **存储读取复用**（已有 `read_existing_records`，无需改）
3) **去重逻辑修改**
   - 文件：`src/main.py`
   - 在去重阶段，根据 `candidate.source` 选择对应窗口：
     ```python
     def _dedup_window_for(source: str) -> int:
         return constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE.get(
             source, constants.DEDUP_LOOKBACK_DAYS_BY_SOURCE["default"]
         )
     ```
   - 构建 `recent_urls` 时按来源分桶，分别应用窗口。
4) **日志**
   - 在去重统计里追加“窗口天数”字段，便于观察。

## 验收标准
- arXiv 新发现 ≥5 条/次运行。
- arXiv 去重率 <70%，总体去重率保持 <60%。
- 推送来源包含 arXiv。

## 风险与回滚
- 风险：窗口过短导致重复上升。缓解：窗口改为 10 天快速回滚。
- 回滚方法：删除按来源窗口逻辑，恢复统一 `DEDUP_LOOKBACK_DAYS`。

## 里程碑
- T+0.5h：完成代码修改+本地跑一次 `.venv/bin/python -m src.main`
- T+1h：评估日志，若 arXiv 仍 0，则将 arXiv 去重窗口调为 5 天重跑。
