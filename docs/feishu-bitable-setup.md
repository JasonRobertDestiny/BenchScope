# 飞书多维表格配置指南

## 问题诊断

**错误现象**: 飞书API返回错误码91402 (NOTEXIST)

**根本原因**: 当前使用的是**飞书Wiki内嵌表格**，不是**独立多维表格(Bitable)**

飞书有3种表格产品：
1. **Wiki内嵌表格** (URL路径 `/wiki/`) - ❌ 不支持OpenAPI
2. **独立多维表格Bitable** (URL路径 `/base/`) - ✅ 支持OpenAPI
3. **云文档表格** - ❌ 不支持OpenAPI

当前URL (旧Wiki表格): `https://jcnqgpxcjdms.feishu.cn/wiki/NJkswt2hKi1pW0kCsdSccIoanmf?table=tbl53JhkakSOP4wo`
- 路径是 `/wiki/` → 这是Wiki表格，无法通过API访问

**已修正为独立Bitable**: `https://deepwisdom.feishu.cn/base/SbIibGBIWayQncslz5kcYMnrnGf?table=tblG5cMwubU6AJcV&view=vewUfT4GO6`
- 路径是 `/base/` → 独立Bitable，可通过API访问 ✅

需要: `https://xxx.feishu.cn/base/{app_token}?table={table_id}`
- 路径是 `/base/` → 独立Bitable，可通过API访问

---

## 解决方案

### 选项1: 创建新的独立多维表格 (推荐)

#### 步骤1: 创建Bitable

1. 打开飞书客户端
2. 点击左侧菜单 **"多维表格"** (不是"云文档"或"Wiki")
3. 点击 **"新建多维表格"**
4. 创建一个名为 "BenchScope候选池" 的表格

#### 步骤2: 配置表格字段

在新建的表格中，添加以下13个字段（必须与代码字段映射一致）：

| 字段名 | 字段类型 | 说明 |
|--------|----------|------|
| 标题 | 多行文本 | Benchmark标题 |
| 来源 | 单选 | arxiv/github/pwc/huggingface |
| URL | URL | 原始链接 |
| 摘要 | 多行文本 | 简介/描述 |
| 活跃度 | 数字 | 评分0-10 |
| 可复现性 | 数字 | 评分0-10 |
| 许可合规 | 数字 | 评分0-10 |
| 任务新颖性 | 数字 | 评分0-10 |
| MGX适配度 | 数字 | 评分0-10 |
| 总分 | 数字 | 加权总分 |
| 优先级 | 单选 | high/medium/low |
| 评分依据 | 多行文本 | LLM推理过程 |
| 状态 | 单选 | pending/approved/rejected |

**字段创建Tips**:
- 数字字段：设置小数位数=1
- 单选字段：手动添加选项
- 确保字段名**完全一致**（中文，区分大小写）

#### 步骤3: 获取app_token和table_id

1. 在浏览器中打开刚创建的Bitable
2. 复制浏览器地址栏URL，格式应该是：
   ```
   https://xxx.feishu.cn/base/NJkswt2hKi1pW0kCsdSccIoanmf?table=tbl53JhkakSOP4wo
   ```
3. 提取参数：
   - `app_token`: URL中 `/base/` 后面的字符串 (NJkswt2hKi1pW0kCsdSccIoanmf)
   - `table_id`: `?table=` 后面的字符串 (tbl53JhkakSOP4wo)

#### 步骤4: 配置应用权限

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 找到你的应用 (APP_ID: cli_a99fe5757cbc101c)
3. 进入 **"权限管理"** → **"权限配置"**
4. 搜索并开通以下权限：
   - `bitable:app` - 获取多维表格信息
   - `bitable:app:table` - 访问表格
   - `bitable:app:table:record` - 读写记录
5. 点击 **"发布版本"** 使权限生效

#### 步骤5: 更新.env.local

```bash
# 更新飞书多维表格配置
FEISHU_BITABLE_APP_TOKEN=NJkswt2hKi1pW0kCsdSccIoanmf  # 从步骤3提取
FEISHU_BITABLE_TABLE_ID=tbl53JhkakSOP4wo              # 从步骤3提取
```

#### 步骤6: 重新测试

```bash
source .venv/bin/activate
PYTHONPATH=. python tests/manual/test_feishu_credentials.py
```

**预期结果**:
```
✅ Access Token获取成功
✅ 飞书多维表格写入成功！
```

---

### 选项2: 仅使用SQLite存储 + 飞书Webhook通知

如果不需要飞书多维表格存储，可以：

1. **保持SQLite作为唯一存储**
   - 数据自动保存到 `fallback.db`
   - 7天后自动清理

2. **配置飞书Webhook通知**
   - 只需要 `FEISHU_WEBHOOK_URL`
   - 不需要 `FEISHU_BITABLE_APP_TOKEN` 和 `FEISHU_BITABLE_TABLE_ID`

3. **修改代码跳过飞书存储**
   - 在 `src/main.py` 中注释掉飞书存储逻辑
   - 仅保留SQLite存储

---

## 验证清单

完成配置后，执行以下验证：

- [ ] 创建了独立的Bitable多维表格（不是Wiki表格）
- [ ] 浏览器URL路径是 `/base/`（不是 `/wiki/`）
- [ ] 表格包含13个必需字段，字段名完全一致
- [ ] 飞书应用已开通 `bitable:*` 相关权限
- [ ] `.env.local` 中配置了正确的 `app_token` 和 `table_id`
- [ ] 运行测试脚本成功：`✅ 飞书多维表格写入成功`

---

## 常见错误

### 错误1: 91402 (NOTEXIST)
**原因**: app_token或table_id不正确，或应用没有权限
**解决**:
1. 确认URL路径是 `/base/`（不是 `/wiki/`）
2. 重新提取app_token和table_id
3. 检查应用权限

### 错误2: 1254039 (字段不存在)
**原因**: 表格字段名与代码映射不一致
**解决**: 检查13个字段名是否完全一致（中文，区分大小写）

### 错误3: 99991663 (权限不足)
**原因**: 应用缺少必需权限
**解决**: 开通 `bitable:*` 权限并发布版本

---

## 参考文档

- [飞书多维表格API文档](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create)
- [飞书权限管理](https://open.feishu.cn/document/home/introduction-to-scope-and-authorization/availability-of-permissions)
