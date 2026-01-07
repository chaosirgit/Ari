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


async def creat_worker(
        task_description: str,
        agent_name: str,
        work_prompt: str
) -> ToolResponse:
    """
        创建子 Agent 来完成具体的任务.

        Args:
            task_description: 任务描述
            agent_name: 子 Agent 名称
            work_prompt: 子 Agent 的系统提示词
        """

    # 创建智能体
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(execute_shell_command)
    worker = MyBaseReActAgent(
        name=agent_name,
        sys_prompt=work_prompt,
        model=OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
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


from core.lib.my_base_agent_lib import MyBaseReActAgent
