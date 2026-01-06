"""
Ari 主智能体实现模块。

基于 AgentScope 1.0 框架的 ReActAgent，集成了长期记忆和 Handoffs 工作流。
"""

import os
from typing import Any, Optional, AsyncGenerator, Dict
from dotenv import load_dotenv
import asyncio

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.model import OpenAIChatModel, DashScopeChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit  # 修正导入
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.embedding import OpenAITextEmbedding,FileEmbeddingCache
from mem0.vector_stores.configs import VectorStoreConfig

from core.lib.stream_agnet_lib import StreamingReActAgent, StreamingResponse

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
PROJECT_NAME = os.getenv("PROJECT_NAME", "Ari")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

MEMORY_PATH = os.getenv("MEMORY_PATH", "./memory/vector_store")
EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", "./memory/embedding_cache")


class AriAgent(StreamingReActAgent):
    """
    Ari 主智能体类。
    
    负责接收用户请求，分析任务类型（聊天或复杂任务），
    拥有长期记忆功能，并能通过 Handoffs 机制调用子 Agent。
    """
    
    def __init__(
        self,
        name: str = "Ari",
        sys_prompt: str = "你是一个自主认知型AI实体，名为Ari。你具有长期记忆能力，能够分解复杂任务并协调多个子Agent完成工作。",
        model: Optional[OpenAIChatModel] = None,
        formatter: Optional[OpenAIChatFormatter] = None,
        toolkit: Optional[Toolkit] = None,  # 修正类型注解
        memory: Optional[InMemoryMemory] = None,
        long_term_memory: Optional[Mem0LongTermMemory] = None,
        **kwargs: Any,
    ) -> None:
        """
        初始化 Ari 主智能体。
        
        Args:
            name: 智能体名称
            sys_prompt: 系统提示词
            model: LLM 模型实例
            formatter: 消息格式化器
            toolkit: 工具集（预留接口，具体工具在其他模块实现）
            memory: 短期记忆
            long_term_memory: 长期记忆
            **kwargs: 其他参数
        """
        # 如果没有提供模型，创建默认模型
        if model is None:
            model = OpenAIChatModel(
                api_key=LLM_API_KEY,
                client_kwargs={"base_url": LLM_BASE_URL},
                model_name=LLM_MODEL_NAME,
                stream=True,
            )
        
        # 如果没有提供格式化器，创建默认格式化器
        if formatter is None:
            formatter = OpenAIChatFormatter()
        
        # 如果没有提供工具集，创建空工具集（预留接口）
        if toolkit is None:
            toolkit = Toolkit()  # 修正实例化
        
        # 如果没有提供短期记忆，创建默认记忆
        if memory is None:
            memory = InMemoryMemory()
        
        # 如果没有提供长期记忆，创建长期记忆
        if long_term_memory is None:
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
    
    async def analyze_task_type(self, message: Msg) -> str:
        """
        分析用户消息的任务类型。
        
        Args:
            message: 用户消息
            
        Returns:
            str: 任务类型 ("chat" 或 "complex_task")
        """
        content = message.content.strip()
        
        # 如果消息为空或非常短，视为聊天
        if len(content) == 0:
            return "chat"
        
        if len(content) <= 20:
            # 短消息检查是否包含明确的指令词
            instruction_words = [
                "请", "能", "可以", "帮我", "如何", "什么", "为什么", "哪里", "谁", 
                "计算", "搜索", "查找", "分析", "创建", "开发", "实现", "完成",
                "任务", "做", "执行", "处理", "解决", "回答", "解释", "说明"
            ]
            
            if any(word in content for word in instruction_words):
                return "complex_task"
            else:
                return "chat"
        else:
            # 较长的消息通常包含复杂任务
            return "complex_task"

    async def __call__(self, message: Msg) -> StreamingResponse:
        """
        处理用户消息的主入口。
        """
        await self.memory.add(message)

        task_type = await self.analyze_task_type(message)

        if task_type == "chat":
            response = await super().__call__(message)
        else:
            from .handoffs import handle_complex_task
            response = await handle_complex_task(self, message)

        await self.memory.add(response.final_msg)
        return response