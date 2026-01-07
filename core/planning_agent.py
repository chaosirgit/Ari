"""
Ari 规划智能体实现模块。

此智能体专门负责接收复杂任务，并将其拆解为结构化的、可执行的步骤列表。
"""
from typing import Any, List, Dict
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME

# 继承自我们自定义的基类，以获得流式消息捕获能力
from core.lib.my_base_agent_lib import MyBaseReActAgent


class PlanningReActAgent(MyBaseReActAgent):
    """
    专门用于任务规划的 ReAct 智能体。

    它接收一个高层次的任务描述，并输出一个包含详细步骤和依赖关系的 JSON 结构。
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        初始化规划智能体。
        """
        name = "PlanningAgent"
        sys_prompt = """
你是一个专业的任务规划专家。你的唯一职责是将用户提供的复杂任务分解为一系列清晰、原子化、可执行的步骤。

请严格遵守以下输出格式要求：

1.  **分析任务**：理解任务的核心目标和约束。
2.  **拆解步骤**：将任务分解为逻辑上连贯的子步骤。每个步骤应该是单一、明确的动作。
3.  **定义依赖**：明确指出每个步骤所依赖的前置步骤（通过步骤ID引用）。如果没有依赖，则依赖列表为空。
4.  **确定模式**：判断所有步骤是必须串行执行（"serial"），还是可以并行执行（"parallel"）。

**最终输出必须是一个严格的 JSON 字符串，且仅包含以下结构**：
```json
{
    "steps": [
        {
            "id": 1,
            "description": "步骤一的具体描述",
            "dependencies": []
        },
        {
            "id": 2,
            "description": "步骤二的具体描述",
            "dependencies": [1]
        }
    ],
    "execution_mode": "serial"
}
```

- `id` 必须是从1开始的连续整数。
- `description` 应该足够详细，以便另一个智能体能独立执行该步骤。
- `dependencies` 是一个整数列表，列出所有前置步骤的 `id`。
- `execution_mode` 只能是 "serial" 或 "parallel"。

请直接输出这个 JSON 字符串，不要包含任何其他解释、Markdown 代码块或前缀/后缀文本。
        """
        model = OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
            model_name=LLM_MODEL_NAME,
            stream=False, # 规划过程不需要流式
        )
        formatter = OpenAIChatFormatter()
        memory = InMemoryMemory()

        super().__init__(
            name=name,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            memory=memory,
            **kwargs,
        )