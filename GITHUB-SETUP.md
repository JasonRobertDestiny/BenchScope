# GitHub仓库创建与部署指南

## 第一步：本地测试验证 (预计10分钟)

### 1.1 启动Redis
```bash
# 方式1: Docker运行 (推荐)
docker run -d --name benchscope-redis -p 6379:6379 redis:7-alpine

# 方式2: 本地安装
# Windows/WSL2:
sudo apt install redis-server && redis-server

# macOS:
brew install redis && brew services start redis

# 验证:
redis-cli ping
# 应返回 PONG
```

### 1.2 安装Python依赖
```bash
cd /mnt/d/VibeCoding_pgm/BenchScope
pip install -r requirements.txt
```

### 1.3 验证配置
```bash
python -c "from src.config import get_settings; get_settings(); print('✓ 配置验证通过')"
```

### 1.4 运行单元测试
```bash
python -m pytest tests/unit -v
```

### 1.5 测试完整流程 (约5-10分钟)
```bash
python -m src.main
```

**预期输出**：
- ✓ 采集arXiv/GitHub/PwC数据
- ✓ LLM评分成功（或降级到规则评分）
- ✓ 写入飞书多维表格
- ✓ 飞书群收到通知

**验证清单**：
- [ ] 飞书多维表格中有新数据
- [ ] 飞书群收到Top 5候选通知
- [ ] 日志文件生成在 `logs/` 目录
- [ ] SQLite降级备份文件生成（如果飞书API失败）

---

## 第二步：创建GitHub仓库 (3分钟)

### 2.1 在GitHub创建新仓库
1. 访问 https://github.com/new
2. 仓库名称: `BenchScope`
3. 描述: `AI Benchmark Intelligence Agent - Daily automated collection and scoring of AI benchmarks`
4. 可见性: **Private** (推荐) 或 Public
5. ⚠️ **不要**初始化README/gitignore/license（本地已有）
6. 点击 **Create repository**

### 2.2 关联远程仓库
```bash
cd /mnt/d/VibeCoding_pgm/BenchScope

# 初始化Git（如果还没有）
git init

# 关联远程仓库（替换YOUR_USERNAME为你的GitHub用户名）
git remote add origin https://github.com/YOUR_USERNAME/BenchScope.git

# 或使用SSH（推荐）
git remote add origin git@github.com:YOUR_USERNAME/BenchScope.git

# 验证
git remote -v
```

---

## 第三步：配置GitHub Secrets (5分钟)

在GitHub仓库页面：**Settings → Secrets and variables → Actions → New repository secret**

添加以下Secrets（一个个添加）：

| Name | Value |
|------|-------|
| `OPENAI_API_KEY` | `sk-hJOSKKNm1TJTRpgrUIrOSA0YlAKJxDMV9JMxSp91qxzHQuej` |
| `OPENAI_BASE_URL` | `https://newapi.deepwisdom.ai/v1` |
| `OPENAI_MODEL` | `gpt-4o` |
| `FEISHU_APP_ID` | `cli_a99fe5757cbc101c` |
| `FEISHU_APP_SECRET` | `O3MyjhEzvfEYw0TM8y1zsbb8NWihxGQe` |
| `FEISHU_BITABLE_APP_TOKEN` | `NJkswt2hKi1pW0kCsdSccIoanmf` |
| `FEISHU_BITABLE_TABLE_ID` | `tbl53JhkakSOP4wo` |
| `FEISHU_WEBHOOK_URL` | `https://open.feishu.cn/open-apis/bot/v2/hook/b9e072c7-f2a2-422c-81ed-0043eb437067` |

⚠️ **注意**：Secrets添加后不可查看，只能替换。请仔细检查拼写。

---

## 第四步：推送代码到GitHub (2分钟)

```bash
cd /mnt/d/VibeCoding_pgm/BenchScope

# 添加所有文件
git add .

# 创建首次提交
git commit -m "feat: complete BenchScope MVP implementation

- Multi-source data collection (arXiv, GitHub, PwC)
- LLM-based 5-dimension scoring with gpt-4o
- Feishu Bitable storage with SQLite fallback
- Automated daily notification via Feishu webhook
- Redis caching for cost optimization
- GitHub Actions automation workflow"

# 推送到GitHub (main分支)
git branch -M main
git push -u origin main
```

---

## 第五步：测试GitHub Actions (5分钟)

### 5.1 手动触发测试
1. 访问仓库页面：**Actions** 标签
2. 左侧选择 **"BenchScope Daily Collection"**
3. 点击右上角 **"Run workflow"** → **"Run workflow"**
4. 等待约5-10分钟

### 5.2 查看执行日志
- 点击运行中的workflow
- 展开各个步骤查看详细日志
- 重点检查：
  - ✓ Setup Python 和依赖安装
  - ✓ Run BenchScope Collection
  - ✓ 飞书API调用日志
  - ✓ 评分结果统计

### 5.3 验证结果
- [ ] 飞书多维表格有新数据
- [ ] 飞书群收到通知
- [ ] GitHub Actions显示 ✓ 绿色通过

---

## 第六步：自动化调度确认

GitHub Actions已配置为 **每天UTC 2:00 (北京时间10:00)** 自动运行。

查看 `.github/workflows/daily-collection.yml`:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # UTC 2:00 = 北京时间10:00
  workflow_dispatch:     # 允许手动触发
```

**下次自动运行时间**：明天北京时间10:00

---

## 故障排查

### 问题1: GitHub Actions失败 - Redis连接错误
**现象**: `ConnectionError: Error connecting to localhost:6379`
**原因**: GitHub Actions使用的是云端runner，没有本地Redis
**解决**: 已在workflow中配置Redis服务容器，检查 `.github/workflows/daily-collection.yml`:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
```

### 问题2: 飞书API错误 - app_access_token invalid
**现象**: Feishu API返回99991663错误
**解决**:
1. 检查GitHub Secrets中 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
2. 在飞书开放平台确认应用状态是否"已启用"
3. 检查应用权限是否包含"多维表格"读写

### 问题3: OpenAI API错误 - Invalid base URL
**现象**: OpenAI client初始化失败
**解决**:
1. 确认 `OPENAI_BASE_URL` = `https://newapi.deepwisdom.ai/v1` (注意末尾的 `/v1`)
2. 检查API密钥是否有效
3. 查看日志，确认是否正确回落到规则评分

### 问题4: 本地测试通过但GitHub Actions失败
**排查步骤**:
1. 检查GitHub Secrets是否全部配置
2. 对比本地 `.env.local` 和 GitHub Secrets 的值
3. 查看GitHub Actions日志中的环境变量加载部分
4. 确认 `src/config.py` 正确读取环境变量

---

## 成功标准

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| 数据采集成功率 | >95% | 查看日志统计 |
| LLM评分成功率 | >90% | 查看评分日志 |
| 飞书写入成功率 | 100% | 检查多维表格 |
| 飞书通知送达 | 100% | 检查群消息 |
| 执行时间 | <20分钟 | GitHub Actions时长 |
| 成本 | <¥5/天 | 查看OpenAI账单 |

---

## 下一步工作

完成上述部署后，可以考虑：

1. **监控优化**：
   - 配置GitHub Actions失败通知（邮件/Slack）
   - 添加Prometheus监控指标
   - 飞书错误告警机器人

2. **功能增强**：
   - 添加HuggingFace数据集监控
   - 实现Papers with Code排行榜变化追踪
   - 增加Twitter关键词监控

3. **性能优化**：
   - 并发采集（asyncio.gather优化）
   - 批量写入优化（目前20条/批）
   - Redis缓存策略调优

---

## 快速参考

```bash
# 本地测试
python -m src.main

# 查看日志
cat logs/$(date +%Y%m%d).log

# 检查Redis缓存
redis-cli keys "score:*"

# 查看SQLite降级备份
sqlite3 data/benchscope.db "SELECT COUNT(*) FROM candidates"

# 手动触发GitHub Actions
# 访问 https://github.com/YOUR_USERNAME/BenchScope/actions

# 查看飞书多维表格
# https://jcnqgpxcjdms.feishu.cn/wiki/NJkswt2hKi1pW0kCsdSccIoanmf?table=tbl53JhkakSOP4wo
```

---

**当前进度**: 100% 配置完成 | **下一步**: 本地测试 → GitHub部署 → 自动化运行 🚀
