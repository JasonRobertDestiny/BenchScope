#!/usr/bin/env python3
"""
BenchScope 配置验证脚本
运行此脚本验证所有配置是否正确
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_redis():
    """验证Redis连接"""
    print("1. 检查Redis连接...")
    try:
        import redis.asyncio as redis
        import asyncio

        async def test():
            client = redis.from_url("redis://localhost:6379")
            await client.ping()
            await client.aclose()

        asyncio.run(test())
        print("   ✓ Redis连接成功")
        return True
    except Exception as e:
        print(f"   ✗ Redis连接失败: {e}")
        print("   → 请运行: docker run -d -p 6379:6379 redis:7-alpine")
        return False


def check_config():
    """验证配置文件"""
    print("2. 检查配置文件...")
    try:
        from src.config import get_settings

        settings = get_settings()

        # 检查OpenAI配置
        if not settings.openai.api_key:
            print("   ✗ OPENAI_API_KEY 未配置")
            return False
        print(f"   ✓ OpenAI API Key: {settings.openai.api_key[:10]}...")
        print(f"   ✓ OpenAI Base URL: {settings.openai.base_url}")
        print(f"   ✓ OpenAI Model: {settings.openai.model}")

        # 检查飞书配置
        if not settings.feishu.app_id:
            print("   ✗ FEISHU_APP_ID 未配置")
            return False
        print(f"   ✓ 飞书 App ID: {settings.feishu.app_id}")

        if settings.feishu.bitable_app_token.startswith("bascn_PLEASE"):
            print("   ✗ FEISHU_BITABLE_APP_TOKEN 未配置")
            return False
        print(f"   ✓ 飞书表格 app_token: {settings.feishu.bitable_app_token[:20]}...")
        print(f"   ✓ 飞书表格 table_id: {settings.feishu.bitable_table_id}")

        if settings.feishu.webhook_url:
            print(f"   ✓ 飞书 Webhook: {settings.feishu.webhook_url[:50]}...")

        print("   ✓ 配置文件验证通过")
        return True
    except Exception as e:
        print(f"   ✗ 配置加载失败: {e}")
        return False


def check_dependencies():
    """验证依赖安装"""
    print("3. 检查依赖包...")
    required = [
        "arxiv",
        "httpx",
        "beautifulsoup4",
        "openai",
        "redis",
        "tenacity",
        "dotenv",
    ]

    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"   ✓ {pkg}")
        except ImportError:
            print(f"   ✗ {pkg} 未安装")
            missing.append(pkg)

    if missing:
        print(f"\n   → 请运行: pip install {' '.join(missing)}")
        return False

    print("   ✓ 所有依赖已安装")
    return True


def check_structure():
    """验证项目结构"""
    print("4. 检查项目结构...")
    required_files = [
        "src/models.py",
        "src/config.py",
        "src/main.py",
        "src/collectors/arxiv_collector.py",
        "src/collectors/github_collector.py",
        "src/collectors/pwc_collector.py",
        "src/prefilter/rule_filter.py",
        "src/scorer/llm_scorer.py",
        "src/scorer/rule_scorer.py",
        "src/storage/feishu_storage.py",
        "src/storage/sqlite_fallback.py",
        "src/storage/storage_manager.py",
        "src/notifier/feishu_notifier.py",
        ".env.local",
        "requirements.txt",
    ]

    missing = []
    for file in required_files:
        path = Path(__file__).parent.parent / file
        if path.exists():
            print(f"   ✓ {file}")
        else:
            print(f"   ✗ {file} 不存在")
            missing.append(file)

    if missing:
        print(f"\n   → 缺少 {len(missing)} 个文件，请检查项目结构")
        return False

    print("   ✓ 项目结构完整")
    return True


def main():
    """运行所有检查"""
    print("=" * 60)
    print("BenchScope 配置验证")
    print("=" * 60)
    print()

    checks = [
        check_dependencies,
        check_redis,
        check_config,
        check_structure,
    ]

    results = [check() for check in checks]

    print()
    print("=" * 60)
    if all(results):
        print("✓ 所有检查通过！可以运行: python -m src.main")
    else:
        print("✗ 部分检查失败，请根据上述提示修复")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
