"""
Ari 主入口文件。
"""

import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 确保内存目录存在
memory_dirs = [
    os.getenv("MEMORY_PATH", "./memory/vector_store"),
    os.getenv("EMBEDDING_CACHE_DIR", "./memory/embedding_cache")
]

for dir_path in memory_dirs:
    os.makedirs(dir_path, exist_ok=True)

from ui.app import AriApp


def main():
    """启动Ari应用程序"""
    app = AriApp()
    app.run()


if __name__ == "__main__":
    main()