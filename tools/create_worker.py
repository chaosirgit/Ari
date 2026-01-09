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
    创建并执行子智能体来完成特定任务。

    **失败处理策略**：
    - 子智能体应在其系统提示词(work_prompt)中包含明确的失败处理指导
    - 如果子智能体无法完成任务，应返回清晰的失败原因和相关信息
    - 本工具不进行重试，任何执行失败都会立即返回"任务失败"结果
    - 主调用方(主Agent)应根据返回结果决定后续处理，不应无限重试

    Args:
        task_id: Planning Task ID
        task_description: 任务描述
        agent_name: 子 Agent 名称 注意:不要包含 `task_id`
        work_prompt: 子 Agent 的系统提示词（应包含失败处理指导）

    Returns:
        ToolResponse: 包含子智能体执行结果或失败信息
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
        # 提供更详细的错误信息，便于调试和用户理解
        error_message = f"❌ 任务 {task_id} 执行失败: {str(e)}"
        return ToolResponse(
            content=[TextBlock(type="text", text=error_message)],
            is_last=True
        )