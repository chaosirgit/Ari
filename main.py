"""
Ari 主应用程序入口文件
集成 Textual UI 和多智能体逻辑
"""
import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import AriApp


def main():
    """主函数"""
    print("🚀 启动 Ari - 自主认知型AI实体")
    print("💡 使用 Ctrl+C 退出应用")
    print("🧹 使用 Ctrl+L 清空输出")
    print("-" * 50)
    
    # 启动 Textual 应用
    app = AriApp()
    app.run()


if __name__ == "__main__":
    main()