# Codex开发指令：提升来源多样性与数据新鲜度

## 快速执行卡
- 目标：推送来源覆盖≥3个（含 arXiv/HuggingFace），去重率下降，预筛选通过率按来源可见。
- 立即动作：压缩 arXiv/HuggingFace 时间窗口；预筛选与去重阶段输出按来源统计。
- 验证：跑一次 `.venv/bin/python -m src.main`，检查日志/飞书来源分布。
- 回滚：恢复时间窗口原值（arXiv 720h、HF 14d）并删日志新增段。

## 痛点与根因（摘要）
- 飞书推送 4 条均来自 GitHub；arXiv/HuggingFace 被高去重率吃掉。
- 时间窗口过长（arXiv 30 天、HF 14 天）导致重复；日志缺少来源维度，无法定位。

## 行动清单（优先级顺序执行）
1) **压缩时间窗口**（配置改动）
   - 文件 `config/sources.yaml`
   - `arxiv.lookback_hours: 168`  # 30 天→7 天
   - `huggingface.lookback_days: 7`  # 14 天→7 天
   - 目的：减少历史重复，提高新鲜度。

2) **预筛选按来源统计**（日志改动）
   - 文件 `src/prefilter/rule_filter.py`，函数 `prefilter_batch`
   - 新增 `source_stats` 记录各来源输入/输出，并追加日志：
   ```python
   logger.info("===== 预筛选按来源统计 =====")
   for source, stats in sorted(source_stats.items()):
       pass_rate = stats["output"] / stats["input"] * 100 if stats["input"] else 0
       logger.info("  %s: %d/%d (通过率%.1f%%)", source.ljust(15), stats["output"], stats["input"], pass_rate)
   ```
   - 目的：看清各来源通过率，便于后续微调。

3) **去重后来源统计（可选，推荐）**
   - 文件 `src/main.py` 去重完成后，统计 `unique_candidates`：
   ```python
   from collections import Counter
   source_counts = Counter(c.source for c in unique_candidates)
   logger.info("===== 去重后按来源统计 =====")
   for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
       logger.info("  %s: %d条新发现", source.ljust(15), count)
   ```
   - 目的：直接看到新发现来自哪里。

## 验证步骤
- 运行：`.venv/bin/python -m src.main`
- 观察日志：
  - 去重段应出现“去重后按来源统计”
  - 预筛选段应出现“预筛选按来源统计”
- 验收标准：
  - arXiv/HuggingFace 新发现 >0 条
  - 推送来源不少于 3 个（含 arXiv/HF）
  - 去重率显著下降（<85% 为佳）

## 回滚
- 将 `arxiv.lookback_hours` 还原为 `720`，`huggingface.lookback_days` 还原为 `14`
- 删除/注释新增的来源统计日志段
- 重新运行 `.venv/bin/python -m src.main` 确认恢复
