# Repository Guidelines

## Project Structure & Module Organization
- `src/` 以功能域拆分：`collectors/`(多源采集器)、`prefilter/`、`scorer/`、`storage/`、`notifier/`、`tracker/`；公共常量放在 `src/common/constants.py`，数据模型位于 `src/models.py`。
- `config/` 存放 YAML 配置；`docs/` 用于 PRD、测试报告和样例；`scripts/` 提供辅助工具（日志分析、版本跟踪等）。
- 测试位于 `tests/unit` 与 `tests/integration`（如存在），夹具放在 `tests/fixtures`。

## Build, Test, and Development Commands
- `uv run python src/main.py`：执行完整采集→评分→存储→通知 pipeline。
- `PYTHONPATH=. uv run pytest tests/unit -m "not slow"`：运行快速单测；添加 `-k <name>` 可筛选模块。
- `poetry run python scripts/manual_review.py docs/samples/pwc.json`：执行强制手动审查以补充测试记录。
- `poetry run python src/collector/cli.py --source arxiv --dry-run`：快速验证单一采集链路。

## Coding Style & Naming Conventions
- Python 代码遵循 PEP 8、4 空格缩进，函数/变量用 `snake_case`，类用 `PascalCase`。
- 关键业务逻辑必须加中文注释；魔法数字统一放入 `src/common/constants.py`。
- 采集器/服务模块尽量单一职责，最大嵌套不超过 3 层；新增脚本放入 `scripts/`，命名描述用途。

## Testing Guidelines
- 单测使用 `pytest` + `pytest-asyncio`，命名为 `test_<module>_<behavior>`；夹具遵循 `fixture_<intent>`。
- 缺少自动化覆盖的核心路径，需要在 `docs/test-report.md` 记录手动验证步骤与截图/日志链接。
- LLM 或外部 API 相关改动，至少提供一个模拟测试（monkeypatch HTTP 响应）以避免真实请求。

## Commit & Pull Request Guidelines
- 采用 Conventional Commits（如 `feat: add helm collector`、`fix: patch feishu mapping`），在 body 说明动机、实现与风险。
- PR 需包含：问题背景、变更摘要、运行命令、手动测试结果、关联 Issue/讨论链接；涉及飞书卡片或 UI 需附截图/录屏。
- 推送前确保 `pytest`、`ruff check`、`black .`（或项目等效格式化工具）已通过，并在 PR 描述列出执行结果。

## Security & Configuration Tips
- 所有密钥放入 `.env.local` 或托管密钥管理器，配置文件仅引用变量名；严禁提交明文凭证。
- 飞书、多源 API 受速率限制，跑批前确认 `.env.local` 中 `OPENAI_*`、`FEISHU_*`、`SEMANTIC_SCHOLAR_API_KEY` 等必填字段存在。
- 采集器遵守目标站点 robots/使用条款；若需白名单例外，更新 `config/whitelist.yaml` 并记录审批依据。
