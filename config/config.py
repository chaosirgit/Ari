"""
配置加载
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
PROJECT_NAME = os.getenv("PROJECT_NAME", "Ari")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

MEMORY_PATH = os.getenv("MEMORY_PATH", "./memory/vector_store")
EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", "./memory/embedding_cache")

# ========== 配置日志 ==========
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('logs/debug_log.log', mode='w', encoding='utf-8'),
    ]
)

logger = logging.getLogger(__name__)