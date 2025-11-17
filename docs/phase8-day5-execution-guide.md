# Phase 8 Day 5 验证执行指南

**执行时间**: 预计30-60分钟
**目标**: 验证PDF增强功能，获取真实数据质量对比

---

## 快速执行（推荐）

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
bash scripts/phase8_day5_validation.sh
```

脚本会自动执行所有步骤并生成日志文件。

---

## 手动执行（详细控制）

### Step 0: 环境准备

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
source .venv/bin/activate

# 验证关键依赖
python -c "from src.enhancer import PDFEnhancer; print('✅ PDFEnhancer')"
python -c "from scipdf.pdf import parse_pdf_to_dict; print('✅ scipdf_parser')"
```

### Step 1: 启动GROBID服务（二选一）

**选项A: Docker本地部署（推荐）**
```bash
# 另开一个终端窗口
docker run -t --rm -p 8070:8070 grobid/grobid:0.8.0

# 验证服务
curl http://localhost:8070/api/version
```

**选项B: 使用云端GROBID（无需Docker）**
```bash
export GROBID_URL=https://kermitt2-grobid.hf.space
```

### Step 2: 运行单元测试

```bash
python -m pytest tests/test_pdf_enhancer.py -v
```

**预期结果**: 4/4 PASSED

如果失败：
- `test_enhance_arxiv_candidate` 失败 → 检查GROBID服务
- 其他失败 → 检查网络连接和依赖安装

### Step 3: 运行完整流程（核心步骤）

```bash
# 创建日志目录
mkdir -p logs exports

# 运行主流程（约10-30分钟）
python -m src.main 2>&1 | tee logs/phase8_validation_$(date +%Y%m%d_%H%M%S).log
```

**关键日志观察点**:

```
[1/6] 数据采集...
✓ 采集完成: XX条

[2/6] 规则预筛选...
✓ 预筛选完成: XX条 (过滤率XX%)

[3/6] PDF内容增强...          ← ✅ 新步骤！关注arXiv候选数
✓ PDF增强完成: XX条候选 (其中arXiv XX条)

[4/6] LLM评分...
✓ 评分完成: XX条

[5/6] 存储入库...
✓ 存储完成

[6/6] 飞书通知...
✓ 飞书通知完成
```

**预期输出**:
- arXiv候选数 > 0（有PDF需要增强）
- PDF增强成功（没有大量ERROR）
- 飞书写入成功

### Step 4: 数据质量分析

```bash
python scripts/analyze_data_quality.py 2>&1 | tee logs/phase8_data_quality_$(date +%Y%m%d_%H%M%S).log
```

**关键指标**（记录到报告）:

| 字段 | Phase 7基线 | Phase 8实测 | 改进 |
|------|------------|------------|------|
| 摘要长度（平均） | <100字 | `[记录]` | `[计算]` |
| 摘要（<100字占比） | 91.4% | `[记录]` | `[计算]` |
| 评估指标覆盖率 | 18.7% | `[记录]` | `[计算]` |
| 基准模型覆盖率 | 17.2% | `[记录]` | `[计算]` |
| 数据集规模覆盖率 | 5.3% | `[记录]` | `[计算]` |
| 机构覆盖率 | 0.5% | `[记录]` | `[计算]` |

### Step 5: 飞书表格验证

1. 打开飞书表格:
   ```
   https://deepwisdom.feishu.cn/base/SbIibGBIWayQncslz5kcYMnrnGf?table=tblG5cMwubU6AJcV&view=vewUfT4GO6
   ```

2. 筛选最新记录（按创建时间排序）

3. 检查以下字段:
   - ✅ 摘要长度 > 500字
   - ✅ 评估指标有内容
   - ✅ 基准模型有内容
   - ✅ 机构信息有内容
   - ✅ 数据集规模有内容

4. 截图保存典型案例（2-3个）

---

## 常见问题处理

### Q1: GROBID连接失败
```
ERROR: HTTPConnectionPool(host='localhost', port=8070): Connection refused
```

**解决**:
1. 确认Docker容器运行: `docker ps | grep grobid`
2. 或使用云端GROBID: `export GROBID_URL=https://kermitt2-grobid.hf.space`

### Q2: arXiv下载很慢
**正常现象**: 有0.5s sleep限流保护，避免触发arXiv限制

### Q3: PDF解析全部失败
**检查**:
1. GROBID服务是否正常
2. 网络连接是否稳定
3. 查看详细错误日志

### Q4: LLM评分失败
```
ERROR: OpenAI API error
```

**解决**:
1. 检查 `.env.local` 中 `OPENAI_API_KEY`
2. 检查API余额
3. 检查网络代理设置

### Q5: 飞书写入失败
```
ERROR: Feishu API error 99991503
```

**解决**:
1. 检查 `.env.local` 中飞书配置
2. 检查app_token和table_id是否正确
3. 查看SQLite降级备份: `fallback.db`

---

## 验证完成后

### 1. 收集验证产物

```bash
# 创建验证产物目录
mkdir -p exports/phase8_validation_$(date +%Y%m%d)

# 复制日志文件
cp logs/phase8_validation_*.log exports/phase8_validation_$(date +%Y%m%d)/
cp logs/phase8_data_quality_*.log exports/phase8_validation_$(date +%Y%m%d)/

# 导出飞书数据（可选）
# 在飞书表格中导出CSV，保存到exports目录
```

### 2. 填写验收报告

编辑 `docs/phase8-pdf-enhancement-report.md`，填写所有 `_TODO_` 项:

**关键章节**:
- **4.2 数据质量对比**: 填写Phase 7 vs Phase 8对比表
- **4.3 典型案例分析**: 选取2-3个代表性案例
- **6.1 性能表现**: 填写PDF处理时间、完整流程耗时
- **6.2 LLM成本**: 填写Token数和成本估算
- **8.2 数据质量提升**: 总结改进幅度
- **9. 操作记录**: 记录实际执行的命令和时间

### 3. 发送数据给Claude Code

将以下文件/信息发送给我：

```
1. 主流程日志: logs/phase8_validation_YYYYMMDD_HHMMSS.log
2. 数据质量报告: logs/phase8_data_quality_YYYYMMDD_HHMMSS.log
3. 典型案例截图: 2-3个飞书表格记录截图
4. 关键指标摘要:
   - 总候选数: XX条
   - arXiv候选数: XX条
   - PDF增强成功数: XX条
   - PDF增强失败数: XX条
   - 平均摘要长度: XX字
   - 评估指标覆盖率: XX%
   - 基准模型覆盖率: XX%
   - 机构覆盖率: XX%
```

**我可以帮你**:
- 解析日志提取性能数据
- 计算改进幅度百分比
- 生成对比图表
- 填充报告所有TODO项
- 撰写验收结论

---

## 预期时间分配

| 步骤 | 时间 | 备注 |
|------|------|------|
| 环境准备 | 5分钟 | 启动GROBID、检查依赖 |
| 单元测试 | 3分钟 | 4个测试用例 |
| 完整流程 | 15-30分钟 | 取决于采集量和PDF数量 |
| 数据分析 | 2分钟 | 自动统计 |
| 飞书验证 | 5分钟 | 手动检查和截图 |
| **总计** | **30-45分钟** | 不含报告填写 |

---

## 开始执行！

**推荐命令**:
```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
bash scripts/phase8_day5_validation.sh
```

执行过程中有任何问题，随时告诉我！

🚀 祝验证顺利！
