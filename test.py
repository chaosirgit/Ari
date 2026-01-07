import asyncio
import json

from agentscope.message import Msg

import utils
from config import PROJECT_NAME
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent


async def main():
    GlobalAgentRegistry._agents.clear()
    steps = []
    # 初始化主 Agent
    ari = MainReActAgent()

    # 创建用户消息对象
    user_msg = Msg(
        name="user",
        content="我现在要测试一下多智能体的并行运行,你让规划Agent规划 5 个步骤, 2个有依赖,3个无依赖,比如,3个分别计算2+3,6+3,4+3,两个有依赖的计算 3 + 2 * 5",
        role="user"
    )
    async for msg, last in GlobalAgentRegistry.stream_all_messages(
            main_task=ari(user_msg),
    ):
        # 主Agent思考
        if msg.name == PROJECT_NAME and msg.role == "assistant" and msg.has_content_blocks("thinking"):
            print("🤔Ari:",msg.get_content_blocks("thinking"))
        # 主 Agent 回答
        if msg.name == PROJECT_NAME and msg.role == "assistant" and (msg.has_content_blocks("text") or msg.has_content_blocks("tool_use")):
            if msg.has_content_blocks("tool_use"):
                print("🤖Ari:",msg.get_content_blocks("tool_use"))
            else:
                print("🤖Ari:",msg.get_content_blocks("text"))
        # 规划 Agent 完成规划
        if msg.name == "Planning" and msg.role == "assistant" and msg.has_content_blocks("text") and last:
            plan_str = utils.extract_json_from_response(msg.get_content_blocks("text"))
            print(plan_str)
            plan = json.loads(plan_str)
            steps = plan.get("steps")
            print("📅Planning:","已完成规划")
            print("一共 ",len(steps)," 个步骤")
            for p in steps:
                print(f"{p.get("task_id")}:{p.get("task_name")}-等待开始")
        # 子 Agent 思考
        if msg.name.startswith("Worker_") and msg.role == "assistant" and msg.has_content_blocks("thinking"):
            # 更新步骤状态-正在思考
            steps[msg.metadata["task_id"]]["status"] = 1
            print(f"🧑‍🌾{msg.name.removeprefix("Worker_")}: {msg.get_content_blocks('thinking')}")

        # 子 Agent 回答
        if msg.name.startswith("Worker_") and msg.role == "assistant" and msg.has_content_blocks("text"):
            # 更新任务状态-正在回答
            steps[msg.metadata["task_id"]]["status"] = 2
            print(f"🧑‍🌾{msg.name.removeprefix("Worker_")}: {msg.get_content_blocks('text')}")
            if last:
                # 更新任务状态-执行完毕(任务完成)
                if msg.metadata["success"]:
                    steps[msg.metadata["task_id"]]["status"] = 3
                # 更新任务状态-执行完毕(任务失败)
                else:
                    steps[msg.metadata["task_id"]]["status"] = 4
                # 所有任务执行完毕
                if all(p.get("status") in [3, 4] for p in steps) and steps:
                    print("所有任务已执行,等待汇总...")

        if last:
            print()


if __name__ == "__main__":
    asyncio.run(main())