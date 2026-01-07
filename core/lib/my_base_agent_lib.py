
from typing import Any


from agentscope.agent import ReActAgent
from agentscope.message import Msg


class MyBaseReActAgent(ReActAgent):
    """
        Ari 主智能体类。

        负责接收用户请求，分析任务类型（聊天或复杂任务），
        拥有长期记忆功能，并能通过 Handoffs 机制调用子 Agent。
        """

    def __init__(self,*args,**kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    # async def observe(self, msg: Msg | list[Msg] | None) -> None:
        # await self.print(msg)