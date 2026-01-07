"""
创建子智能体工具

基于 AgentScope 1.0 框架的 ReActAgent，集成了 Handoffs 工作流。
"""
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import ToolResponse, Toolkit, execute_python_code, execute_shell_command
from anthropic.types import TextBlock

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
            agent_name: 子 Agent 名称
            work_prompt: 子 Agent 的系统提示词
        """
    try:
        # 创建智能体
        toolkit = Toolkit()
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(execute_shell_command)
        worker = MyBaseReActAgent(
            name=f"Worker_{agent_name}",
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
        return ToolResponse(
            content=res.get_content_blocks("text"),
            metadata={
                "task_id": task_id,
                "success": True,
            }
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(type="text", text="任务失败")],
            metadata={
                "task_id": task_id,
                "success": False,
                "result": "",
                "error_message": str(e)
            },
            is_last=True
        )
