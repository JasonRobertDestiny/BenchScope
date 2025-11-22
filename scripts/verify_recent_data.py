"""验证最近采集数据的新鲜度（基于日志分析）"""

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, TypedDict, cast

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class LogStats(TypedDict, total=False):
    """日志统计字段定义"""

    arxiv_count: int
    github_count: int
    hf_count: int
    prefilter_input: int
    prefilter_output: int
    prefilter_rate: float
    score_success: int
    score_total: int


class KeywordStats(TypedDict, total=False):
    """关键词覆盖统计字段定义"""

    total_keywords: int
    has_reasoning: bool
    has_multimodal: bool
    has_knowledge: bool
    sample_keywords: List[str]


def parse_log_file(log_file: Path) -> LogStats:
    """解析日志文件，提取采集数据"""

    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取采集统计
    arxiv_match = re.search(r"ArxivCollector: (\d+)条", content)
    github_match = re.search(r"GitHubCollector: (\d+)条", content)
    hf_match = re.search(r"HuggingFaceCollector: (\d+)条", content)

    # 提取预筛选统计
    prefilter_match = re.search(
        r"预筛选完成,输入(\d+)条,输出(\d+)条,过滤率([\d.]+)%",
        content,
    )

    # 提取评分统计
    score_match = re.search(r"批量评分完成: 成功(\d+)条/共(\d+)条", content)

    stats: LogStats = {
        "arxiv_count": int(arxiv_match.group(1)) if arxiv_match else 0,
        "github_count": int(github_match.group(1)) if github_match else 0,
        "hf_count": int(hf_match.group(1)) if hf_match else 0,
    }

    if prefilter_match:
        stats["prefilter_input"] = int(prefilter_match.group(1))
        stats["prefilter_output"] = int(prefilter_match.group(2))
        stats["prefilter_rate"] = float(prefilter_match.group(3))

    if score_match:
        stats["score_success"] = int(score_match.group(1))
        stats["score_total"] = int(score_match.group(2))

    return stats


def analyze_github_query_strategy():
    """分析GitHub采集器的查询策略"""

    github_collector_file = Path("src/collectors/github_collector.py")

    with open(github_collector_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查使用的是 pushed:>= 还是 created:>=
    if 'pushed:>=' in content:
        strategy = "pushed:>= (最后更新时间)"
        issue = "❌ 会采集老项目的新commit"
    elif 'created:>=' in content:
        strategy = "created:>= (首次创建时间)"
        issue = "✅ 只采集新创建的项目"
    else:
        strategy = "未知"
        issue = "⚠️ 无法确定策略"

    # 检查时间窗口
    lookback_match = re.search(r'lookback_days.*=.*(\d+)', content)
    lookback_days = int(lookback_match.group(1)) if lookback_match else "未知"

    return {
        'strategy': strategy,
        'issue': issue,
        'lookback_days': lookback_days,
    }


def analyze_prefilter_keywords() -> KeywordStats:
    """分析预筛选关键词覆盖"""

    constants_file = Path("src/common/constants.py")

    with open(constants_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取关键词列表
    keywords_match = re.search(
        r"PREFILTER_REQUIRED_KEYWORDS.*?\[(.*?)\]",
        content,
        re.DOTALL,
    )

    if keywords_match:
        keywords_text = keywords_match.group(1)
        # 统计关键词数量（去除注释）
        keywords = [
            line.strip().strip('"').strip("'").rstrip(",")
            for line in keywords_text.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        keywords = [k for k in keywords if k]

        # 检查新增类别覆盖情况
        has_reasoning = any(
            "reasoning" in k.lower() or "math" in k.lower() for k in keywords
        )
        has_multimodal = any(
            "multimodal" in k.lower() or "vision" in k.lower() for k in keywords
        )
        has_knowledge = any(
            "knowledge" in k.lower() or "qa" in k.lower() for k in keywords
        )

        return {
            "total_keywords": len(keywords),
            "has_reasoning": has_reasoning,
            "has_multimodal": has_multimodal,
            "has_knowledge": has_knowledge,
            "sample_keywords": keywords[:10],
        }

    return {"total_keywords": 0}


def main():
    """主验证流程"""

    print(f"\n{'='*80}")
    print(f"BenchScope数据新鲜度验证报告")
    print(f"{'='*80}\n")

    # 1. 分析最近的日志
    log_dir = Path("logs")
    recent_logs = sorted(log_dir.glob("*.log"), reverse=True)[:3]

    print(f"📊 最近3次运行统计:\n")

    for i, log_file in enumerate(recent_logs, 1):
        stats = parse_log_file(log_file)
        date = log_file.stem

        print(f"{i}. {date}")
        print(f"   采集: arXiv={stats.get('arxiv_count', 0)} | "
              f"GitHub={stats.get('github_count', 0)} | "
              f"HF={stats.get('hf_count', 0)}")

        if 'prefilter_output' in stats:
            pre_out = stats.get('prefilter_output', 0)
            pre_in = stats.get('prefilter_input', 0)
            pre_rate = stats.get('prefilter_rate', 0.0)
            print(f"   预筛选: {pre_out}/{pre_in} (过滤率{pre_rate:.1f}%)")

        if 'score_success' in stats:
            score_succ = stats.get('score_success', 0)
            score_total = stats.get('score_total', 0)
            print(f"   评分: {score_succ}/{score_total}")
        print()

    # 2. 分析GitHub查询策略
    print(f"\n{'='*80}")
    print(f"🔍 GitHub采集器配置分析\n")
    print(f"{'='*80}\n")

    github_config = analyze_github_query_strategy()
    print(f"查询策略: {github_config['strategy']}")
    print(f"时间窗口: {github_config['lookback_days']}天")
    print(f"影响: {github_config['issue']}\n")

    # 3. 分析预筛选关键词
    print(f"{'='*80}")
    print(f"🔑 预筛选关键词分析\n")
    print(f"{'='*80}\n")

    keywords_config = analyze_prefilter_keywords()
    print(f"关键词总数: {keywords_config.get('total_keywords', 0)}")
    print(f"包含Reasoning类: {'✅' if keywords_config.get('has_reasoning') else '❌'}")
    print(f"包含Multimodal类: {'✅' if keywords_config.get('has_multimodal') else '❌'}")
    print(f"包含Knowledge类: {'✅' if keywords_config.get('has_knowledge') else '❌'}\n")

    sample_keywords = cast(List[str], keywords_config.get("sample_keywords", []))
    if sample_keywords:
        print(f"示例关键词: {', '.join(sample_keywords[:5])}\n")

    # 4. 综合诊断
    print(f"{'='*80}")
    print(f"🎯 综合诊断\n")
    print(f"{'='*80}\n")

    issues = []
    filter_rate = 0.0  # 默认0，避免未定义引用

    # 检查过滤率
    if recent_logs:
        latest_stats = parse_log_file(recent_logs[0])
        filter_rate = float(latest_stats.get('prefilter_rate', 0))

        if filter_rate > 80:
            issues.append(f"❌ 过滤率过高({filter_rate:.1f}%)，可能漏掉新学术工作")
        elif filter_rate < 50:
            issues.append(f"✅ 过滤率正常({filter_rate:.1f}%)")
        else:
            issues.append(f"⚠️ 过滤率偏高({filter_rate:.1f}%)，建议优化")

    # 检查GitHub策略
    if 'pushed:>=' in github_config['strategy']:
        issues.append("❌ GitHub使用pushed:>=，会采集swebench等老项目")
    elif 'created:>=' in github_config['strategy']:
        issues.append("✅ GitHub使用created:>=，只采集新项目")

    # 检查关键词覆盖
    if keywords_config.get('total_keywords', 0) < 50:
        issues.append(f"❌ 关键词过少({keywords_config.get('total_keywords')}个)，覆盖不足")
    elif keywords_config.get('total_keywords', 0) >= 70:
        issues.append(f"✅ 关键词充足({keywords_config.get('total_keywords')}个)")

    for issue in issues:
        print(issue)

    print(f"\n{'='*80}")
    print(f"📋 建议措施\n")
    print(f"{'='*80}\n")

    if filter_rate > 80:
        print("1. 扩充关键词列表（增加reasoning/multimodal/knowledge类别）")
        print("2. 将arXiv加入TRUSTED_SOURCES白名单，避免重复过滤")

    if 'pushed:>=' in github_config['strategy']:
        print("3. 修改GitHub查询策略：pushed:>= → created:>=")
        print("   或使用混合策略：新项目(created) + 活跃项目(pushed + created>6月)")

    print(f"\n详细优化方案见: .claude/specs/benchmark-intelligence-agent/CODEX-FILTER-OPTIMIZATION.md\n")


if __name__ == "__main__":
    main()
