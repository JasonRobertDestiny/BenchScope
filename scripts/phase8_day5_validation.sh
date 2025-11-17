#!/bin/bash
# Phase 8 Day 5 完整验证脚本
# 执行时间: 2025-11-17
# 目标: 验证PDF增强功能并获取真实数据

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Phase 8 Day 5 完整验证开始"
echo "=========================================="
echo ""

# ============ Step 0: 环境检查 ============
echo "[Step 0] 环境检查..."

# 检查虚拟环境
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ 虚拟环境未激活，正在激活..."
    source .venv/bin/activate
else
    echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"
fi

# 检查关键依赖
echo "检查关键依赖..."
.venv/bin/python -c "from src.enhancer import PDFEnhancer; print('✅ PDFEnhancer')"
.venv/bin/python -c "from scipdf.pdf import parse_pdf_to_dict; print('✅ scipdf_parser')"
.venv/bin/python -c "import arxiv; print('✅ arxiv')"

# 检查环境变量
echo ""
echo "检查环境变量配置..."
if grep -q "OPENAI_API_KEY=" .env.local 2>/dev/null; then
    echo "✅ OPENAI_API_KEY 已配置"
else
    echo "❌ OPENAI_API_KEY 未配置"
    exit 1
fi

if grep -q "FEISHU_APP_ID=" .env.local 2>/dev/null; then
    echo "✅ FEISHU_APP_ID 已配置"
else
    echo "⚠️  FEISHU_APP_ID 未配置（可选）"
fi

echo ""
echo "=========================================="
echo "[Step 1] GROBID服务检查"
echo "=========================================="

# 检查GROBID服务是否可用
if curl -s http://localhost:8070/api/version > /dev/null 2>&1; then
    echo "✅ GROBID服务运行中 (localhost:8070)"
    GROBID_VERSION=$(curl -s http://localhost:8070/api/version | head -1)
    echo "   版本: $GROBID_VERSION"
elif [ -n "$GROBID_URL" ]; then
    echo "✅ 使用云端GROBID: $GROBID_URL"
else
    echo "⚠️  GROBID服务未启动，PDF解析将失败"
    echo ""
    echo "启动GROBID (二选一):"
    echo "  选项A: docker run -t --rm -p 8070:8070 grobid/grobid:0.8.0"
    echo "  选项B: export GROBID_URL=https://kermitt2-grobid.hf.space"
    echo ""
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "[Step 2] 运行单元测试"
echo "=========================================="

echo "运行 PDFEnhancer 单元测试..."
.venv/bin/python -m pytest tests/test_pdf_enhancer.py -v --tb=short

if [ $? -eq 0 ]; then
    echo "✅ 单元测试通过"
else
    echo "❌ 单元测试失败"
    read -p "是否继续完整流程? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "[Step 3] 运行完整流程（重要！）"
echo "=========================================="

# 创建日志目录
mkdir -p logs exports

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/phase8_validation_${TIMESTAMP}.log"

echo "日志将保存到: $LOG_FILE"
echo "开始运行主流程..."
echo ""

# 运行主流程，同时输出到终端和日志文件
.venv/bin/python -m src.main 2>&1 | tee "$LOG_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 完整流程执行成功"
else
    echo ""
    echo "❌ 完整流程执行失败，请检查日志: $LOG_FILE"
    exit 1
fi

echo ""
echo "=========================================="
echo "[Step 4] 数据质量分析"
echo "=========================================="

QUALITY_LOG="logs/phase8_data_quality_${TIMESTAMP}.log"
echo "数据质量报告将保存到: $QUALITY_LOG"
echo ""

.venv/bin/python scripts/analyze_data_quality.py 2>&1 | tee "$QUALITY_LOG"

echo ""
echo "=========================================="
echo "[Step 5] 提取关键指标"
echo "=========================================="

echo "从日志中提取关键性能指标..."
echo ""

# 提取PDF增强统计
echo "【PDF增强统计】"
grep -A 2 "PDF内容增强" "$LOG_FILE" || echo "未找到PDF增强日志"

# 提取LLM评分统计
echo ""
echo "【LLM评分统计】"
grep -A 2 "LLM评分" "$LOG_FILE" || echo "未找到LLM评分日志"

# 提取总体时间
echo ""
echo "【执行时间】"
grep "BenchScope.*启动\|BenchScope.*完成" "$LOG_FILE" || echo "未找到时间日志"

echo ""
echo "=========================================="
echo "验证完成！"
echo "=========================================="
echo ""
echo "生成的文件："
echo "  - 主流程日志: $LOG_FILE"
echo "  - 数据质量报告: $QUALITY_LOG"
echo ""
echo "下一步："
echo "  1. 查看飞书表格验证数据: https://deepwisdom.feishu.cn/base/SbIibGBIWayQncslz5kcYMnrnGf?table=tblG5cMwubU6AJcV&view=vewUfT4GO6"
echo "  2. 填写报告: docs/phase8-pdf-enhancement-report.md"
echo "  3. 将日志文件发送给Claude Code进行分析"
echo ""
