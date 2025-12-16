#!/bin/bash
# BenchScope 开发环境初始化脚本

set -e

echo "=== BenchScope 开发环境初始化 ==="

# 0. 配置代理（WSL2环境需要）
export http_proxy=http://172.21.224.1:10809
export https_proxy=http://172.21.224.1:10809
export HTTP_PROXY=http://172.21.224.1:10809
export HTTPS_PROXY=http://172.21.224.1:10809
echo "代理已配置: $http_proxy"

# 1. 确认工作目录
cd "$(dirname "$0")"
echo "工作目录: $(pwd)"

# 2. 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3.11 -m venv .venv
fi

# 3. 激活并检查依赖
source .venv/bin/activate
echo "Python: $(which python)"

# 4. 检查环境变量
if [ ! -f ".env.local" ]; then
    echo "警告: .env.local 不存在，请配置环境变量"
fi

# 5. 快速健康检查
echo "运行健康检查..."
python -c "from src.config import get_settings; print('配置加载: OK')" 2>/dev/null || echo "配置加载: 需要检查"

echo "=== 初始化完成 ==="
