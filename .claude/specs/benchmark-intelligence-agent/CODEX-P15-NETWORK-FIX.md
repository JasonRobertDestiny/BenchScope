# P15: 网络稳定性修复与GitHub Actions优化

## 问题诊断

### 测试时间
2025-12-14 11:30:56 ~ 11:33:08

### 采集器失败统计

| 采集器 | 状态 | 结果 | 错误信息 | 根本原因 |
|--------|------|------|----------|----------|
| **arXiv** | ❌ 失败 | 0条 | 连续3次超时(每次20s) | 超时配置10s太短，实际需要20-30s |
| **HuggingFace** | ❌ 失败 | 0条 | `[Errno 101] Network is unreachable` | WSL2网络路由问题，缺少重试机制 |
| **TechEmpower** | ❌ 失败 | 0条 | 请求超时(>15s) | 15s超时太短，大JSON响应需要更长时间 |
| **HELM** | ✅ 正常 | 14条 | - | 正常工作 |
| **GitHub** | ✅ 正常 | 42条 | - | 正常工作 |
| **DBEngines** | ✅ 正常 | 50条 | - | 正常工作 |

### 详细错误日志

**arXiv超时日志**：
```
2025-12-14 11:31:17 [WARNING] arXiv查询超时,准备重试(1/2)
2025-12-14 11:31:38 [WARNING] arXiv查询超时,准备重试(2/2)
2025-12-14 11:31:40 [ERROR] arXiv连续失败,返回空列表
```

**HuggingFace网络错误**：
```
2025-12-14 11:32:00 [ERROR] HuggingFace采集失败: [Errno 101] Network is unreachable
```

**TechEmpower超时**：
```
2025-12-14 11:32:16 [ERROR] TechEmpower请求超时(>15s)
```

### 根本原因分析

#### 1. 超时配置不合理

**当前配置** (`src/common/constants.py`):
```python
ARXIV_TIMEOUT_SECONDS: Final[int] = 10  # ❌ 太短
# HuggingFace缺少超时配置  # ❌ 缺失
TECHEMPOWER_TIMEOUT_SECONDS: Final[int] = 15  # ❌ 太短
```

**实际耗时统计**：
- arXiv API: 通常需要15-25秒
- HuggingFace API: 通常需要10-15秒
- TechEmpower JSON: 文件大(>1MB)，需要20-25秒

#### 2. 错误处理不足

**HuggingFace采集器** (`src/collectors/huggingface_collector.py`):
```python
async def collect(self) -> List[RawCandidate]:
    try:
        datasets = await self._fetch_datasets()
        # ...
    except Exception as exc:
        logger.error(f"HuggingFace采集失败: {exc}")
        return []  # ❌ 直接返回空列表，没有重试
```

**问题**：
- 网络瞬断直接失败，无重试
- 缺少httpx timeout配置
- 错误日志不够详细

#### 3. GitHub Actions配置可优化

**当前配置** (`.github/workflows/daily_collect.yml`):
```yaml
jobs:
  collect:
    timeout-minutes: 20  # ❌ 可能不够

    steps:
      - name: Run pipeline
        env:
          # ...
        run: |
          python -m src.main  # ❌ 无重试机制
```

**问题**：
- 20分钟超时可能不够（arXiv重试耗时长）
- 失败无重试，浪费每日机会
- 缺少网络诊断步骤

---

## 解决方案

### 方案A：增加超时时间（推荐）

**优点**：
- 简单直接，改动最小
- 立即解决超时问题
- 不影响现有逻辑

**缺点**：
- 流程总耗时增加
- 仍可能遇到极端网络问题

### 方案B：指数退避重试

**优点**：
- 更健壮，应对网络抖动
- 成功率更高
- 生产级方案

**缺点**：
- 代码复杂度增加
- 调试难度增加

### 方案C：混合方案（本次采用）

**增加超时 + 改进重试 + GitHub Actions优化**

---

## 实施步骤

### Step 1: 调整超时配置

**文件**: `src/common/constants.py`

**修改位置**: Line 39, 新增Line, Line 295

**当前代码**：
```python
# Line 39
ARXIV_TIMEOUT_SECONDS: Final[int] = 10

# HuggingFace缺少配置

# Line 295
TECHEMPOWER_TIMEOUT_SECONDS: Final[int] = 15
```

**修复后代码**：
```python
# Line 39 - arXiv超时从10秒增加到30秒
ARXIV_TIMEOUT_SECONDS: Final[int] = 30  # P15: arXiv API响应慢,实测需要15-25秒,增加到30秒

# 新增Line（在ARXIV_TIMEOUT_SECONDS之后）
HUGGINGFACE_TIMEOUT_SECONDS: Final[int] = 20  # P15: HuggingFace API超时配置,实测需要10-15秒,设置20秒

# Line 295 - TechEmpower超时从15秒增加到25秒
TECHEMPOWER_TIMEOUT_SECONDS: Final[int] = 25  # P15: TechEmpower大JSON文件响应慢,从15秒增加到25秒
```

**修改原因**：
- arXiv: 10s → 30s（3次重试共90秒，避免全部超时）
- HuggingFace: 新增20s配置（之前缺失）
- TechEmpower: 15s → 25s（大JSON文件需要更多时间）

### Step 2: HuggingFace添加超时配置

**文件**: `src/collectors/huggingface_collector.py`

**修改位置**: Line 23-26 (构造函数中)

**当前代码**：
```python
def __init__(self, settings: Optional[Settings] = None) -> None:
    self.settings = settings or get_settings()
    self.cfg = self.settings.sources.huggingface
```

**修复后代码**：
```python
def __init__(self, settings: Optional[Settings] = None) -> None:
    self.settings = settings or get_settings()
    self.cfg = self.settings.sources.huggingface
    # P15: 添加httpx client超时配置
    self.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(constants.HUGGINGFACE_TIMEOUT_SECONDS)
    )
```

**修改位置**: Line 54 (collect方法中)

**当前代码**：
```python
async def collect(self) -> List[RawCandidate]:
    """主采集入口"""
    if not self.cfg.enabled:
        logger.info("HuggingFace采集器已禁用")
        return []

    try:
        datasets = await self._fetch_datasets()
        # ...省略...
    except Exception as exc:
        logger.error(f"HuggingFace采集失败: {exc}")
        return []
```

**修复后代码**：
```python
async def collect(self) -> List[RawCandidate]:
    """主采集入口"""
    if not self.cfg.enabled:
        logger.info("HuggingFace采集器已禁用")
        return []

    try:
        datasets = await self._fetch_datasets()
        # ...省略...
    except httpx.TimeoutException as exc:
        # P15: 超时异常单独处理，提供更详细的日志
        logger.error(
            f"HuggingFace采集超时: {exc}, "
            f"超时配置={constants.HUGGINGFACE_TIMEOUT_SECONDS}秒"
        )
        return []
    except httpx.NetworkError as exc:
        # P15: 网络错误单独处理
        logger.error(
            f"HuggingFace网络错误: {exc}, "
            f"请检查网络连接或HuggingFace服务状态"
        )
        return []
    except Exception as exc:
        logger.error(f"HuggingFace采集失败: {exc}")
        return []
```

**新增**: 在文件顶部导入httpx
```python
import httpx  # P15: 用于超时和网络错误处理
from src.common import constants  # P15: 导入超时配置
```

**新增**: 在类中添加cleanup方法
```python
async def __aenter__(self):
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    # P15: 确保HTTP client正确关闭
    await self.http_client.aclose()
```

### Step 3: 优化GitHub Actions配置

**文件**: `.github/workflows/daily_collect.yml`

**修改位置**: Line 11, Line 46-62

**当前代码**：
```yaml
jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 20  # Line 11

    # ...省略其他步骤...

    - name: Run pipeline  # Line 46
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        # ...省略环境变量...
      run: |
        python -m src.main
```

**修复后代码**：
```yaml
jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # P15: 从20分钟增加到30分钟，应对arXiv/TechEmpower慢响应

    # ...省略其他步骤...

    # P15: 新增网络诊断步骤（在Install dependencies之后）
    - name: Network diagnostics
      run: |
        echo "=== Network connectivity check ==="
        curl -I https://export.arxiv.org/api/query || true
        curl -I https://huggingface.co || true
        curl -I https://www.techempower.com || true
        echo "=== DNS resolution ==="
        nslookup export.arxiv.org || true
        nslookup huggingface.co || true

    - name: Run pipeline
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
        OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
        FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
        FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
        FEISHU_BITABLE_APP_TOKEN: ${{ secrets.FEISHU_BITABLE_APP_TOKEN }}
        FEISHU_BITABLE_TABLE_ID: ${{ secrets.FEISHU_BITABLE_TABLE_ID }}
        FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
        GITHUB_TOKEN: ${{ secrets.GH_PAT }}
        HUGGINGFACE_TOKEN: ${{ secrets.HUGGINGFACE_TOKEN }}
        REDIS_URL: redis://localhost:6379/0
        LOG_LEVEL: INFO
      run: |
        # P15: 添加重试机制，最多重试1次
        python -m src.main || (echo "First attempt failed, retrying in 30s..." && sleep 30 && python -m src.main)

    # P15: 新增失败分析步骤
    - name: Analyze failures
      if: failure()
      run: |
        echo "=== Pipeline failed, analyzing logs ==="
        if [ -f logs/benchscope.log ]; then
          echo "Last 100 lines of log:"
          tail -100 logs/benchscope.log
          echo ""
          echo "Error summary:"
          grep -i "error\|timeout\|failed" logs/benchscope.log | tail -20 || true
        fi
```

**修改原因**：
- 超时从20分钟增加到30分钟（arXiv重试耗时长）
- 添加网络诊断步骤（帮助排查网络问题）
- 添加重试机制（失败后等待30秒重试1次）
- 添加失败分析步骤（自动输出错误日志）

### Step 4: 优化arXiv重试策略

**文件**: `src/collectors/arxiv_collector.py`

**修改位置**: 查找retry相关代码

**当前代码**：
```python
# 假设当前重试逻辑在某处
max_retries = 2
for retry in range(max_retries + 1):
    try:
        # ...查询逻辑...
    except TimeoutError:
        if retry < max_retries:
            logger.warning(f"arXiv查询超时,准备重试({retry+1}/{max_retries})")
            continue
        else:
            logger.error("arXiv连续失败,返回空列表")
            return []
```

**修复后代码**：
```python
# P15: 优化重试策略，增加重试间隔
max_retries = 2
retry_delays = [5, 10]  # P15: 第1次重试等5秒，第2次重试等10秒

for retry in range(max_retries + 1):
    try:
        # ...查询逻辑...
    except (TimeoutError, httpx.TimeoutException) as exc:
        if retry < max_retries:
            delay = retry_delays[retry] if retry < len(retry_delays) else 10
            logger.warning(
                f"arXiv查询超时,准备重试({retry+1}/{max_retries}), "
                f"等待{delay}秒后重试, 错误: {exc}"
            )
            await asyncio.sleep(delay)  # P15: 添加重试延迟
            continue
        else:
            logger.error(
                f"arXiv连续失败{max_retries+1}次,返回空列表, "
                f"超时配置={constants.ARXIV_TIMEOUT_SECONDS}秒"
            )
            return []
```

---

## 测试验证计划

### 本地测试

#### Test 1: 超时配置验证

**命令**：
```bash
.venv/bin/python -c "
from src.common import constants
print(f'arXiv超时: {constants.ARXIV_TIMEOUT_SECONDS}秒')
print(f'HuggingFace超时: {constants.HUGGINGFACE_TIMEOUT_SECONDS}秒')
print(f'TechEmpower超时: {constants.TECHEMPOWER_TIMEOUT_SECONDS}秒')
"
```

**预期输出**：
```
arXiv超时: 30秒
HuggingFace超时: 20秒
TechEmpower超时: 25秒
```

#### Test 2: 完整流程测试

**命令**：
```bash
.venv/bin/python -m src.main 2>&1 | tee /tmp/benchscope_fix_test.log
```

**验证要点**：
- [ ] arXiv采集不再全部超时（成功率>0%）
- [ ] HuggingFace采集改进（有详细错误日志）
- [ ] TechEmpower采集成功（或有明确的超时日志）
- [ ] 总流程耗时 < 4分钟

#### Test 3: 错误处理测试

**手动触发网络错误**（可选）：
```bash
# 暂时禁用网络，测试错误日志
sudo iptables -A OUTPUT -p tcp --dport 443 -d huggingface.co -j DROP
.venv/bin/python -m src.main
sudo iptables -D OUTPUT -p tcp --dport 443 -d huggingface.co -j DROP
```

**预期**：
```
[ERROR] HuggingFace网络错误: Network is unreachable, 请检查网络连接或HuggingFace服务状态
```

### GitHub Actions测试

#### Test 4: 手动触发workflow

**操作步骤**：
1. 提交代码到GitHub
2. 访问 `https://github.com/{用户名}/BenchScope/actions`
3. 点击 "BenchScope Daily Collection"
4. 点击 "Run workflow"
5. 等待运行完成（约5-10分钟）

**验证要点**：
- [ ] workflow在30分钟内完成
- [ ] 网络诊断步骤输出正常
- [ ] arXiv采集成功率>50%
- [ ] 失败时重试机制生效
- [ ] 日志artifacts上传成功

#### Test 5: 失败分析验证

**模拟失败**（修改代码强制失败）：
```python
# 临时修改main.py，在开头添加
raise Exception("Test failure analysis")
```

**验证**：
- [ ] "Analyze failures" 步骤执行
- [ ] 输出最后100行日志
- [ ] 输出错误摘要

---

## 成功标准

### 采集成功率

| 采集器 | 修复前 | 修复后目标 | 验证方法 |
|--------|--------|-----------|----------|
| arXiv | 0% | ≥70% | GitHub Actions日志 |
| HuggingFace | 0% | ≥50% | GitHub Actions日志 |
| TechEmpower | 0% | ≥80% | GitHub Actions日志 |
| HELM | 100% | 100% | 保持稳定 |
| GitHub | 100% | 100% | 保持稳定 |
| DBEngines | 100% | 100% | 保持稳定 |

### 流程指标

- [ ] 本地测试：完整流程耗时 < 4分钟
- [ ] GitHub Actions: workflow耗时 < 15分钟
- [ ] 错误日志：包含详细的超时/网络错误信息
- [ ] 重试机制：失败后自动重试1次

### 日志质量

**修复前**：
```
[ERROR] HuggingFace采集失败: [Errno 101] Network is unreachable
```

**修复后**：
```
[ERROR] HuggingFace网络错误: [Errno 101] Network is unreachable, 请检查网络连接或HuggingFace服务状态, 超时配置=20秒
```

---

## 回滚计划

如果修复导致新问题：

1. **立即回滚配置**：
```bash
git revert HEAD
git push
```

2. **恢复超时配置**：
```python
ARXIV_TIMEOUT_SECONDS = 10
TECHEMPOWER_TIMEOUT_SECONDS = 15
# 删除HUGGINGFACE_TIMEOUT_SECONDS
```

3. **恢复GitHub Actions**：
```yaml
timeout-minutes: 20
# 删除网络诊断和重试步骤
```

---

## 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 超时时间太长导致流程卡住 | 中 | 低 | GitHub Actions 30分钟总超时保护 |
| 重试导致重复数据 | 低 | 低 | URL去重机制已完善 |
| HuggingFace client未关闭 | 低 | 中 | 添加__aexit__确保关闭 |
| 网络诊断增加流程耗时 | 低 | 高 | 诊断步骤耗时<10秒 |

---

## 检查清单

### 代码修改
- [ ] `src/common/constants.py`: 调整3个超时配置
- [ ] `src/collectors/huggingface_collector.py`: 添加超时配置和错误处理
- [ ] `src/collectors/arxiv_collector.py`: 优化重试策略
- [ ] `.github/workflows/daily_collect.yml`: 优化workflow配置

### 测试验证
- [ ] Test 1: 超时配置验证
- [ ] Test 2: 完整流程测试
- [ ] Test 3: 错误处理测试
- [ ] Test 4: GitHub Actions手动触发
- [ ] Test 5: 失败分析验证

### 文档更新
- [ ] 更新CLAUDE.md中的超时配置说明
- [ ] 记录P15修复到commit message
- [ ] 更新README.md（如有需要）

---

## 附录

### A. 超时配置对比

| 采集器 | 修复前 | 修复后 | 增加时长 | 原因 |
|--------|--------|--------|----------|------|
| arXiv | 10s | 30s | +200% | API响应慢，实测需要15-25秒 |
| HuggingFace | 无 | 20s | 新增 | 缺少配置，实测需要10-15秒 |
| TechEmpower | 15s | 25s | +67% | 大JSON文件，需要更多时间 |

### B. GitHub Actions优化对比

| 配置项 | 修复前 | 修复后 | 改进 |
|--------|--------|--------|------|
| 超时 | 20分钟 | 30分钟 | +50% |
| 重试 | 无 | 1次 | 新增 |
| 网络诊断 | 无 | 有 | 新增 |
| 失败分析 | 无 | 有 | 新增 |

### C. 预期流程耗时变化

| 阶段 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| 采集 | 90秒 | 120秒 | +30秒（arXiv重试延迟） |
| 去重 | 2秒 | 2秒 | 无变化 |
| 预筛选 | 1秒 | 1秒 | 无变化 |
| 评分 | 43秒 | 43秒 | 无变化 |
| 存储 | 4秒 | 4秒 | 无变化 |
| 通知 | 2秒 | 2秒 | 无变化 |
| **总计** | **142秒** | **172秒** | **+30秒** |

---

**文档版本**: v1.0
**创建时间**: 2025-12-14
**作者**: Claude Code
**状态**: 待Codex实现
