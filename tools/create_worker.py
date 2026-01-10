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
from tools.ex_insert_text_file import ex_insert_text_file
from tools.ex_view_text_file import ex_view_text_file
from tools.ex_write_text_file import ex_write_text_file


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
        # 🔒 方案3：在 work_prompt 中添加失败处理指导
        enhanced_work_prompt = f"""{work_prompt}

🚨 **失败处理规则（重要）**：
- 如果任务无法完成或遇到错误，你的回复必须以 "❌ 任务失败" 开头
- 然后详细说明失败原因和相关信息
- 不要尝试掩饰或美化失败结果
- 示例失败回复格式：
  ❌ 任务失败：除数为0，这是数学上未定义的操作。错误类型：ZeroDivisionError

现在开始执行任务。
"""

        # 创建智能体
        toolkit = Toolkit()
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(ex_view_text_file)
        toolkit.register_tool_function(ex_write_text_file)
        toolkit.register_tool_function(ex_insert_text_file)

        worker = MyBaseReActAgent(
            name=f"Worker_{agent_name}-{task_id}",
            sys_prompt=enhanced_work_prompt,  # 🔒 使用增强后的 prompt
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
            max_iters=20
        )
        res = await worker(Msg("user", task_description, "user"))

        # 确保正确处理文本内容
        if isinstance(res.content, str):
            content_blocks = [TextBlock(type="text", text=res.content)]
        else:
            content_blocks = res.get_content_blocks("text")

        # 🔒 方案1：判断任务是否失败
        result_text = res.content if isinstance(res.content, str) else "".join(
            block.text for block in content_blocks if hasattr(block, 'text')
        )

        is_failed = _is_task_failed(result_text)

        # 🔒 方案1：返回带有状态标记的 ToolResponse
        return ToolResponse(
            content=content_blocks,
            metadata={
                "task_id": task_id,
                "status": "failed" if is_failed else "success"
            }
        )

    except Exception as e:
        # 提供更详细的错误信息，便于调试和用户理解
        error_message = f"❌ 任务 {task_id} 执行失败: {str(e)}"
        return ToolResponse(
            content=[TextBlock(type="text", text=error_message)],
            metadata={
                "task_id": task_id,
                "status": "failed"
            }
        )


def _is_task_failed(text_content: str) -> bool:
    """
    判断任务是否失败（基于关键词检测）

    Args:
        text_content: 任务结果文本

    Returns:
        bool: True 表示失败，False 表示成功
    """
    # 🔒 失败关键词列表（中英文）
    failure_keywords = [
        # 中文关键词
        "失败", "错误", "异常", "无法", "不能", "未能",
        "未定义", "不支持", "无效", "拒绝", "超时",

        # 英文关键词
        "error", "failed", "failure", "exception", "unable",
        "cannot", "can't", "could not", "couldn't",

        # Python 异常类型
        "zerodivisionerror", "valueerror", "typeerror",
        "keyerror", "indexerror", "attributeerror",
        "nameerror", "runtimeerror", "ioerror",

        # 失败标记符号
        "❌", "✗", "[失败]", "[错误]", "[异常]"
    ]

    text_lower = text_content.lower()

    # 检查是否包含失败关键词
    for keyword in failure_keywords:
        if keyword in text_lower:
            return True

    return False
