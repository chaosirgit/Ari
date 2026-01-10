"""
修复版的 Mem0LongTermMemory，解决异步嵌入调用问题。
"""
from typing import Any, Optional, Union, List
from agentscope.memory._mem0_long_term_memory import Mem0LongTermMemory
from agentscope.message import Msg


class FixedMem0LongTermMemory(Mem0LongTermMemory):
    """
    修复版的 Mem0LongTermMemory，确保正确处理异步嵌入模型调用。
    
    问题：原版在某些情况下会返回协程对象而不是实际的向量，
    导致 Qdrant PointStruct 错误。
    
    解决方案：重写 _mem0_record 方法，确保使用 mem0 的异步 add 方法。
    """
    
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
        # 注意：这里明确调用异步版本，并确保所有参数正确传递
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
            # 如果异步调用失败，尝试同步调用作为备选（但要确保嵌入模型正确处理）
            print(f"警告: 异步记忆记录失败: {e}")
            # 这里可以添加额外的日志或错误处理
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