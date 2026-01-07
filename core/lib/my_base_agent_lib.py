from typing import Any

from agentscope.agent import ReActAgent
from agentscope.message import Msg

# 导入全局消息流管理器
from ui.message_stream_manager import get_or_create_agent_stream


class MyBaseReActAgent(ReActAgent):
    """
    Ari 主智能体基类。

    所有 Ari 体系内的智能体都应继承此类，以获得统一的消息流捕获能力。
    """

    def __init__(self, *args, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # 为当前智能体初始化消息流
        self._agent_stream = get_or_create_agent_stream(self.name)

    async def reply(self, *args, **kwargs) -> Msg:
        """
        重写 reply 方法以捕获智能体的最终回复。
        
        无论是流式还是非流式调用，此方法都会在最终消息生成后被调用。
        """
        # 调用父类的 reply 方法获取原始回复
        response_msg = await super().reply(*args, **kwargs)
        
        # 将回复内容存入该智能体的全局消息流
        self._agent_stream["reply"].append({
            "role": "assistant",
            "content": response_msg.get_text_content(),
            "timestamp": response_msg.timestamp,
        })
        
        return response_msg

    async def observe(self, msg: Msg | list[Msg] | None) -> None:
        """
        重写 observe 方法以捕获接收到的消息。
        
        此方法会在智能体接收到任何外部消息时被调用。
        """
        # 先调用父类的 observe 方法
        await super().observe(msg)
        
        # TODO: 在这里可以添加逻辑来解析特定消息（如规划结果）
        # 并更新任务状态等。目前先简单记录。
        if isinstance(msg, list):
            for m in msg:
                self._agent_stream["thinking"].append({
                    "role": m.role,
                    "name": m.name,
                    "content": m.get_text_content(),
                    "timestamp": m.timestamp,
                })
        elif msg is not None:
            self._agent_stream["thinking"].append({
                "role": msg.role,
                "name": msg.name,
                "content": msg.get_text_content(),
                "timestamp": msg.timestamp,
            })