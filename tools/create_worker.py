"""
创建子智能体工具

基于 AgentScope 1.0 框架的 ReActAgent，集成了 Handoffs 工作流。
"""
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg, TextBlock
from agentscope.model import OpenAIChatModel
from agentscope.tool import ToolResponse, Toolkit, execute_python_code, execute_shell_command

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
from core.lib.my_base_agent_lib import MyBaseReActAgent


async def create_worker(
        task_id: int,
        task_description: str,
        agent_name: str,
        work_prompt: str
) -> ToolResponse:
    """
        你是专业的子智能体,你的目标是完美的完成派发给你的任务.

        Args:
            task_id: Planning Task ID
            task_description: 任务描述
            agent_name: 子 Agent 名称 注意:不要包含 `task_id`
            work_prompt: 子 Agent 的系统提示词
        """
    try:
        # 创建智能体
        toolkit = Toolkit()
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(execute_shell_command)
        worker = MyBaseReActAgent(
            name=f"Worker_{agent_name}-{task_id}",
            sys_prompt=work_prompt,
            model=OpenAIChatModel(
                api_key=LLM_API_KEY,
                client_kwargs={
                    "base_url": LLM_BASE_URL,
                },
                model_name=LLM_MODEL_NAME,
                stream=True,
            ),
            formatter=OpenAIChatFormatter(),
            toolkit=toolkit,
        )
        res = await worker(Msg("user", task_description, "user"))
        # 确保正确处理文本内容
        if isinstance(res.content, str):
            content_blocks = [TextBlock(type="text", text=res.content)]
        else:
            content_blocks = res.get_content_blocks("text")

        return ToolResponse(
            content=content_blocks
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(type="text", text="任务失败")],
            is_last=True
        )
