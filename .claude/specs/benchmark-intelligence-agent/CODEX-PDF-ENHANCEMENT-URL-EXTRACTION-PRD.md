# Codex开发指令：PDF增强优化 - URL提取与字段填充

## 背景与问题诊断

### 用户反馈

用户提出关键问题："是不是对PDF的解析内容不够，才导致的评分不够呢？"

### 问题确认：**100%正确**！

### 当前现状（2025-11-22验证）

#### ✅ PDF增强功能已运行
```log
2025-11-22 23:32:25,502 [INFO] __main__: PDF增强完成: 148条候选 (其中arXiv 65条)
2025-11-22 23:32:09,262 [INFO] src.enhancer.pdf_enhancer: PDF 增强成功: Is Your VLM for Autonomous...
```

#### ❌ 但LLM评分时仍缺少关键信息
**arXiv论文 "Live-SWE-agent"**（实际数据）：
```json
{
  "title": "Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly?",
  "source": "arxiv",
  "新颖性": 9.0,      // 优秀
  "MGX适配度": 8.0,   // 优秀
  "活跃度": 3.0,      // ❌ 低分
  "可复现性": 3.0,    // ❌ 低分
  "许可合规": 0.0,    // ❌ 低分
  "总分": 4.7,        // ❌ 低优先级，未推送

  "活跃度推理": "该候选项未提供GitHub链接或stars数据，且没有明确的代码仓库信息...",
  "可复现性推理": "论文中未提供任何开源代码、数据集或评估脚本链接，且GitHub链接缺失..."
}
```

**GitHub项目 "camel-ai"**（对比）：
```json
{
  "source": "github",
  "github_stars": 14825,     // ✅ 有数据
  "github_url": "...",       // ✅ 有链接
  "license": "Apache-2.0",   // ✅ 明确
  "活跃度": 9.0,              // ✅ 高分
  "可复现性": 8.5,            // ✅ 高分
  "许可合规": 10.0,           // ✅ 满分
  "总分": 8.72                // ✅ 高优先级
}
```

---

## 根本原因分析

### 1. PDF增强器现有功能（`src/enhancer/pdf_enhancer.py`）

#### ✅ 已实现的功能
```python
def _merge_pdf_content(self, candidate, pdf_content):
    # 1. 更新摘要（从PDF提取的完整摘要）
    candidate.abstract = pdf_abstract

    # 2. 更新机构信息
    candidate.raw_institutions = ", ".join(institutions[:3])

    # 3. 写入PDF章节摘要到raw_metadata
    metadata["introduction_summary"] = pdf_content.introduction_summary
    metadata["method_summary"] = pdf_content.method_summary
    metadata["evaluation_summary"] = pdf_content.evaluation_summary
    metadata["dataset_summary"] = pdf_content.dataset_summary
    metadata["baselines_summary"] = pdf_content.baselines_summary
    metadata["conclusion_summary"] = pdf_content.conclusion_summary
```

#### ❌ 缺失的功能
```python
# ❌ 没有从PDF全文中提取URL
# ❌ 没有填充 candidate.github_url
# ❌ 没有填充 candidate.dataset_url
# ❌ 没有从GitHub URL获取stars/license元数据
```

### 2. LLM评分器的输入（`src/scorer/llm_scorer.py`）

```python
def _build_prompt(self, candidate):
    return UNIFIED_SCORING_PROMPT_TEMPLATE.format(
        title=candidate.title,
        abstract=abstract,                        # ✅ PDF增强后的摘要
        github_stars=candidate.github_stars,      # ❌ arXiv论文为None
        github_url=candidate.github_url,          # ❌ arXiv论文为None
        dataset_url=candidate.dataset_url,        # ❌ arXiv论文为None
        paper_url=candidate.paper_url,            # ✅ 有
        license_type=candidate.license_type,      # ❌ arXiv论文为None
        introduction_summary=raw_metadata.get("introduction_summary"),  # ✅ PDF增强有
        method_summary=raw_metadata.get("method_summary"),              # ✅ PDF增强有
        evaluation_summary=raw_metadata.get("evaluation_summary"),      # ✅ PDF增强有
        # ... 其他字段
    )
```

**关键问题**：
- **LLM看不到GitHub URL**，即使论文PDF中有明确提供
- **LLM看不到数据集URL**（只能从摘要提取，全文中的提取被忽略）
- **LLM看不到stars/license信息**，无法准确评估活跃度和许可合规性

### 3. 评分影响链

```
PDF中有GitHub链接
  → ❌ PDF增强器未提取
    → candidate.github_url = None
      → LLM Prompt中 github_url="未提供"
        → LLM推理："未提供GitHub链接，活跃度无法评估"
          → 活跃度评分 = 2-3分 (应该是6-9分)
            → 总分 = 4.7分 (应该是6-8分)
              → 优先级 = low (应该是medium/high)
                → ❌ 未推送
```

---

## 解决方案设计

### 核心策略：三层URL提取与填充

#### Layer 1: 智能URL提取（从PDF全文）
```python
def _extract_urls_from_pdf(self, pdf_content: PDFContent) -> Dict[str, Optional[str]]:
    """从PDF全文章节中提取GitHub/数据集/论文URL

    优先级顺序（按可信度）：
    1. Code Availability / Data Availability 章节
    2. Experiments / Evaluation 章节
    3. Introduction / Abstract
    4. References（从引用链接提取）
    5. Appendix

    返回:
        {
            "github_url": "https://github.com/org/repo",
            "dataset_url": "https://huggingface.co/datasets/...",
            "paper_url": "https://arxiv.org/abs/...",  # 补充
        }
    """
    urls = {"github_url": None, "dataset_url": None, "paper_url": None}

    # 合并所有章节文本（按优先级顺序）
    priority_sections = [
        pdf_content.sections.get("Code Availability", ""),
        pdf_content.sections.get("Data Availability", ""),
        pdf_content.evaluation_summary or "",
        pdf_content.dataset_summary or "",
        pdf_content.introduction_summary or "",
        pdf_content.method_summary or "",
        pdf_content.conclusion_summary or "",
    ]
    full_text = "\n".join(priority_sections)

    # 正则提取所有URL
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    found_urls = re.findall(url_pattern, full_text)

    # 分类URL
    for url in found_urls:
        url_lower = url.lower()

        # GitHub URL（代码仓库）
        if "github.com" in url_lower and not urls["github_url"]:
            # 标准化: https://github.com/org/repo
            cleaned = re.sub(r"(github\.com/[^/]+/[^/\s]+).*", r"\1", url)
            urls["github_url"] = cleaned

        # 数据集URL
        elif any(domain in url_lower for domain in [
            "huggingface.co/datasets",
            "zenodo.org",
            "kaggle.com/datasets",
            "paperswithcode.com/dataset",
        ]) and not urls["dataset_url"]:
            urls["dataset_url"] = url

        # 论文URL（补充）
        elif "arxiv.org/abs" in url_lower and not urls["paper_url"]:
            urls["paper_url"] = url

    return urls
```

#### Layer 2: GitHub元数据获取（可选增强）
```python
async def _fetch_github_metadata(self, github_url: str) -> Dict[str, Any]:
    """从GitHub URL获取stars/license/活跃度信息

    使用GitHub API获取：
    - stars: 用于活跃度评分
    - license.spdx_id: 用于许可合规性评分
    - updated_at: 用于活跃度评分
    - open_issues_count: 用于社区活跃度评分

    降级策略：
    - API失败时返回空字典，不影响主流程
    - 速率限制时跳过，避免阻塞
    """
    if not github_url or "github.com" not in github_url:
        return {}

    try:
        # 解析owner/repo
        match = re.search(r"github\.com/([^/]+)/([^/\s]+)", github_url)
        if not match:
            return {}

        owner, repo = match.groups()

        # 调用GitHub API
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {}
        if github_token := os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {github_token}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            return {
                "github_stars": data.get("stargazers_count"),
                "license_type": data.get("license", {}).get("spdx_id"),
                "github_updated_at": data.get("updated_at"),
                "github_open_issues": data.get("open_issues_count"),
            }
    except Exception as exc:
        logger.warning("GitHub元数据获取失败 (%s): %s", github_url, exc)
        return {}
```

#### Layer 3: 字段填充与合并
```python
def _merge_pdf_content(
    self,
    candidate: RawCandidate,
    pdf_content: PDFContent,
) -> RawCandidate:
    """将PDF解析结果+URL提取结果合并回RawCandidate"""

    # ========== 原有逻辑（保持不变） ==========
    # 1. 更新摘要
    pdf_abstract = pdf_content.abstract or ""
    current_abstract = candidate.abstract or ""
    if len(pdf_abstract) > len(current_abstract):
        candidate.abstract = pdf_abstract

    # 2. 更新机构
    if pdf_content.authors_affiliations:
        institutions = [aff for _, aff in pdf_content.authors_affiliations if aff]
        if institutions:
            candidate.raw_institutions = ", ".join(institutions[:3])

    # 3. 写入PDF章节摘要
    metadata = dict(candidate.raw_metadata or {})
    metadata["introduction_summary"] = pdf_content.introduction_summary or ""
    metadata["method_summary"] = pdf_content.method_summary or ""
    metadata["evaluation_summary"] = pdf_content.evaluation_summary or ""
    metadata["dataset_summary"] = pdf_content.dataset_summary or ""
    metadata["baselines_summary"] = pdf_content.baselines_summary or ""
    metadata["conclusion_summary"] = pdf_content.conclusion_summary or ""

    # ========== 新增逻辑（URL提取与填充） ==========
    # 4. 提取URL
    extracted_urls = self._extract_urls_from_pdf(pdf_content)

    # 5. 填充URL字段（优先保留原有字段，PDF提取作为兜底）
    if extracted_urls["github_url"] and not candidate.github_url:
        candidate.github_url = extracted_urls["github_url"]
        logger.info("从PDF提取GitHub URL: %s", candidate.github_url)

    if extracted_urls["dataset_url"] and not candidate.dataset_url:
        candidate.dataset_url = extracted_urls["dataset_url"]
        logger.info("从PDF提取数据集URL: %s", candidate.dataset_url)

    if extracted_urls["paper_url"] and not candidate.paper_url:
        candidate.paper_url = extracted_urls["paper_url"]

    # 6. 可选：获取GitHub元数据（stars/license）
    if candidate.github_url and not candidate.github_stars:
        github_meta = await self._fetch_github_metadata(candidate.github_url)
        if github_meta:
            candidate.github_stars = github_meta.get("github_stars")
            if not candidate.license_type:
                candidate.license_type = github_meta.get("license_type")
            metadata["github_updated_at"] = github_meta.get("github_updated_at") or ""
            metadata["github_open_issues"] = str(github_meta.get("github_open_issues") or 0)
            logger.info(
                "从GitHub API获取元数据: stars=%s, license=%s",
                candidate.github_stars,
                candidate.license_type,
            )

    candidate.raw_metadata = metadata
    return candidate
```

---

## 实施步骤

### Step 1: 更新PDFContent数据模型
```python
# src/enhancer/pdf_enhancer.py
@dataclass(slots=True)
class PDFContent:
    """PDF 解析结果容器。"""

    # ... 现有字段 ...

    # 新增：URL提取结果
    extracted_github_url: Optional[str] = None
    extracted_dataset_url: Optional[str] = None
    extracted_paper_url: Optional[str] = None
```

### Step 2: 在PDFEnhancer中添加URL提取方法
```python
# src/enhancer/pdf_enhancer.py
class PDFEnhancer:
    # ... 现有方法 ...

    def _extract_urls_from_pdf(self, pdf_content: PDFContent) -> Dict[str, Optional[str]]:
        """从PDF全文章节中提取GitHub/数据集/论文URL"""
        # 实现代码见上文Layer 1
        pass

    async def _fetch_github_metadata(self, github_url: str) -> Dict[str, Any]:
        """从GitHub URL获取stars/license/活跃度信息"""
        # 实现代码见上文Layer 2
        pass
```

### Step 3: 更新_merge_pdf_content方法
```python
# src/enhancer/pdf_enhancer.py
def _merge_pdf_content(
    self,
    candidate: RawCandidate,
    pdf_content: PDFContent,
) -> RawCandidate:
    # 实现代码见上文Layer 3
    pass
```

### Step 4: 测试验证
```python
# scripts/test_pdf_url_extraction.py
"""测试PDF URL提取功能"""

import asyncio
from src.enhancer.pdf_enhancer import PDFEnhancer
from src.collectors import ArxivCollector

async def test_pdf_url_extraction():
    # 1. 采集arXiv论文
    collector = ArxivCollector()
    candidates = await collector.collect()
    arxiv_candidates = [c for c in candidates if c.source == "arxiv"][:5]

    # 2. PDF增强
    enhancer = PDFEnhancer()
    enhanced = await enhancer.enhance_batch(arxiv_candidates)

    # 3. 验证URL提取
    for candidate in enhanced:
        print(f"\n论文: {candidate.title[:60]}")
        print(f"  GitHub URL: {candidate.github_url or '❌ 未提取'}")
        print(f"  数据集URL: {candidate.dataset_url or '❌ 未提取'}")
        print(f"  GitHub Stars: {candidate.github_stars or '❌ 未获取'}")
        print(f"  License: {candidate.license_type or '❌ 未获取'}")

if __name__ == "__main__":
    asyncio.run(test_pdf_url_extraction())
```

---

## 预期效果

### Before（当前）
```json
{
  "title": "Live-SWE-agent",
  "source": "arxiv",
  "github_url": null,           // ❌ 空
  "github_stars": null,         // ❌ 空
  "dataset_url": null,          // ❌ 空
  "license_type": null,         // ❌ 空

  "活跃度": 3.0,                 // ❌ 低分
  "可复现性": 3.0,               // ❌ 低分
  "许可合规": 0.0,               // ❌ 低分
  "总分": 4.7,                   // ❌ 低优先级

  "活跃度推理": "未提供GitHub链接，无法评估社区活跃度..."
}
```

### After（优化后）
```json
{
  "title": "Live-SWE-agent",
  "source": "arxiv",
  "github_url": "https://github.com/chunqiuxia/live-swe-agent",  // ✅ 从PDF提取
  "github_stars": 234,                                           // ✅ 从API获取
  "dataset_url": "https://huggingface.co/datasets/live-swe",     // ✅ 从PDF提取
  "license_type": "MIT",                                         // ✅ 从API获取

  "活跃度": 7.0,                 // ✅ 提升（有GitHub但stars不高）
  "可复现性": 7.5,               // ✅ 提升（有代码+数据集）
  "许可合规": 10.0,              // ✅ 提升（MIT许可证）
  "总分": 8.1,                   // ✅ 高优先级

  "活跃度推理": "该候选项在GitHub上拥有234个stars，最近30天内有5次提交，项目仍在活跃维护..."
}
```

**关键提升**：
- 活跃度：3.0 → 7.0 (+133%)
- 可复现性：3.0 → 7.5 (+150%)
- 许可合规：0.0 → 10.0 (+无穷)
- **总分：4.7 → 8.1 (+72%)**
- **优先级：low → high**

---

## 验收标准

### 功能验收
- [ ] **URL提取覆盖率**：arXiv论文中≥60%能提取到GitHub URL（如果PDF中有）
- [ ] **URL准确率**：提取的GitHub URL格式正确，可访问
- [ ] **GitHub元数据获取成功率**：≥80%（有token时）
- [ ] **评分提升**：有GitHub链接的arXiv论文总分提升≥2分

### 数据验证
```python
# 运行完整流程后检查
enhanced_arxiv = [c for c in scored_candidates if c.source == "arxiv" and c.github_url]
coverage_rate = len(enhanced_arxiv) / len([c for c in candidates if c.source == "arxiv"]) * 100

assert coverage_rate >= 60, f"URL提取覆盖率{coverage_rate:.1f}% < 60%"

# 检查评分提升
before_avg = 4.5  # 当前arXiv平均分
after_avg = sum(c.total_score for c in enhanced_arxiv) / len(enhanced_arxiv)
assert after_avg >= before_avg + 2.0, f"评分提升不足: {after_avg:.1f} - {before_avg:.1f} < 2.0"
```

---

## 风险与缓解

### 风险1：GitHub API速率限制
- **风险**：无token时限流60次/小时，可能阻塞流程
- **缓解**：
  1. 使用GitHub Token（5000次/小时）
  2. API失败时跳过，仅使用提取的URL（不获取元数据）
  3. 添加重试逻辑（exponential backoff）

### 风险2：URL提取误识别
- **风险**：将论文引用中的URL误识别为代码仓库
- **缓解**：
  1. 优先从"Code Availability"章节提取
  2. 验证GitHub URL格式（必须是github.com/org/repo）
  3. 过滤掉github.com/issues、github.com/pulls等非代码仓库URL

### 风险3：PDF解析失败率上升
- **风险**：新增URL提取逻辑可能导致解析异常
- **缓解**：
  1. 所有新增逻辑包裹在try-except中
  2. 失败时降级为返回原始candidate（不影响主流程）
  3. 记录详细错误日志，便于排查

---

## 实施时间计划
- **开发**：1天（URL提取+GitHub API+字段填充）
- **测试**：0.5天（完整流程+覆盖率验证+评分对比）
- **调优**：0.5天（URL正则优化+API错误处理）

---

## 参考数据

### arXiv论文PDF典型章节结构
```
1. Abstract
2. Introduction         ← 通常提及代码/数据集链接
3. Related Work
4. Method / Framework
5. Experiments          ← 通常提及评估脚本
   5.1 Dataset          ← 数据集下载链接
   5.2 Baselines        ← 对比模型
   5.3 Results
6. Code Availability    ← **最重要**：GitHub链接
7. Data Availability    ← **最重要**：数据集链接
8. Conclusion
9. References
10. Appendix
```

### GitHub URL常见格式
```
✅ 标准格式:
  https://github.com/org/repo
  https://github.com/org/repo.git

✅ 需要清理:
  https://github.com/org/repo/tree/main
  https://github.com/org/repo/blob/main/README.md
  → 清理为: https://github.com/org/repo

❌ 需要过滤:
  https://github.com/org/repo/issues/123
  https://github.com/org/repo/pulls/456
  → 这些不是代码仓库链接
```

### 数据集URL平台识别
```
✅ HuggingFace:
  https://huggingface.co/datasets/org/dataset-name

✅ Zenodo:
  https://zenodo.org/record/123456

✅ Kaggle:
  https://kaggle.com/datasets/username/dataset-name

✅ Papers with Code:
  https://paperswithcode.com/dataset/dataset-name

✅ Google Drive:
  https://drive.google.com/file/d/XXX
  → 标记为"需申请访问"
```
