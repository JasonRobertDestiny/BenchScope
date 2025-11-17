"""验证所有Python模块导入"""
import sys

print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.executable}\n")

print("=" * 60)
print("检查核心依赖导入")
print("=" * 60)

modules = {
    'arxiv': 'arXiv API客户端',
    'httpx': 'HTTP客户端',
    'bs4': 'BeautifulSoup4 (HTML解析)',
    'openai': 'OpenAI API',
    'redis': 'Redis客户端',
    'feedparser': 'RSS/Atom解析器',
    'pydantic': '数据验证',
    'tenacity': '重试机制',
    'yaml': 'YAML解析 (PyYAML)',
    'dotenv': 'python-dotenv',
    'huggingface_hub': 'HuggingFace Hub',
}

success_count = 0
fail_count = 0

for mod_name, description in modules.items():
    try:
        __import__(mod_name)
        print(f"✓ {mod_name:20} - {description}")
        success_count += 1
    except ImportError as e:
        print(f"✗ {mod_name:20} - {description} ({e})")
        fail_count += 1

print("\n" + "=" * 60)
print(f"结果: {success_count} 成功, {fail_count} 失败")
print("=" * 60)

if fail_count > 0:
    print("\n⚠️ 部分模块缺失，请运行: .venv/bin/python -m pip install -r requirements.txt")
    sys.exit(1)
else:
    print("\n✅ 所有核心依赖已正确安装")
    sys.exit(0)
