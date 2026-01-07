"""
任务规划器工具

基于 AgentScope 1.0 框架的 ReActAgent，集成了 Handoffs 工作流。
"""
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import ToolResponse, Toolkit, execute_python_code, execute_shell_command

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from core.lib.my_base_agent_lib import MyBaseReActAgent


async def task_decomposer(
        task_description: str,
) -> ToolResponse:
    """
    将复杂任务分解为结构化的计划。
        Args:
            task_description: 任务描述
    """
    # 使用 LLM 来分解任务
    decomposition_prompt = f"""
            你是一个任务规划专家。请将以下复杂任务分解为一系列有序的子任务。
            每个子任务应该是独立的、可执行的，并且有明确的输入输出。

            复杂任务: {task_description}

            请以 JSON 格式返回，包含以下字段：
            - "plan_name": 计划名称 (简短概括)
            - "plan_description": 计划详细描述 (主要目标)
            - "plan_expected_outcome": 计划期望的最终结果
            - "subtasks": 子任务列表，每个子任务包含:
              - "name": 子任务名称 (简短描述)
              - "description": 子任务详细描述
              - "agent_type": 推荐的Agent类型 ("general", "math", "search", "coding", "analysis")
              - "expected_output": 期望的输出格式
              - "dependencies": 依赖的子任务名称列表 (可选)

            确保子任务之间有合理的依赖关系，并且能够按顺序执行。

            ⚠️ 重要：请直接返回纯JSON，不要使用Markdown代码块包裹（不要用```json```）。
            """

    # 创建智能体
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(execute_shell_command)
    decomposer = MyBaseReActAgent(
        name="Task Decomposer",
        sys_prompt=decomposition_prompt,
        model=OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
            model_name=LLM_MODEL_NAME,
            stream=False,
        ),
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
    )
    res = await decomposer(Msg("user", task_description, "user"))
    return ToolResponse(
        content=res.get_content_blocks("text"),
    )
