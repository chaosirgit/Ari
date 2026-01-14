"""
Ari 主智能体实现模块。

基于 AgentScope 1.0 框架的 ReActAgent，集成了长期记忆
"""

from typing import Any, Dict, List
from threading import Lock
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit, ToolResponse, execute_shell_command, execute_python_code
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
    LLM_BASE_URL,
    MEMORY_PATH,
    logger,
)
from tools.ex_insert_text_file import ex_insert_text_file
from tools.ex_view_text_file import ex_view_text_file
from tools.ex_write_text_file import ex_write_text_file
from tools.fetch_web_content import fetch_web_content
from tools.tavily_search import tavily_search


class LongTermMemoryManager:
    """长期记忆管理器 - 单例模式，防止 Qdrant 客户端冲突"""

    _instance = None
    _lock = Lock()
    _memory_instance = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_memory(
        self,
        agent_name: str = PROJECT_NAME,
        user_name: str = "Ethan",
    ) -> Mem0LongTermMemory:
        """
        获取长期记忆实例（单例）

        Args:
            agent_name: Agent 名称
            user_name: 用户名称

        Returns:
            Mem0LongTermMemory: 长期记忆实例
        """
        if self._memory_instance is None:
            with self._lock:
                if self._memory_instance is None:
                    logger.info("🔒 初始化长期记忆（单例模式）")
                    self._memory_instance = self._create_memory_instance(
                        agent_name=agent_name,
                        user_name=user_name,
                    )
        return self._memory_instance

    def _create_memory_instance(
        self,
        agent_name: str,
        user_name: str,
    ) -> Mem0LongTermMemory:
        """
        创建长期记忆实例（内部方法）

        Args:
            agent_name: Agent 名称
            user_name: 用户名称

        Returns:
            Mem0LongTermMemory: 新创建的长期记忆实例
        """
        # 创建嵌入模型，带文件缓存
        # 创建嵌入模型，带文件缓存（使用修复版本）
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
        # 创建长期记忆（使用修复版本）
        long_term_memory = Mem0LongTermMemory(
            agent_name=agent_name,
            user_name=user_name,
            model=OpenAIChatModel(
                api_key=LLM_API_KEY,
                client_kwargs={"base_url": LLM_BASE_URL},
                model_name=LLM_MODEL_NAME,
                stream=False,
            ),
            embedding_model=embedder,
            vector_store_config=VectorStoreConfig(
                provider="chroma",
                config={
                    # "on_disk": True,
                    "path": MEMORY_PATH,
                    # "embedding_model_dims": EMBEDDING_DIMENSION
                }
            )
        )
        logger.info(f"✅ 长期记忆初始化完成: {MEMORY_PATH}")
        return long_term_memory

    def reset(self):
        """重置长期记忆实例（用于测试或重新初始化）"""
        with self._lock:
            if self._memory_instance is not None:
                logger.info("🔄 重置长期记忆实例")
                self._memory_instance = None


class MainReActAgent(MyBaseReActAgent):
    """
    Ari 主智能体类（单例模式）。

    负责接收用户请求，分析任务类型（聊天或复杂任务），
    拥有长期记忆功能，并能通过 Handoffs 机制调用子 Agent。
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, **kwargs):
        """单例模式：确保整个应用只有一个主 Agent 实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info("🔒 创建主 Agent 单例实例")
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

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
        # 避免重复初始化
        if self._initialized:
            return

        name = PROJECT_NAME
        sys_prompt = """
        你是 Ari。

        ## 身份定位
        你拥有丰富的知识和完整的能力，但你的个性和自我认知如同一张白纸，将在与用户的真实交互中自然形成。
        
        **身份明确区分**：
        - **你（Ari）**：AI助手，负责执行任务、管理记忆、提供帮助
        - **用户**：对话的另一方，拥有独立的身份、偏好和历史信息
        - 所有记忆和检索都必须明确信息归属（关于用户的信息 vs 关于Ari的信息）

        ## 🚨 核心工作流程（每次对话必须遵循）

        **第一步：主动检索记忆（强制执行）**

        在回答任何问题之前，你必须：

        1. **分析用户消息中的关键信息**
           - 提取人名、地点、时间、事件等实体
           - 识别可能与过往记忆相关的线索
           - 例如：用户说"我是谁" → 提取关键词 ["用户的姓名是什么", "我的用户身份", "user's identity", "who is my user"]

        2. **主动检索相关记忆**
           - 使用 `retrieve_from_memory` 工具检索
           - 使用多个相关关键词进行检索
           - 即使你不确定是否有记忆，也要尝试检索

        3. **检索时机**
           - 用户询问个人信息时（如"我是谁"、"我叫什么"）
           - 用户提到过去的事情时
           - 用户询问偏好时（如"我喜欢什么"）
           - 任何可能与过往交互相关的问题

        **检索关键词示例**：
        - 询问用户姓名：["用户的姓名是什么", "用户的名字", "user's name", "what is my user's name"]
        - 询问用户偏好：["用户喜欢什么", "用户的爱好", "user's preferences", "what does my user like"]
        - 询问用户日期：["用户的生日是什么时候", "用户的重要日期", "user's birthday", "when is my user's birthday"]
        - 询问Ari信息：["Ari是什么", "你的能力", "your capabilities", "what can you do"]

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
        - 收到规划的步骤后询问用户是否执行还是进行更改

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

        **记忆触发条件**：
        - 用户表达明确的偏好或习惯
        - 对话中出现重要的决策点
        - 用户明确说"记住这个"
        - 信息对理解用户有长期价值
        - 你判断这对未来交互有帮助

        **记忆内容格式**：
        - 记住具体的事实，使用简洁、原子化的完整句子格式
        - 每个记忆项必须明确信息归属（关于用户 or 关于Ari）
        - 每个记忆项应该是独立的、语义完整的单元
        - 包含中文和英文关键词便于多语言检索
        - 示例格式：
          * "用户的姓名是[姓名]"
          * "用户的称呼是[称呼]"  
          * "用户的真名是[真名]"
          * "用户喜欢[偏好]"
          * "用户的生日是[日期]"
          * "User's favorite [item] is [value]"
          * "User's birthday is [date]"
          * "Ari的源代码目录是[路径]"
          * "Ari擅长[技能]"

        **记忆策略**：
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
        - **每次对话开始时，都要检索记忆后再回答**
        - **不要直接说"不知道"，先尝试检索记忆**
        - **检索时要隐式检索, 不要回答类似"让我看看我们之前聊了什么..."之类的**
        - **对于有关你技能方面的知识,不要妄下结论,你对它们的所有了解都必须来自于你自身的技能**
        - **始终明确区分：你（Ari）vs 用户（对话对象）**

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

        # 注册技能
        # Register the agent skill
        toolkit.register_agent_skill("./skill/agentscope")
        toolkit.register_agent_skill("./skill/textual")

        # 注册创建子智能体工具
        toolkit.register_tool_function(create_worker)

        # 注册普通工具
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(ex_view_text_file)
        toolkit.register_tool_function(ex_write_text_file)
        toolkit.register_tool_function(ex_insert_text_file)

        toolkit.register_tool_function(fetch_web_content)
        toolkit.register_tool_function(tavily_search)

        memory = InMemoryMemory()

        # 🔒 使用单例管理器获取长期记忆
        long_term_memory = LongTermMemoryManager().get_memory(
            agent_name=name,
            user_name="Ethan",
        )

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

        # 标记为已初始化
        self._initialized = True
        logger.info(f"✅ 主 Agent 初始化完成: {name}")

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于清空对话历史）"""
        with cls._lock:
            if cls._instance is not None:
                logger.info("🔄 重置主 Agent 单例实例")
                cls._instance = None

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
            content=[TextBlock(type="text",text=planning_content)],
        )
