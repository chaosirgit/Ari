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
        print(msg,last)
        # msg 数据结构:
        # 主智能体回复 name==PROJECT_NAME ToolUseBlock 的 name == ‘_plan_task’ 输出 input 的 task_description 代表请求规划器
        # 流式打印 input 的 task_description
        # ```Msg(id='oY5N8mSLh2neaxaEvQoF3s', name='Ari', content=[{'type': 'tool_use', 'id': 'call_5164c8d8a8cb4b789f843541', 'name': '_plan_task', 'input': {}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:09.202', invocation_id='None') False
        # Msg(id='oY5N8mSLh2neaxaEvQoF3s', name='Ari', content=[{'type': 'tool_use', 'id': 'call_5164c8d8a8cb4b789f843541', 'name': '_plan_task', 'input': {}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:09.202', invocation_id='None') False
        # Msg(id='oY5N8mSLh2neaxaEvQoF3s', name='Ari', content=[{'type': 'tool_use', 'id': 'call_5164c8d8a8cb4b789f843541', 'name': '_plan_task', 'input': {'task_description': ''}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:09.202', invocation_id='None') False
        # Msg(id='oY5N8mSLh2neaxaEvQoF3s', name='Ari', content=[{'type': 'tool_use', 'id': 'call_5164c8d8a8cb4b789f843541', 'name': '_plan_task', 'input': {'task_description': '规划一个包含5个'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:09.202', invocation_id='None') False
        # Msg(id='oY5N8mSLh2neaxaEvQoF3s', name='Ari', content=[{'type': 'tool_use', 'id': 'call_5164c8d8a8cb4b789f843541', 'name': '_plan_task', 'input': {'task_description': '规划一个包含5个计算步骤的任务，其中3'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:09.202', invocation_id='None') False```
        # ...
        #
        # Planning name == Planning and last == true 时解析 TextBlock 的text内容,拿到 steps 作为计划列表 status 全是0 代表等待开始
        # 不流式打印
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```'}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') False
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```json\n{\n'}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') False
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```json\n{\n    "steps'}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') False
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```json\n{\n    "steps": [\n       '}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') False
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```json\n{\n    "steps": [\n        {\n            "task_id":'}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') False
        # ...
        # Msg(id='nBc84R4iJngpAfZFN4U4rz', name='Planning', content=[{'type': 'text', 'text': '```json\n{\n    "steps": [\n        {\n            "task_id": 1,\n            "task_name": "加法1",\n            "description": "计算 2 + 3",\n            "dependencies": [],\n            "status": 0\n        },\n        {\n            "task_id": 2,\n            "task_name": "加法2",\n            "description": "计算 6 + 3",\n            "dependencies": [],\n            "status": 0\n        },\n        {\n            "task_id": 3,\n            "task_name": "加法3",\n            "description": "计算 4 + 3",\n            "dependencies": [],\n            "status": 0\n        },\n        {\n            "task_id": 4,\n            "task_name": "乘法",\n            "description": "计算 2 * 5",\n            "dependencies": [],\n            "status": 0\n        },\n        {\n            "task_id": 5,\n            "task_name": "依赖加法",\n            "description": "计算 3 + 步骤4的结果",\n            "dependencies": [4],\n            "status": 0\n        }\n    ],\n    "execution_mode": "parallel"\n}\n```'}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:11.693', invocation_id='None') True
        #
        # 主智能体回复 name==PROJECT_NAME and ToolUseBlock 的 name == ‘create_worker’ 输出 input 的 work_prompt 代表正在给input.task_id号任务分配专家 此时更新steps[input.task_id] 的状态为 1 代表分配专家中
        # 流式打印 input 的 dask_description
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3', 'agent_name': '加法计算器'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3', 'agent_name': '加法计算器1'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3', 'agent_name': '加法计算器1', 'work_prompt': '你'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3', 'agent_name': '加法计算器1', 'work_prompt': '你是一个精准的数学计算'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # Msg(id='6m9pUF8xrvM2Ny9UEaiznf', name='Ari', content=[{'type': 'tool_use', 'id': 'call_b26bb2d1f4f64ca7b316e6a0', 'name': 'create_worker', 'input': {'task_id': 1, 'task_description': '计算 2 + 3', 'agent_name': '加法计算器1', 'work_prompt': '你是一个精准的数学计算专家。你的任务是执行'}}], role='assistant', metadata=None, timestamp='2026-01-08 13:39:17.527', invocation_id='None') False
        # ...
        #
        # 子智能体回复(专家回复) name==msg.name.startWith("Worker_") 的
        # task_id = 以 - 截取字符串,最后的是 task_id
        # 如果 !last 并且解析到 task_id. 代表正在工作. 更新steps[input.task_id] 的状态为 2 表示工作中.
        # 流式打印 TextBlock 的 Text
        # 如果 last 表示工作完成. 更新steps[input.task_id] 的状态为3 表示工作完成.并检查 steps 的数组中的所有{'status'} 是否都是 3.如果是 代表全部规划完成.
        # Msg(id='bLEqcW778ZeqkYNw2UUh5N', name='Worker_Addition_Calculator_1-1', content=[{'type': 'text', 'text': '5'}], role='assistant', metadata=None, timestamp='2026-01-08 14:42:03.921', invocation_id='None') False
        # Msg(id='bLEqcW778ZeqkYNw2UUh5N', name='Worker_Addition_Calculator_1-1', content=[{'type': 'text', 'text': '5'}], role='assistant', metadata=None, timestamp='2026-01-08 14:42:03.921', invocation_id='None') False
        # Msg(id='bLEqcW778ZeqkYNw2UUh5N', name='Worker_Addition_Calculator_1-1', content=[{'type': 'text', 'text': '5'}], role='assistant', metadata=None, timestamp='2026-01-08 14:42:03.921', invocation_id='None') False
        # Msg(id='bLEqcW778ZeqkYNw2UUh5N', name='Worker_Addition_Calculator_1-1', content=[{'type': 'text', 'text': '5'}], role='assistant', metadata=None, timestamp='2026-01-08 14:42:03.921', invocation_id='None') True
        # ...
        #
        #

        if last:
            print()  # 换行


if __name__ == "__main__":
    asyncio.run(main())