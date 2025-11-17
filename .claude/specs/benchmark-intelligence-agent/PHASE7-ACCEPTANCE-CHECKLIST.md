# Phase 7 验收测试清单

**角色分工**:
- **Codex**: 负责编码实现（根据CODEX-PHASE7-IMPLEMENTATION.md）
- **Claude Code**: 负责执行测试、验收、监督（根据本清单）

**文档关联**:
- PRD: `PHASE7-FOCUS-PRD.md`
- 开发指令: `CODEX-PHASE7-IMPLEMENTATION.md`

---

## 📋 交付物检查清单

Codex完成开发后，应交付以下文件：

### 核心代码文件

- [ ] `config/sources.yaml` - 数据源配置优化
- [ ] `src/collectors/helm_collector.py` - HELM任务过滤
- [ ] `src/collectors/github_collector.py` - GitHub Benchmark验证
- [ ] `src/prefilter/rule_filter.py` - 关键词相关性过滤
- [ ] `src/config.py` - 配置模型更新（HelmSettings新增字段）
- [ ] `src/scorer/llm_scorer.py` - Prompt优化（可选）

### 测试文件

- [ ] `tests/test_helm_collector.py` - HELM采集器单元测试
- [ ] `tests/test_github_collector.py` - GitHub采集器单元测试
- [ ] `tests/test_rule_filter.py` - 预筛选规则单元测试
- [ ] `scripts/test_phase7_pipeline.py` - 完整流程集成测试

### 文档文件

- [ ] `docs/phase7-test-report.md` - 测试报告（Codex填写）
- [ ] `docs/phase7-config-changes.md` - 配置变更说明
- [ ] `docs/phase7-manual-verification.csv` - 人工标注数据（100条样本）

---

## ✅ Claude Code验收步骤

### Step 1: 代码质量验收（15分钟）

**执行命令**:

```bash
# 1.1 代码格式检查
cd /mnt/d/VibeCoding_pgm/BenchScope
.venv/bin/python -m black --check .

# 1.2 代码风格检查
.venv/bin/python -m ruff check .

# 1.3 配置加载验证
.venv/bin/python -c "
from src.config import get_settings
settings = get_settings()
print('✅ arXiv keywords:', len(settings.sources.arxiv.keywords))
print('✅ GitHub topics:', len(settings.sources.github.topics))
print('✅ GitHub min_stars:', settings.sources.github.min_stars)
print('✅ HELM allowed:', len(settings.sources.helm.allowed_scenarios))
print('✅ HELM excluded:', len(settings.sources.helm.excluded_scenarios))
assert len(settings.sources.arxiv.keywords) >= 12, 'arXiv关键词不足12个'
assert len(settings.sources.github.topics) >= 12, 'GitHub topics不足12个'
assert settings.sources.github.min_stars >= 50, 'GitHub min_stars未提升到50'
assert len(settings.sources.helm.allowed_scenarios) >= 10, 'HELM allowed场景不足10个'
print('\n✅ 配置验证通过')
"
```

**验收标准**:
- [ ] black检查无格式问题
- [ ] ruff检查无风格错误
- [ ] 配置加载断言全部通过

---

### Step 2: 单元测试验收（30分钟）

**执行命令**:

```bash
# 2.1 运行所有单元测试
.venv/bin/python -m pytest tests/test_helm_collector.py -v
.venv/bin/python -m pytest tests/test_github_collector.py -v
.venv/bin/python -m pytest tests/test_rule_filter.py -v

# 2.2 测试覆盖率检查（可选）
.venv/bin/python -m pytest tests/ --cov=src/collectors --cov=src/prefilter --cov-report=term
```

**验收标准**:
- [ ] HELM采集器测试: ≥5个测试用例全部通过
- [ ] GitHub采集器测试: ≥4个测试用例全部通过
- [ ] 预筛选规则测试: ≥5个测试用例全部通过
- [ ] 新增代码覆盖率: ≥80%

---

### Step 3: 集成测试验收（60分钟）

**执行命令**:

```bash
# 3.1 运行完整流程测试（采样10条）
.venv/bin/python scripts/test_phase7_pipeline.py

# 记录输出到日志
.venv/bin/python scripts/test_phase7_pipeline.py > logs/phase7_integration_test.log 2>&1
```

**验收标准**（查看日志输出）:

**采集层过滤**:
- [ ] HELM采集数: ≤20条（目标≤15，允许浮动）
- [ ] GitHub采集数: ≥5条（确保未过度过滤）
- [ ] arXiv采集数: ≥1条
- [ ] HuggingFace采集数: ≥10条

**预筛选层过滤**:
- [ ] 关键词过滤率: 20-50%
- [ ] 日志中有"过滤候选（排除关键词: XXX）"的详细记录
- [ ] 日志中有"保留候选"的正向记录

**评分结果**（采样10条）:
- [ ] 平均总分: ≥6.0（目标6.5，允许浮动）
- [ ] 平均相关性: ≥5.0（目标6.0）
- [ ] 高优先级占比: ≥10%（目标20%，采样10条时≥1条）

---

### Step 4: 完整流程验收（3次运行，180分钟）

**执行命令**:

```bash
# 4.1 第一次完整运行
.venv/bin/python src/main.py

# 记录关键指标（从日志中提取）
# - 采集总数
# - 高优先级数量
# - 平均评分
# - HELM采集数

# 4.2 第二次完整运行（间隔2小时，确保不是缓存）
sleep 7200
.venv/bin/python src/main.py

# 4.3 第三次完整运行（间隔2小时）
sleep 7200
.venv/bin/python src/main.py
```

**填写性能数据表**:

| 指标 | Run 1 | Run 2 | Run 3 | 平均值 | 目标 | 达标 |
|------|-------|-------|-------|--------|------|------|
| 采集总数 | | | | | 40-60 | |
| 高优先级数量 | | | | | ≥8 | |
| 高优先级命中率 | | | | | ≥20% | |
| 平均评分 | | | | | ≥6.5 | |
| HELM采集数 | | | | | ≤15 | |
| 预筛选过滤率 | | | | | 30-60% | |

**验收标准**（3次平均值）:
- [ ] 采集总数: 40-60条
- [ ] 高优先级命中率: ≥20%
- [ ] 平均评分: ≥6.5
- [ ] HELM采集数: ≤15条

---

### Step 5: 人工验收（120分钟）

**执行步骤**:

1. **抽样100条候选**（从飞书多维表格或SQLite）

```bash
# 从SQLite导出最新100条
.venv/bin/python -c "
import sqlite3
import csv

conn = sqlite3.connect('fallback.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT title, source, url, abstract
    FROM candidates
    ORDER BY created_at DESC
    LIMIT 100
''')

rows = cursor.fetchall()

with open('docs/phase7-manual-verification.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['候选标题', '来源', 'URL', '摘要', '是否相关(0/1)', '场景分类'])
    for row in rows:
        writer.writerow(list(row) + ['', ''])

print('✅ 已导出100条候选到 docs/phase7-manual-verification.csv')
print('请手动标注"是否相关"和"场景分类"列')
"
```

2. **人工标注**（逐条判断）

打开 `docs/phase7-manual-verification.csv`，填写：
- `是否相关(0/1)`: 0表示无关，1表示相关（与MGX场景）
- `场景分类`: coding / web / gui / agent / 推理 / 无关

3. **计算相关性占比**

```bash
.venv/bin/python -c "
import csv

with open('docs/phase7-manual-verification.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

    relevant = sum(1 for r in rows if r['是否相关(0/1)'] == '1')
    total = len(rows)

    # 场景分布
    from collections import Counter
    categories = [r['场景分类'] for r in rows if r['是否相关(0/1)'] == '1']
    category_counter = Counter(categories)

    print(f'相关候选: {relevant}/{total} = {relevant/total*100:.1f}%')
    print(f'\n场景分布:')
    for cat, count in category_counter.most_common():
        print(f'  {cat}: {count}条 ({count/relevant*100:.1f}%)')

    print(f'\n目标: ≥60%')
    print(f'达标: {"✅" if relevant/total >= 0.6 else "❌"}')
"
```

**验收标准**:
- [ ] 相关候选占比: ≥60%
- [ ] coding场景: ≥20条
- [ ] web场景: ≥10条
- [ ] coding+web+gui+agent总和: ≥40条

---

### Step 6: 回归测试验收（30分钟）

**验证现有功能未破坏**:

```bash
# 6.1 飞书存储测试
.venv/bin/python -c "
from src.storage import FeishuStorage
from src.models import ScoredCandidate

storage = FeishuStorage()

# 创建测试候选
test_candidate = ScoredCandidate(
    title='Phase 7回归测试',
    url='https://test.example.com/phase7',
    source='Test',
    abstract='Phase 7回归测试候选',
    activity_score=8.0,
    reproducibility_score=9.0,
    license_score=10.0,
    novelty_score=7.0,
    relevance_score=8.0,
    reasoning='回归测试'
)

# 写入飞书
success = storage.write_batch([test_candidate])
print(f'飞书存储测试: {"✅ 通过" if success else "❌ 失败"}')
"

# 6.2 飞书通知测试
.venv/bin/python scripts/test_layered_notification.py
```

**验收标准**:
- [ ] 飞书存储功能正常
- [ ] 飞书通知功能正常
- [ ] 无新增异常或错误日志

---

## 📊 最终验收报告

Codex完成开发并自测后，应填写 `docs/phase7-test-report.md`（模板见CODEX-PHASE7-IMPLEMENTATION.md）。

Claude Code审核报告并执行上述6个步骤的验收，最终判断：

### ✅ 验收通过标准

**必须满足以下所有条件**:

1. **代码质量**: black/ruff检查通过
2. **单元测试**: 所有测试用例通过，覆盖率≥80%
3. **集成测试**: 采样10条测试通过
4. **完整流程**: 3次运行平均值达标（命中率≥20%，平均分≥6.5，HELM≤15条）
5. **人工验收**: 相关候选占比≥60%
6. **回归测试**: 现有功能未破坏

### ⚠️ 需调优情况

**如果以下任一条件不满足，需要调优**:

- 高优先级命中率: 10-20%（未达20%但有改善）
- 平均评分: 6.0-6.5（未达6.5但有提升）
- 相关候选占比: 50-60%（未达60%但有改善）

**调优方向**:
1. 放宽关键词白名单（增加边缘关键词）
2. 收紧关键词黑名单（减少误杀）
3. 调整HELM allowed/excluded场景列表
4. 优化LLM Prompt（更明确的场景分级）

### ❌ 验收失败情况

**如果以下任一条件出现，验收失败需返工**:

- 采集总数: >100条或<20条（过度采集或过度过滤）
- 高优先级命中率: <10%（优化无效）
- 平均评分: <6.0（评分下降）
- 相关候选占比: <50%（过滤失效）
- 单元测试: >20%测试用例失败
- 回归测试: 现有功能破坏

---

## 🚀 验收通过后上线流程

1. **Codex提交代码**

```bash
git add .
git commit -m "feat(phase7): MGX场景聚焦优化

- 数据源关键词聚焦（arXiv 12个/GitHub 12个）
- HELM任务过滤（11个允许/14个排除）
- GitHub Benchmark验证（README内容分析）
- 预筛选关键词过滤（20个必需/17个排除）

性能提升:
- 采集精准度: 3.5% → XX%
- 平均评分: 5.86 → X.XX
- coding/web占比: <20% → XX%
- HELM采集数: 59 → XX

测试:
- 单元测试: 14/14通过
- 集成测试: 3/3次达标
- 人工验收: XX/100相关(XX%)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

2. **Claude Code审核并推送**

```bash
# 审核commit message和代码
git log -1 --stat
git diff HEAD~1

# 推送到GitHub
git push origin main
```

3. **监控GitHub Actions运行**

- 查看Actions日志确认无错误
- 验证飞书通知是否正常推送
- 检查飞书多维表格数据质量

4. **持续监控（7天）**

- 每日查看日志文件
- 每日查看飞书推送质量
- 收集用户反馈

5. **Phase 7完成总结**

编写 `.claude/specs/benchmark-intelligence-agent/PHASE7-COMPLETION-SUMMARY.md`

---

**文档结束**
**祝开发顺利！**
