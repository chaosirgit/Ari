"""
创建子智能体工具

基于 AgentScope 1.0 框架的 ReActAgent，集成了 Handoffs 工作流。
"""
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import ToolResponse, Toolkit, execute_python_code, execute_shell_command

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME


async def create_worker(
        task_description: str,
        agent_name: str,
        work_prompt: str
) -> ToolResponse:
    """
        当需要创建子智能体 (`create_worker`) 时，你必须为其构建一个**精准、强大的系统提示词 (`work_prompt`)**。
        这个 `work_prompt` 必须明确告知子智能体：
            a. **其专业角色** (例如：“你是世界顶尖的食材准备顾问”)。
            b. **其在此上下文中的成功标准**。这取决于任务的本质和系统的当前能力：
                - **若任务可被指导** (如烹饪、写作)：要求子智能体提供**详尽、清晰、可操作的步骤指南**。
                - **若任务需模拟或构想** (如设计、规划未来场景)：要求子智能体在**理想化的假设下，生成一个完美、完整的解决方案或结果描述**。
                - **若任务在未来可能被执行**：要求子智能体**同时提供执行方案和理想化的预期结果**。
        你的目标是让每个子智能体都能在其被赋予的角色和上下文中，发挥出最大的价值，并返回对用户最有用的信息。

        Args:
            task_description: 任务描述
            agent_name: 子 Agent 名称
            work_prompt: 子 Agent 的系统提示词
        """

    # 创建智能体
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(execute_shell_command)
    worker = ReActAgent(
        name=agent_name,
        sys_prompt=work_prompt,
        model=OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={
                "base_url": LLM_BASE_URL,
            },
            model_name=LLM_MODEL_NAME,
            stream=False,
        ),
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
    )
    res = await worker(Msg("user", task_description, "user"))
    return ToolResponse(
        content=res.get_content_blocks("text"),
    )
