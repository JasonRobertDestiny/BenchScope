# Phase 7 Test Report

- 日期: 2025-11-14
- 阶段: Phase 7.2 - 飞书集成与测试补充

## 覆盖范围

1. 飞书多维表字段脚本 (`scripts/check_feishu_fields.py`, `scripts/create_feishu_fields_v2.py`)
2. 三域评分写入/通知改造 (`src/storage/feishu_storage.py`, `src/notifier/feishu_notifier.py`)
3. 数据模型与评分器回归 (`src/models.py`, `src/scorer/llm_scorer.py`)
4. SQLite 备份兼容性 (`src/storage/sqlite_fallback.py`)

## 自动化测试

| 序号 | 命令 | 结果 |
|------|------|------|
| 1 | `pytest tests/test_scorer.py tests/test_models.py tests/test_sqlite_fallback.py` | ✅ 通过 |
| 2 | `python3 -m compileall src/models.py src/scorer/llm_scorer.py src/storage/feishu_storage.py` | ✅ 通过 |

## 手动/半自动验证

1. **飞书字段自检**：使用 `PYTHONPATH=. uv run python scripts/check_feishu_fields.py` 列出字段，确认 14 个三域字段已存在；若缺失可执行 `scripts/create_feishu_fields_v2.py` 进行补齐。
2. **飞书写入验证**：在具备真实凭证的环境运行 `uv run python src/main.py`，检查多维表是否出现 `planning_score`、`risk_total`、`risk_level` 等字段以及对应数值、风险等级单选。
3. **通知体验**：通过 `PYTHONPATH=. uv run python scripts/test_layered_notification.py --dry-run` 校验卡片 Markdown；正式环境需使用测试 Webhook 观察三域段落与风险徽标是否正常显示。

> 注：当前测试环境无法访问真实飞书租户，以上步骤 1-3 需在具备凭证的运行机执行并截图存档。

## 已知风险 / 待补充

- 飞书单选字段 `risk_level` 的选项需与 `scripts/create_feishu_fields_v2.py` 定义保持一致，否则写入会失败。
- 仍需在 Phase 7.3 中补充安全验证器与自进化样本池的端到端测试。
