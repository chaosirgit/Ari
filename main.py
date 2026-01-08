"""
Ari 主应用程序入口文件
集成 Textual UI 和多智能体逻辑
"""
import asyncio
import os
import sys
import logging

# 设置文件日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "ari_debug.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import AriApp


def main():
    """主函数"""
    print("🚀 启动 Ari - 自主认知型AI实体")
    print("💡 使用 Ctrl+Q 退出应用")
    print("🛑 使用 Ctrl+C 中断智能体")
    print("🧹 使用 Ctrl+L 清空输出")
    print("-" * 50)
    print(f"📝 调试日志将写入: {log_file}")
    
    # 启动 Textual 应用
    app = AriApp()
    app.run()


if __name__ == "__main__":
    main()