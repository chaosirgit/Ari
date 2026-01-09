"""
Ari 主应用程序入口文件
集成 Textual UI 和多智能体逻辑
"""
import asyncio

import agentscope
from agentscope.message import Msg

from core.main_agent import MainReActAgent


async def main():
    """主函数"""
    msg = Msg(
        role="user",
        content="我是谁?",
        name="user"
    )
    ari = MainReActAgent()
    response = await ari(msg)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())