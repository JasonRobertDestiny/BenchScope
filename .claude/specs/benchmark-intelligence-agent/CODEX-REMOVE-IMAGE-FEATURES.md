# Codex开发指令：删除所有图片相关功能

**决策时间**: 2025-11-23
**决策理由**: 图片功能没必要，耗时且质量低，影响核心流程性能
**优先级**: P0（高优先级清理）

---

## 一、问题背景

### 当前问题

图片功能（Phase 9引入）在实践中暴露了多个问题：

1. **性能问题**：
   - arXiv PDF转图片（pdf2image）需要Poppler依赖，部署复杂
   - 图片下载、验证、上传增加30-60秒处理时间
   - 飞书图片上传API不稳定，偶现超时失败

2. **质量问题**：
   - GitHub og:image质量参差不齐（很多是Logo或默认头像）
   - arXiv PDF首页图大多是标题页，信息量低
   - HuggingFace数据集封面图抓取成功率<30%

3. **维护成本**：
   - 7个图片测试脚本需要维护
   - Redis缓存逻辑增加系统复杂度
   - Poppler依赖在GitHub Actions环境需要额外安装

4. **实际价值**：
   - 飞书卡片展示中图片非必需
   - 用户更关注评分、摘要、来源等核心信息
   - 图片展示区域有限，信息密度低

### 决策

**完全删除所有图片相关功能**，回归核心Benchmark发现与评分流程。

---

## 二、删除范围清单

### 2.1 完整删除的文件（8个）

```bash
# 核心模块
src/storage/feishu_image_uploader.py        # 飞书图片上传器（206行）
src/extractors/image_extractor.py           # 图片提取器（282行）

# 测试脚本
scripts/test_image_extraction.py
scripts/test_external_image_card.py
scripts/test_complete_image_pipeline.py
scripts/test_image_storage.py
scripts/test_huggingface_image_fix.py
scripts/test_arxiv_image_generation.py
scripts/test_image_url_filter.py
```

**Action**: 使用`rm`命令直接删除上述文件

---

### 2.2 需要修改的文件（11个）

#### 文件1: `src/models.py`

**删除内容**：
- `hero_image_url: Optional[str]` 字段（RawCandidate和ScoredCandidate）
- `hero_image_key: Optional[str]` 字段（已废弃，顺便清理）

**当前代码**：
```python
@dataclass(slots=True)
class RawCandidate:
    ...
    dataset_url: Optional[str] = None
    hero_image_url: Optional[str] = None  # Phase 9: 图片原始URL  ← 删除此行
    hero_image_key: Optional[str] = None  # Phase 9: 飞书image_key (已废弃)  ← 删除此行
    raw_metrics: Optional[List[str]] = None
    ...

@dataclass(slots=True)
class ScoredCandidate:
    ...
    dataset_url: Optional[str] = None
    hero_image_url: Optional[str] = None  ← 删除此行
    hero_image_key: Optional[str] = None  # 已废弃  ← 删除此行
    raw_metadata: Dict[str, str] = field(default_factory=dict)
    ...
```

**修改后代码**：
```python
@dataclass(slots=True)
class RawCandidate:
    ...
    dataset_url: Optional[str] = None
    # hero_image_url和hero_image_key已删除
    raw_metrics: Optional[List[str]] = None
    ...

@dataclass(slots=True)
class ScoredCandidate:
    ...
    dataset_url: Optional[str] = None
    # hero_image_url和hero_image_key已删除
    raw_metadata: Dict[str, str] = field(default_factory=dict)
    ...
```

---

#### 文件2: `src/extractors/__init__.py`

**删除内容**：移除ImageExtractor导出

**当前代码**：
```python
"""Feature Extractors"""

from src.extractors.image_extractor import ImageExtractor  ← 删除此行

__all__ = ["ImageExtractor"]  ← 删除此行
```

**修改后代码**：
```python
"""Feature Extractors"""

# 图片提取器已删除（2025-11-23）

__all__ = []
```

---

#### 文件3: `src/collectors/arxiv_collector.py`

**删除内容**：删除`ImageExtractor.extract_arxiv_image`调用及相关代码

**当前代码**（约102-123行）：
```python
from src.extractors import ImageExtractor  ← 删除此导入

# 约102行
hero_image_key = await ImageExtractor.extract_arxiv_image(
    pdf_path=str(pdf_file), arxiv_id=arxiv_id
)

candidates.append(
    RawCandidate(
        ...
        hero_image_url=None,  ← 删除此参数
        hero_image_key=hero_image_key,  ← 删除此参数
        ...
    )
)
```

**修改后代码**：
```python
# 删除ImageExtractor导入

candidates.append(
    RawCandidate(
        title=title,
        url=arxiv_url,
        source="arxiv",
        abstract=summary,
        authors=authors,
        publish_date=published,
        paper_url=arxiv_url,
        raw_metrics=raw_metrics,
        raw_baselines=raw_baselines,
        raw_authors=raw_authors,
        raw_institutions=raw_institutions,
        raw_dataset_size=raw_dataset_size,
    )
)
```

**注意**：确保删除`hero_image_url`和`hero_image_key`参数后RawCandidate构造正常。

---

#### 文件4: `src/collectors/github_collector.py`

**删除内容**：删除`ImageExtractor.extract_github_image`调用

**当前代码**（约216-239行）：
```python
from src.extractors import ImageExtractor  ← 删除此导入

# 约216行
hero_image_url = await ImageExtractor.extract_github_image(
    repo_url=url, readme_html=readme_html
)

return RawCandidate(
    ...
    hero_image_url=hero_image_url,  ← 删除此参数
    ...
)
```

**修改后代码**：
```python
# 删除ImageExtractor导入

return RawCandidate(
    title=title,
    url=url,
    source="github",
    abstract=description,
    authors=authors,
    publish_date=None,
    github_stars=stars,
    github_url=url,
    dataset_url=None,
    task_type=task_type,
    license_type=license_type,
    evaluation_metrics=evaluation_metrics,
    reproduction_script_url=reproduction_script_url,
    raw_metadata={"readme_snippet": readme_snippet[:500]},
)
```

---

#### 文件5: `src/collectors/huggingface_collector.py`

**删除内容**：删除`ImageExtractor.extract_huggingface_image`调用

**当前代码**（约54行）：
```python
from src.extractors import ImageExtractor  ← 删除此导入

# 约54行
candidate.hero_image_url = await ImageExtractor.extract_huggingface_image(
    dataset_id=candidate_id
)
```

**修改后代码**：
```python
# 删除ImageExtractor导入
# 删除extract_huggingface_image调用（约54行附近）
```

---

#### 文件6: `src/collectors/helm_collector.py`

**删除内容**：删除`ImageExtractor.extract_og_image`调用

**当前代码**（约157-180行）：
```python
from src.extractors import ImageExtractor  ← 删除此导入

# 约157行
hero_image_url = await ImageExtractor.extract_og_image(candidate_url)

candidates.append(
    RawCandidate(
        ...
        hero_image_url=hero_image_url,  ← 删除此参数
        ...
    )
)
```

**修改后代码**：
```python
# 删除ImageExtractor导入

candidates.append(
    RawCandidate(
        title=name,
        url=candidate_url,
        source="helm",
        abstract=description,
        authors=None,
        publish_date=None,
        dataset_url=None,
        task_type=inferred_task,
        raw_metadata={"category": category, "tags": tags},
    )
)
```

---

#### 文件7: `src/storage/feishu_storage.py`

**删除内容**：删除`hero_image_url`字段处理逻辑

**当前代码**（约401-403行）：
```python
# 约401行
if getattr(candidate, "hero_image_url", None):
    fields[self.FIELD_MAPPING["hero_image_url"]] = {
        "link": candidate.hero_image_url
    }
```

**修改后代码**：
```python
# 删除hero_image_url字段处理（约401-403行）
```

**说明**：FIELD_MAPPING中的"hero_image_url"映射也可以保留（因为飞书表格字段已存在），或者删除（更彻底）。建议保留映射但删除赋值逻辑，避免飞书API报错。

---

#### 文件8: `src/storage/sqlite_fallback.py`

**删除内容**：删除`hero_image_url`字段存储

**当前代码**（约149行）：
```python
# 约149行
"hero_image_url": candidate.hero_image_url,
```

**修改后代码**：
```python
# 删除hero_image_url字段（约149行）
```

**说明**：SQLite表结构中的hero_image_url列可以保留（向后兼容），但存储时不再写入。

---

#### 文件9: `src/scorer/llm_scorer.py`

**删除内容**：删除`hero_image_url`字段传递

**当前代码**（约861行）：
```python
# 约861行
hero_image_url=candidate.hero_image_url,
```

**修改后代码**：
```python
# 删除hero_image_url字段传递（约861行）
```

---

#### 文件10: `src/scorer/backend_scorer.py`

**删除内容**：删除`hero_image_url`字段传递

**当前代码**（约197行）：
```python
# 约197行
hero_image_url=candidate.hero_image_url,
```

**修改后代码**：
```python
# 删除hero_image_url字段传递（约197行）
```

---

#### 文件11: `src/common/constants.py`

**删除内容**：删除所有图片相关常量（约22-23行、227行、376行、408行、482-491行）

**当前代码**：
```python
# 约22-23行
ARXIV_IMAGE_CACHE_PREFIX: Final[str] = "arxiv_pdf_image:"
ARXIV_IMAGE_CONVERT_DPI: Final[int] = 150  # pdf2image渲染DPI

# 约227行（HELM_EXCLUDED_SCENARIOS列表中）
"image",

# 约376行（PREFILTER_REQUIRED_KEYWORDS列表中）
"image-text",

# 约408行（PREFILTER_EXCLUDED_KEYWORDS列表中）
"image classification",

# 约482-491行
# ---- 图片处理配置 ----
IMAGE_MIN_SIZE_BYTES: Final[int] = 30 * 1024
IMAGE_MAX_SIZE_BYTES: Final[int] = 5 * 1024 * 1024
IMAGE_MIN_WIDTH: Final[int] = 300
IMAGE_MIN_HEIGHT: Final[int] = 200
IMAGE_DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 5
IMAGE_UPLOAD_TIMEOUT_SECONDS: Final[int] = 10
IMAGE_CACHE_TTL_SECONDS: Final[int] = 30 * 24 * 3600
IMAGE_CACHE_PREFIX: Final[str] = "feishu:img:"
IMAGE_SUPPORTED_FORMATS: Final[list[str]] = ["JPEG", "PNG", "GIF", "BMP"]
```

**修改后代码**：
```python
# 删除ARXIV_IMAGE_CACHE_PREFIX, ARXIV_IMAGE_CONVERT_DPI（约22-23行）
# 删除"image"（HELM_EXCLUDED_SCENARIOS，约227行）
# 删除"image-text"（PREFILTER_REQUIRED_KEYWORDS，约376行）
# 删除"image classification"（PREFILTER_EXCLUDED_KEYWORDS，约408行）
# 删除整个"图片处理配置"段落（约482-491行，共10行）
```

---

#### 文件12: `requirements.txt`

**删除内容**：删除图片处理依赖

**当前代码**：
```txt
Pillow>=10.2.0  # Phase 9: 图片验证
pdf2image==1.16.3
```

**修改后代码**：
```txt
# Pillow和pdf2image已删除（2025-11-23）
```

---

## 三、实施步骤

### Step 1: 删除核心模块和测试脚本

```bash
# 删除核心模块
rm src/storage/feishu_image_uploader.py
rm src/extractors/image_extractor.py

# 删除测试脚本
rm scripts/test_image_extraction.py
rm scripts/test_external_image_card.py
rm scripts/test_complete_image_pipeline.py
rm scripts/test_image_storage.py
rm scripts/test_huggingface_image_fix.py
rm scripts/test_arxiv_image_generation.py
rm scripts/test_image_url_filter.py
```

### Step 2: 修改数据模型（src/models.py）

删除`RawCandidate`和`ScoredCandidate`中的：
- `hero_image_url: Optional[str] = None`
- `hero_image_key: Optional[str] = None`

### Step 3: 清理采集器（4个文件）

按照"删除范围清单"修改：
- `src/collectors/arxiv_collector.py`
- `src/collectors/github_collector.py`
- `src/collectors/huggingface_collector.py`
- `src/collectors/helm_collector.py`

**关键点**：
1. 删除`from src.extractors import ImageExtractor`导入
2. 删除所有`ImageExtractor.extract_*`调用
3. 删除RawCandidate构造中的`hero_image_url`和`hero_image_key`参数

### Step 4: 清理存储层（2个文件）

- `src/storage/feishu_storage.py`：删除hero_image_url字段处理（约401-403行）
- `src/storage/sqlite_fallback.py`：删除hero_image_url字段存储（约149行）

### Step 5: 清理评分器（2个文件）

- `src/scorer/llm_scorer.py`：删除hero_image_url字段传递（约861行）
- `src/scorer/backend_scorer.py`：删除hero_image_url字段传递（约197行）

### Step 6: 清理导出和常量（2个文件）

- `src/extractors/__init__.py`：移除ImageExtractor导出
- `src/common/constants.py`：删除所有图片相关常量（约14行）

### Step 7: 清理依赖（requirements.txt）

删除：
- `Pillow>=10.2.0`
- `pdf2image==1.16.3`

### Step 8: 重新安装依赖并测试

```bash
# 重新安装依赖
.venv/bin/pip install -r requirements.txt

# 运行完整流程测试
.venv/bin/python -m src.main

# 检查日志，确保无图片相关错误
tail -100 logs/$(ls -t logs/ | head -n1)
```

---

## 四、验证计划

### 4.1 单元测试（手动）

测试采集器是否正常工作（无图片功能）：

```bash
# 测试arXiv采集（无PDF转图片）
.venv/bin/python -c "
import asyncio
from src.collectors import ArxivCollector
async def test():
    collector = ArxivCollector()
    candidates = await collector.collect()
    print(f'✓ arXiv采集: {len(candidates)}条')
    assert all(getattr(c, 'hero_image_url', 'MISSING') == 'MISSING' for c in candidates)
asyncio.run(test())
"

# 测试GitHub采集（无图片提取）
.venv/bin/python -c "
import asyncio
from src.collectors import GitHubCollector
async def test():
    collector = GitHubCollector()
    candidates = await collector.collect()
    print(f'✓ GitHub采集: {len(candidates)}条')
    assert all(getattr(c, 'hero_image_url', 'MISSING') == 'MISSING' for c in candidates)
asyncio.run(test())
"
```

### 4.2 集成测试（完整流程）

```bash
# 运行完整流程（采集 → 预筛 → 评分 → 存储 → 通知）
.venv/bin/python -m src.main

# 预期结果：
# 1. 无ImageExtractor相关日志
# 2. 无pdf2image相关错误
# 3. 无Pillow相关错误
# 4. 飞书表格写入成功（hero_image_url列为空）
# 5. 飞书通知推送成功（无图片）
```

### 4.3 飞书验证（手动）

1. 打开飞书多维表格：https://deepwisdom.feishu.cn/base/SbIibGBIWayQncslz5kcYMnrnGf
2. 检查新写入的记录：
   - `hero_image_url`列应该为空
   - 其他字段（标题、来源、评分）正常
3. 检查飞书通知推送：
   - 卡片展示正常
   - 无图片展示区域
   - 内容清晰可读

---

## 五、预期效果

### 5.1 性能提升

- **采集阶段**：减少30-60秒图片下载/转换时间
- **完整流程**：从~90秒降至~60秒（提升33%）
- **并发度**：无需限制图片上传并发，系统更稳定

### 5.2 维护成本降低

- **删除代码**：约500行图片处理代码
- **删除测试**：7个图片测试脚本
- **依赖简化**：不再依赖Poppler、pdf2image、Pillow

### 5.3 系统简化

- **模块数量**：从14个核心模块降至12个
- **数据模型**：RawCandidate和ScoredCandidate各减少2个字段
- **配置常量**：减少14个图片相关常量

---

## 六、风险与回退

### 6.1 风险评估

**零风险**：图片功能与核心流程解耦，删除不影响评分、存储、通知

### 6.2 回退方案

如果需要恢复图片功能（可能性<1%）：
```bash
# 从Git历史恢复
git checkout HEAD~1 src/storage/feishu_image_uploader.py
git checkout HEAD~1 src/extractors/image_extractor.py
```

---

## 七、成功标准

### 验收清单

- [ ] 所有8个图片相关文件已删除
- [ ] 所有11个修改文件已更新（无hero_image_url引用）
- [ ] requirements.txt已删除Pillow和pdf2image
- [ ] `grep -r "hero_image" src/` 返回0结果（除注释）
- [ ] `grep -r "ImageExtractor" src/` 返回0结果
- [ ] `grep -r "pdf2image" .` 返回0结果（除.venv）
- [ ] 完整流程测试通过（.venv/bin/python -m src.main）
- [ ] 飞书表格写入正常（hero_image_url列为空）
- [ ] 飞书通知推送正常（无图片）
- [ ] 日志无ImageExtractor相关错误

---

## 八、补充说明

### 8.1 保留的图片相关字符串

以下字符串是关键词/排除词，**不要删除**：
- `constants.py`中的`"image"`（HELM_EXCLUDED_SCENARIOS）
- `constants.py`中的`"image-text"`（PREFILTER_REQUIRED_KEYWORDS）
- `constants.py`中的`"image classification"`（PREFILTER_EXCLUDED_KEYWORDS）

**理由**：这些是用于过滤无关Benchmark的关键词，与图片处理功能无关。

**建议**：暂时保留这些关键词，后续可通过数据分析决定是否删除。

---

## 九、Codex执行总结

Codex请按以下顺序执行：

1. **Step 1**: 删除8个文件（rm命令）
2. **Step 2-7**: 修改11个文件（严格按照"删除范围清单"）
3. **Step 8**: 重新安装依赖并测试
4. **验证**: 执行4.1-4.3的验证计划
5. **报告**: 提交修改清单+测试结果+飞书截图

---

**任务完成标准**：Claude Code验收通过 ✅
