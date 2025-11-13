#!/bin/bash
# BenchScope环境激活脚本 - 确保uv环境纯净，不受conda干扰

# 如果在conda环境中，先退出
if [[ ! -z "$CONDA_PREFIX" ]]; then
    echo "检测到conda环境，正在退出..."
    eval "$(conda shell.bash hook)"
    while [[ ! -z "$CONDA_PREFIX" ]]; do
        conda deactivate 2>/dev/null || break
    done
fi

# 激活uv环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✓ uv环境已激活"
    echo "Python: $(which python)"
    echo "版本: $(python --version)"
else
    echo "✗ .venv目录不存在，请先运行: uv venv"
    exit 1
fi
