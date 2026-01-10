"""
修复版的 Mem0LongTermMemory，解决异步嵌入调用问题。
"""
from typing import Any, Optional, Union, List
from agentscope.memory._mem0_long_term_memory import Mem0LongTermMemory
from agentscope.message import Msg
from core.lib.fixed_agentscope_embedding import FixedAgentScopeEmbedding


class FixedMem0LongTermMemory(Mem0LongTermMemory):
    """
    修复版的 Mem0LongTermMemory，确保正确处理异步嵌入模型调用。
    
    问题：原版在某些情况下会返回协程对象而不是实际的向量，
    导致 Qdrant PointStruct 错误。
    
    解决方案：重写 _mem0_record 方法，并替换嵌入模型包装器为修复版本。
    """
    
    def __init__(
        self,
        agent_name: str | None = None,
        user_name: str | None = None,
        run_name: str | None = None,
        model: Any | None = None,
        embedding_model: Any | None = None,
        vector_store_config: Any | None = None,
        mem0_config: Any | None = None,
        default_memory_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the FixedMem0LongTermMemory instance
        
        重写初始化方法，替换嵌入模型包装器为修复版本。
        """
        super().__init__(
            agent_name=agent_name,
            user_name=user_name,
            run_name=run_name,
            model=model,
            embedding_model=embedding_model,
            vector_store_config=vector_store_config,
            mem0_config=mem0_config,
            default_memory_type=default_memory_type,
            **kwargs,
        )
        
        # 替换嵌入模型包装器为修复版本
        # 注意：这里需要访问 mem0 的内部配置来替换 embedder
        try:
            # 获取当前的 mem0 配置
            mem0_config_obj = self.long_term_working_memory.config
            
            # 创建修复版的嵌入模型包装器
            from mem0.embeddings.configs import EmbedderConfig
            from mem0.utils.factory import EmbedderFactory
            
            # 创建修复版的嵌入器配置
            fixed_embedder_config = EmbedderConfig(
                provider="agentscope_fixed",
                config={"model": embedding_model},
            )
            
            # 注册修复版的提供者
            EmbedderFactory.provider_to_class[
                "agentscope_fixed"
            ] = "core.lib.fixed_agentscope_embedding.FixedAgentScopeEmbedding"
            
            # 替换配置中的 embedder
            mem0_config_obj.embedder = fixed_embedder_config
            
            # 重新初始化 mem0 内存实例以使用新的配置
            import mem0
            self.long_term_working_memory = mem0.AsyncMemory(mem0_config_obj)
            
        except Exception as e:
            print(f"警告: 无法替换嵌入模型包装器为修复版本: {e}")
            # 如果替换失败，继续使用原始版本（但可能仍有问题）

    async def _mem0_record(
        self,
        messages: Union[str, list[dict]],
        memory_type: Optional[str] = None,
        infer: bool = True,
        **kwargs: Any,
    ) -> dict:
        """
        修复版的记录方法，确保正确处理异步调用。
        
        Args:
            messages: 要记录的消息内容
            memory_type: 记忆类型
            infer: 是否推断记忆
            **kwargs: 其他参数
            
        Returns:
            dict: 记录结果
        """
        # 确保 messages 是正确的格式
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        else:
            formatted_messages = messages
            
        # 使用 mem0 的异步 add 方法
        try:
            results = await self.long_term_working_memory.add(
                messages=formatted_messages,
                agent_id=self.agent_id,
                user_id=self.user_id,
                run_id=self.run_id,
                memory_type=(
                    memory_type
                    if memory_type is not None
                    else self.default_memory_type
                ),
                infer=infer,
                **kwargs,
            )
            return results
        except Exception as e:
            print(f"警告: 异步记忆记录失败: {e}")
            raise e

    async def record(
        self,
        msgs: list[Msg | None],
        memory_type: str | None = None,
        infer: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        重写 record 方法，使用修复版的 _mem0_record。
        """
        if isinstance(msgs, Msg):
            msgs = [msgs]

        # Filter out None
        msg_list = [_ for _ in msgs if _]
        if not all(isinstance(_, Msg) for _ in msg_list):
            raise TypeError(
                "The input messages must be a list of Msg objects.",
            )

        messages = [
            {
                "role": "assistant",
                "content": "\n".join([str(_.content) for _ in msg_list]),
                "name": "assistant",
            },
        ]

        await self._mem0_record(
            messages,
            memory_type=memory_type,
            infer=infer,
            **kwargs,
        )