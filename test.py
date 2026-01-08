import asyncio
import json

from agentscope.message import Msg

import config
import utils
from config import PROJECT_NAME
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent


async def main():
    GlobalAgentRegistry._agents.clear()
    steps = []
    planning_completed = False

    # 初始化主 Agent
    ari = MainReActAgent()

    # 创建用户消息对象
    user_msg = Msg(
        name="user",
        content="我现在要测试一下多智能体的并行运行,你让规划Agent规划 5 个步骤, 2个有依赖,3个无依赖,比如,3个分别计算2+3,6+3,4+3,两个有依赖的计算 3 + 2 * 5",
        role="user"
    )

    # GlobalAgentRegistry.stream_all_messages 已确认拿到数据,以下注释中写有数据例子

    async for msg, last in GlobalAgentRegistry.stream_all_messages(
            main_task=ari(user_msg),
    ):
        config.logger.info(f"msg:{msg}, last:{last}")


if __name__ == "__main__":
    asyncio.run(main())