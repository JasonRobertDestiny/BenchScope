# BenchScope 快速配置指南

## 当前状态 ✅

- [x] Codex已完成MVP开发
- [x] API Keys已配置（OpenAI, 飞书App）
- [x] .env.local已创建
- [x] 支持自定义OpenAI base_url

## 立即需要完成 ⚠️

### 1. 飞书多维表格配置 (5分钟)

#### Step 1: 创建多维表格
1. 打开飞书
2. 新建多维表格，命名为 **"Benchmark候选池"**
3. 添加以下字段（严格按照此顺序）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 标题 | 单行文本 | Benchmark标题 |
| 来源 | 单选 | arxiv / github / pwc |
| URL | 超链接 | 论文/仓库链接 |
| 摘要 | 多行文本 | 简介 |
| 创新性 | 数字 | 0-10分 |
| 技术深度 | 数字 | 0-10分 |
| 影响力 | 数字 | 0-10分 |
| 数据质量 | 数字 | 0-10分 |
| 可复现性 | 数字 | 0-10分 |
| 总分 | 数字 | 自动计算 |
| 优先级 | 单选 | high / medium / low |
| 状态 | 单选 | 待审阅 / 已添加 / 已拒绝 |
| 发现时间 | 日期 | 自动填充 |
| GitHub Stars | 数字 | 仓库star数 |
| GitHub URL | 超链接 | 代码仓库 |

#### Step 2: 获取app_token和table_id
1. 打开创建的多维表格
2. 查看URL，格式如：
   ```
   https://xxx.feishu.cn/base/bascnXXXXXXXXXXXX?table=tblXXXXXXXXXXXX
   ```
3. 提取：
   - `app_token`: `/base/` 后面的部分 (bascn开头)
   - `table_id`: `?table=` 后面的部分 (tbl开头)

4. 填入 `.env.local`:
   ```bash
   FEISHU_BITABLE_APP_TOKEN=bascnXXXXXXXXXXXX
   FEISHU_BITABLE_TABLE_ID=tblXXXXXXXXXXXX
   ```

### 2. 飞书机器人Webhook配置 (3分钟)

1. 在飞书群聊中，点击 **"设置" → "群机器人"**
2. 点击 **"添加机器人" → "自定义机器人"**
3. 机器人名称: **BenchScope播报**
4. 复制Webhook URL
5. 填入 `.env.local`:
   ```bash
   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx
   ```

### 3. 安装依赖并测试 (5分钟)

```bash
# 1. 安装Python依赖
cd /mnt/d/VibeCoding_pgm/BenchScope
pip install -r requirements.txt

# 2. 启动Redis (如果未启动)
docker run -d -p 6379:6379 redis:7-alpine
# 或
redis-server

# 3. 验证配置
python -c "from src.config import get_settings; s = get_settings(); print('✓ 配置加载成功')"

# 4. 运行单元测试
python -m pytest tests/unit -v

# 5. 运行完整流程 (测试模式)
python -m src.main
```

---

## 配置完成后的下一步

### 选项1: 本地测试运行
```bash
python -m src.main
```

### 选项2: 部署到GitHub Actions
1. 在GitHub仓库 Settings → Secrets 添加：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`
   - `FEISHU_APP_ID`
   - `FEISHU_APP_SECRET`
   - `FEISHU_BITABLE_APP_TOKEN`
   - `FEISHU_BITABLE_TABLE_ID`
   - `FEISHU_WEBHOOK_URL`

2. Push代码到GitHub:
   ```bash
   git add .
   git commit -m "feat: complete BenchScope MVP implementation"
   git push
   ```

3. 手动触发工作流测试:
   - GitHub → Actions → "BenchScope Daily Collection"
   - 点击 "Run workflow"

---

## 故障排查

### Redis连接失败
```bash
# 检查Redis是否运行
redis-cli ping
# 应返回 PONG

# 如未运行，启动Redis
docker run -d -p 6379:6379 redis:7-alpine
```

### 飞书API错误
```
Error: app_access_token invalid
```
**解决**: 检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET 是否正确

### OpenAI API错误
```
Error: Invalid base URL
```
**解决**: 确认 OPENAI_BASE_URL = https://newapi.deepwisdom.ai/v1

---

## 预期结果

配置完成后，系统将：
1. ✅ 每日UTC 2:00自动采集arXiv/GitHub/PwC
2. ✅ 使用gpt-4o智能评分
3. ✅ 自动写入飞书多维表格
4. ✅ 推送Top 5候选到飞书群
5. ✅ SQLite自动降级备份
6. ✅ 完整日志记录

---

## 当前配置状态

| 配置项 | 状态 | 说明 |
|--------|------|------|
| OpenAI API | ✅ 已配置 | gpt-4o, 自定义base_url |
| 飞书App | ✅ 已配置 | App ID + Secret |
| 飞书多维表格 | ⚠️ 待配置 | 需手动创建表格 |
| 飞书Webhook | ⚠️ 待配置 | 需添加机器人 |
| GitHub Token | ✅ 已配置 | 提高API限额 |
| Redis | ⚠️ 待启动 | 需本地运行 |

---

**下一步**: 完成飞书多维表格和Webhook配置后，立即可运行测试！ 🚀
