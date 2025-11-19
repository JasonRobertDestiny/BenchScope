"""测试全局配置，确保 src 模块可被导入。"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # 添加仓库根目录，允许 `import src.*`
    sys.path.insert(0, str(PROJECT_ROOT))
