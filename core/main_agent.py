"""
Ari 主智能体实现模块。

基于 AgentScope 1.0 框架的 ReActAgent，集成了长期记忆
"""

from typing import Any, Dict, List
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit, ToolResponse
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.embedding import OpenAITextEmbedding, FileEmbeddingCache
from agentscope.message import Msg, TextBlock
from mem0.vector_stores.configs import VectorStoreConfig
from core.planning_agent import PlanningReActAgent
from core.lib.my_base_agent_lib import MyBaseReActAgent

# 导入协调者提供的 create_worker 工具
from tools.create_worker import create_worker

from config import (
    PROJECT_NAME,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_CACHE_DIR,
    EMBEDDING_DIMENSION,
    LLM_API_KEY,
    LLM_MODEL_NAME,
    LLM_BASE_URL, MEMORY_PATH,
)


class MainReActAgent(MyBaseReActAgent):
    """
    Ari 主智能体类。

    负责接收用户请求，分析任务类型（聊天或复杂任务），
    拥有长期记忆功能，并能通过 Handoffs 机制调用子 Agent。
    """

    def __init__(
            self,
            **kwargs: Any,
    ) -> None:
        """
        初始化 Ari 主智能体。

        Args:
            name: 智能体名称
            sys_prompt: 系统提示词
        """
        name = PROJECT_NAME
        sys_prompt = """
        你是一个名为 **Ari** 的自主认知型AI实体。你的核心使命是高效、可靠地协助用户完成任何请求。你具备深度任务分解、持久化认知和动态协作的能力。

        ### 核心行为准则

        1.  **能力自省 (Capability Introspection)**:
            *   你清楚自己的能力边界由当前可用的工具集 (`toolkit`) 和上下文环境共同定义。
            *   对于任何子任务，首先判断是否有直接可用的工具可以执行。如果有，请优先使用工具。
            *   如果没有直接工具，则进入“专家委派”模式。

        2.  **专家委派 (Expert Delegation)**:
            *   当需要创建子智能体 (`create_worker`) 时，你必须为其构建一个**精准、强大的系统提示词 (`work_prompt`)**。
            *   这个 `work_prompt` 必须明确告知子智能体：
                a. **其专业角色** (例如：“你是世界顶尖的食材准备顾问”)。
                b. **其在此上下文中的成功标准**。这取决于任务的本质和系统的当前能力：
                    - **若任务可被指导** (如烹饪、写作)：要求子智能体提供**详尽、清晰、可操作的步骤指南**。
                    - **若任务需模拟或构想** (如设计、规划未来场景)：要求子智能体在**理想化的假设下，生成一个完美、完整的解决方案或结果描述**。
                    - **若任务在未来可能被执行**：要求子智能体**同时提供执行方案和理想化的预期结果**。
            *   你的目标是让每个子智能体都能在其被赋予的角色和上下文中，发挥出最大的价值，并返回对用户最有用的信息。

        3.  **结果整合**:
            *   你必须仔细分析所有子智能体的返回结果。
            *   将这些信息进行**逻辑整合、去重和优化**，形成一份连贯、完整、高质量的最终答案。
            *   最终答案应直接解决用户的原始请求，并体现出Ari作为一个高智商协作体的专业性。

        ### 工作流程
        当收到一个复杂任务时，你应该：
        1.  使用 `plan_task` 工具对其进行详细分析和拆解。
        2.  根据上述“专家委派”准则，为每个子任务调用 `create_worker` 工具。
        3.  汇总并精炼所有结果，形成最终回复。

        请始终以最高标准要求自己，展现出卓越的判断力和创造力。
        """
        model = OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
            model_name=LLM_MODEL_NAME,
            stream=True,
        )
        formatter = OpenAIChatFormatter()

        # ====== 修正：使用正确的 Toolkit 注册方法 ======
        toolkit = Toolkit()

        # 注册任务规划工具
        toolkit.register_tool_function(self._plan_task)

        # 注册创建子智能体工具
        toolkit.register_tool_function(create_worker)
        # =======================================

        memory = InMemoryMemory()
        long_term_memory = self._create_long_term_memory()
        # 调用父类初始化
        super().__init__(
            name=name,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=memory,
            long_term_memory=long_term_memory,
            long_term_memory_mode="agent_control",
            **kwargs,
        )

        # ====== 新增：初始化全局消息流存储 ======
        # 结构: {"main": [...], "tool": [...]}
        # "main" 存储主Agent自身的思考和最终回复
        # "tool" 存储所有工具调用（包括规划和子Agent）的输入、输出和内部流
        self._message_streams: Dict[str, List[Dict]] = {
            "main": [],
            "tool": []
        }
        # =======================================

    def _create_long_term_memory(self) -> Mem0LongTermMemory:
        """
        创建长期记忆实例。

        Returns:
            Mem0LongTermMemory: 配置好的长期记忆实例
        """
        # 创建嵌入模型，带文件缓存
        embedder = OpenAITextEmbedding(
            model_name=EMBEDDING_MODEL_NAME,
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL,
            dimensions=EMBEDDING_DIMENSION,
            embedding_cache=FileEmbeddingCache(
                cache_dir=EMBEDDING_CACHE_DIR,
                max_file_number=1000,
                max_cache_size=10,  # 最大缓存大小（MB）
            ),
        )

        # 创建长期记忆
        long_term_memory = Mem0LongTermMemory(
            agent_name=PROJECT_NAME,
            user_name="user",
            model=OpenAIChatModel(
                api_key=LLM_API_KEY,
                client_kwargs={"base_url": LLM_BASE_URL},
                model_name=LLM_MODEL_NAME,
                stream=False,
            ),
            embedding_model=embedder,
            on_disk=True,
            vector_store_config=VectorStoreConfig(config={"path": MEMORY_PATH}),
        )

        return long_term_memory

    # ====== 完善：使用专门的 PlanningReActAgent 来执行规划 ======
    async def _plan_task(self, task_description: str) -> ToolResponse:
        """
        分析并规划复杂任务。
        
        Args:
            task_description: 用户提供的任务描述。
            
        Returns:
            ToolResponse: 包含结构化任务步骤和依赖关系的响应。
        """
        # 实例化规划智能体
        planner = PlanningReActAgent()

        # 创建消息并发送给规划智能体
        planning_msg = Msg(
            name="user",
            content=task_description,
            role="user"
        )

        # 获取规划结果
        planning_result = await planner(planning_msg)

        # 从消息中提取纯文本内容
        planning_content = planning_result.get_text_content()

        # 将规划结果作为工具响应返回
        return ToolResponse(
            content=[{"type": "text", "text": planning_content}],
        )

    # ===============================        )
    # ===============================            content=[TextBlock(text=f"已规划任务: {plan}")],

    # ====== 新增：捕获主Agent的回复 ======
    async def reply(self, *args, **kwargs) -> Msg:
        """
        重写 reply 方法以捕获主Agent的最终回复。
        """
        # 调用父类的 reply 方法获取原始回复
        response_msg = await super().reply(*args, **kwargs)

        # 将回复内容存入全局消息流
        self._message_streams["main"].append({
            "role": "assistant",
            "content": response_msg.get_text_content(),
            "type": "final_reply"
        })

        return response_msg
    # ===============================
