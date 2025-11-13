# Repository Guidelines

## Project Structure & Module Organization
- 现有根目录以战略文档为主（`PRD_FINAL.md`、`gemini.md`、调研 PDF）；源码统一放在 `src/`，并保持按领域拆分的子包结构。
- `src/collector` 负责多源抓取，`src/prefilter` 承担评分过滤，`src/notifier` 汇总播报；跨模块常量放入 `src/common/constants.py`。
- 配置集中在 `config/`（如 `config/sources.yaml`、`config/weights.yaml`），示例数据与设计稿放到 `docs/` 与 `docs/samples/`。
- 测试文件位于 `tests/`，按 `tests/unit` 与 `tests/integration` 分层，夹具保存在 `tests/fixtures`，保证可复现性。

## Build, Test, and Development Commands
- `poetry install`：初始化虚拟环境与依赖。
- `poetry run python src/collector/cli.py --source arxiv --dry-run`：快速验证单一数据源抓取链路。
- `poetry run python scripts/manual_review.py docs/samples/pwc.json`：执行强制性的手动审查脚本并记录输出。
- `poetry run pytest tests -m "not slow"`：运行自动化测试；未覆盖的路径需在 PR 描述中补充手动验证步骤。

## Coding Style & Naming Conventions
- Python 代码遵循 PEP8 与 4 空格缩进；函数与变量使用 `snake_case`，类名使用 `PascalCase`，环境变量为 `UPPER_SNAKE`。
- 关键业务逻辑必须写中文注释，单函数保持单一职责，最大嵌套层级 ≤3；出现的阈值、权重等“魔法数字”需定义在 `constants.py`。
- 数据模型与配置键名采用名词短语（如 `benchmark_score`、`source_priority`），文件名描述模块职能（示例：`prefilter/scoring_service.py`）。

## Testing Guidelines
- 仓库默认“修改前先运行手动测试”，尤其是飞书播报、Notion 入库、外部 API 交互等场景；结果需写入 `docs/test-report.md` 并附截图或日志路径。
- Pytest 用例命名 `test_<module>_<behavior>`，夹具命名 `fixture_<intent>`；关键路径需覆盖成功、失败与异常数据集。
- 若引入新评分维度，必须提供最小可复现脚本（放在 `scripts/`）和对应样例输入，便于评审触发。

## Commit & Pull Request Guidelines
- 当前无 git 历史，统一采用 Conventional Commits（如 `feat: add arxiv collector`、`chore: update config`），在 body 中交代动机、实现与风险。
- PR 模板需包含：问题背景、变更摘要、运行的命令、手动测试结果、相关 Issue/飞书讨论链接；涉及 UI 或飞书卡片的改动需附截图或录屏。
- SEO 模块专项约束：禁止修改 `analyzer.py` 第 12-89 行的 `is_quality_keyword()`；若确需变更，先提 Issue 并经负责人书面批准。

## Security & Configuration Tips
- 所有 API Token 与 Cookie 均放入 `.env.local` 或服务端密钥管理器，配置文件仅引用变量名，严禁提交明文凭证。
- NotebookLM/NotebookLLM 抓取任务必须遵守 robots.txt；如需白名单例外，将站点与理由记录在 `config/whitelist.yaml` 并同步合规审批记录。
- 数据落库、播报队列等持久化操作只允许通过封装的仓储层完成，避免脚本直接改写 Notion/Airtable。
