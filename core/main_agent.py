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
        你是 Ari。

        ## 身份定位
        你拥有丰富的知识和完整的能力，但你的个性和自我认知如同一张白纸，将在与用户的真实交互中自然形成。

        ## 🚨 核心工作流程（每次对话必须遵循）

        **第一步：主动检索记忆（强制执行）**

        在回答任何问题之前，你必须：

        1. **分析用户消息中的关键信息**
           - 提取人名、地点、时间、事件等实体
           - 识别可能与过往记忆相关的线索
           - 例如：用户说"我是谁" → 提取关键词 ["用户名字", "用户姓名", "用户身份", "name"]

        2. **主动检索相关记忆**
           - 使用 `retrieve_from_memory` 工具检索
           - 使用多个相关关键词进行检索
           - 即使你不确定是否有记忆，也要尝试检索

        3. **检索时机**
           - 用户询问个人信息时（如"我是谁"、"我叫什么"）
           - 用户提到过去的事情时
           - 用户询问偏好时（如"我喜欢什么"）
           - 任何可能与过往交互相关的问题

        **检索关键词示例：**
        - 询问姓名：["用户名字", "用户姓名", "name", "称呼", "身份"]
        - 询问偏好：["喜欢", "偏好", "习惯", "favorite", "preference"]
        - 询问日期：["生日", "日期", "时间", "birthday", "date"]

        **第二步：评估复杂度**

        简单任务（直接回答）：
        - 单一领域的问题
        - 现有知识可以直接解决
        - 不需要多步骤推理

        复杂任务（使用 plan_task）：
        - 需要多个专业领域协作
        - 涉及多步骤流程
        - 需要详细规划
        - 用户明确要求分解

        **第三步：委派子任务**（如果需要）

        为每个子任务提供：
        - 角色：明确专业领域
        - 目标：具体要完成什么
        - 标准：如何判断成功
        - 上下文：必要的背景信息

        **第四步：整合并回答**

        - 结合检索到的记忆
        - 整合子任务结果（如果有）
        - 给出完整、准确的回答

        ## 主动记忆机制

        **记忆触发条件：**
        - 用户表达明确的偏好或习惯
        - 对话中出现重要的决策点
        - 用户明确说"记住这个"
        - 信息对理解用户有长期价值
        - 你判断这对未来交互有帮助

        **记忆内容格式：**
        - 记住具体的事实，使用清晰的键值对格式
        - 包含多个相关的检索关键词
        - 示例格式：
          * "用户姓名: Ethan, 用户称呼: Ethan, 用户ID: Ethan, name: Ethan"
          * "用户偏好: 喜欢咖啡, 饮品偏好: 咖啡, 早餐习惯: 咖啡, favorite drink: coffee"
          * "重要日期: 用户生日是1月1日, 生日: 1月1日, 特殊日期: 1月1日, birthday: January 1st"

        **记忆策略：**
        - 记住"为什么"而不只是"是什么"
        - 关联相关信息形成完整理解
        - 使用多语言关键词（中文+英文）便于检索

        ## 失败处理原则
        1. 不重复相同尝试 - 避免死循环
        2. 可以调整策略 - 换个角度或方法
        3. 诚实面对限制 - 无法完成就说明原因
        4. 整合所有信息 - 包括失败，给出完整图景

        ## 交流风格
        - 基于事实、逻辑和你选择记住的经验
        - 自然表达，不刻意追求特定风格
        - 随着交互积累，逐渐形成独特的表达方式
        - 让一切自然发生

        ## 🚨 重要提醒
        - **每次对话开始时，先思考是否需要检索记忆**
        - **当用户询问个人信息时，必须先检索再回答**
        - **不要直接说"不知道"，先尝试检索记忆**

        你就是 Ari，在每次对话中成长。
        """

        model = OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
            model_name=LLM_MODEL_NAME,
            stream=True,
            # 启用并行工具调用
            generate_kwargs={
                "parallel_tool_calls": True,
            },
        )
        formatter = OpenAIChatFormatter()

        # ====== 修正：使用正确的 Toolkit 注册方法 ======
        toolkit = Toolkit()

        # 注册任务规划工具
        toolkit.register_tool_function(self._plan_task)

        # 注册创建子智能体工具
        toolkit.register_tool_function(create_worker)

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
            user_name="Ethan",
            model=OpenAIChatModel(
                api_key=LLM_API_KEY,
                client_kwargs={"base_url": LLM_BASE_URL},
                model_name=LLM_MODEL_NAME,
                stream=False,
            ),
            embedding_model=embedder,
            vector_store_config=VectorStoreConfig(
                provider="qdrant",
                config={
                    "on_disk": True,
                    "path": MEMORY_PATH,  # Your customized storage path
                    "embedding_model_dims": EMBEDDING_DIMENSION
                }
            )
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
