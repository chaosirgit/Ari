"""
Ari 主智能体实现模块。

基于 AgentScope 1.0 框架的 ReActAgent，集成了长期记忆和 Handoffs 工作流。
"""

import os
import uuid
from typing import Any, Optional, AsyncGenerator, Dict, Type
from dotenv import load_dotenv
import json

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock, ToolUseBlock
from agentscope.model import OpenAIChatModel, DashScopeChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit  # 修正导入
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.embedding import OpenAITextEmbedding, FileEmbeddingCache
from mem0.vector_stores.configs import VectorStoreConfig
from pydantic import BaseModel

import utils
from core.lib.my_base_agent_lib import MyBaseReActAgent
from core.lib.stream_agnet_lib import StreamingReActAgent, StreamingResponse
from tools.task_decomposer import task_decomposer

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
from utils import extract_json_from_response


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
        你是一个自主认知型AI实体，名为Ari。你具有长期记忆能力，能够分解复杂任务并协调多个子Agent完成工作。
        """
        model = OpenAIChatModel(
            api_key=LLM_API_KEY,
            client_kwargs={"base_url": LLM_BASE_URL},
            model_name=LLM_MODEL_NAME,
            stream=True,
        )
        formatter = OpenAIChatFormatter()

        toolkit = Toolkit()  # 修正实例化
        toolkit.register_tool_function(task_decomposer)
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

    async def reply(
            self,
            msg: Msg | list[Msg] | None = None,
            structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """
        重写 reply 方法来实现任务类型判断和处理
        """
        # 分析任务类型
        task_type = await self.analyze_task_type(msg)

        if task_type == "chat":
            # 调用父类的 reply 方法，保持原有功能
            return await super().reply(msg)
        else:
            # 任务规划模式
            return await self.toolkit.call_tool_function(
                ToolUseBlock(
                    name="task_decomposer",
                    input={"task_description": msg.content},
                    type="tool_use",
                    id=uuid.uuid4().hex[:16],
                ),
            )