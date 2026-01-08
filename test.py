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
        # 提取文本内容用于打印
        text_content = ""
        if isinstance(msg.content, list):
            for block in msg.content:
                if block.get("type") == "text":
                    text_content = block.get("text", "")
                    break

        # 处理不同类型的Agent消息
        if msg.name == PROJECT_NAME:  # 主Agent (Ari)
            # 检查是否是工具调用
            if isinstance(msg.content, list) and len(msg.content) > 0:
                first_block = msg.content[0]
                if first_block.get("type") == "tool_use":
                    tool_name = first_block.get("name")
                    tool_input = first_block.get("input", {})

                    if tool_name == "_plan_task":
                        # 规划任务请求 - 流式打印 task_description
                        task_desc = tool_input.get("task_description", "")
                        if task_desc:
                            print(f"\r规划任务: {task_desc}", end="", flush=True)

                    elif tool_name == "create_worker":
                        # 创建子Agent - 流式打印 task_description
                        task_desc = tool_input.get("task_description", "")
                        task_id = tool_input.get("task_id")
                        if task_desc and task_id is not None:
                            print(f"\r分配专家给任务 {task_id}: {task_desc}", end="", flush=True)

                            # 更新任务状态为1 (分配专家中)
                            if steps and task_id <= len(steps):
                                steps[task_id - 1]["status"] = 1

        elif msg.name == "Planning":  # 规划Agent
            if last and text_content:
                # 完整的规划结果，解析JSON
                try:
                    # 提取JSON内容（去除```标记）
                    json_start = text_content.find("{")
                    json_end = text_content.rfind("}") + 1
                    if json_start != -1 and json_end != -1:
                        json_str = text_content[json_start:json_end]
                        planning_result = json.loads(json_str)
                        steps = planning_result.get("steps", [])
                        planning_completed = True

                        # 打印规划结果
                        print(f"\n\n规划完成! 共 {len(steps)} 个步骤:")
                        for i, step in enumerate(steps):
                            deps = step.get("dependencies", [])
                            dep_str = f" (依赖: {deps})" if deps else ""
                            print(f"  {i+1}. {step['task_name']}: {step['description']}{dep_str}")
                        print()

                except json.JSONDecodeError as e:
                    print(f"\n规划结果解析失败: {e}")
                    print(f"原始内容: {text_content}")

        elif msg.name.startswith("Worker_"):  # 子Agent (专家)
            # 从名字中提取 task_id (格式: Worker_xxx-task_id)
            try:
                task_id_str = msg.name.split("-")[-1]
                task_id = int(task_id_str)

                if not last:
                    # 工作中 - 流式打印
                    if text_content:
                        print(f"\r任务 {task_id} 执行中: {text_content}", end="", flush=True)

                    # 更新任务状态为2 (工作中)
                    if steps and task_id <= len(steps):
                        steps[task_id - 1]["status"] = 2

                else:
                    # 工作完成
                    if text_content:
                        print(f"\r任务 {task_id} 完成: {text_content}")

                    # 更新任务状态为3 (完成)
                    if steps and task_id <= len(steps):
                        steps[task_id - 1]["status"] = 3

                    # 检查是否所有任务都完成了
                    if steps and all(step["status"] == 3 for step in steps):
                        print("\n🎉 所有任务执行完成!")

            except (ValueError, IndexError):
                # 如果无法解析task_id，直接打印内容
                if text_content:
                    print(f"\r{msg.name}: {text_content}", end="" if not last else "\n", flush=True)

        else:
            # 其他消息类型
            if text_content:
                print(f"\r{msg.name}: {text_content}", end="" if not last else "\n", flush=True)

        if last:
            print()  # 换行        if last:
            print()  # 换行


if __name__ == "__main__":
    asyncio.run(main())