from typing import Any, Coroutine, AsyncGenerator, Union, Tuple

from agentscope.agent import ReActAgent

import asyncio
from typing import List, Set

from agentscope.message import Msg, AudioBlock


class GlobalAgentRegistry:
    """全局 Agent 注册器"""
    _agents: List['MyBaseReActAgent'] = []
    _monitored_agent_ids: Set[str] = set()
    _message_queue: asyncio.Queue = None
    _registration_lock = asyncio.Lock()

    @classmethod
    def register_agent(cls, agent: 'MyBaseReActAgent'):
        cls._agents.append(agent)
        # 如果已经在监控中，立即设置队列
        if cls._message_queue is not None:
            cls._setup_agent_queue(agent)

    @classmethod
    def _setup_agent_queue(cls, agent: 'MyBaseReActAgent'):
        if agent.id not in cls._monitored_agent_ids:
            agent.set_msg_queue_enabled(True, cls._message_queue)
            cls._monitored_agent_ids.add(agent.id)

    @classmethod
    async def stream_all_messages(
            cls,
            main_task: Coroutine[Any, Any, Any],
            end_signal: str = "[END]",
            yield_speech: bool = False,
    ) -> AsyncGenerator[
        Union[
            Tuple[Msg, bool],
            Tuple[Msg, bool, Union[AudioBlock, list[AudioBlock], None]]
        ],
        None,
    ]:
        """
        统一获取所有已注册和未来创建的 Agent 消息。

        Args:
            main_task (`Coroutine`):
                要执行的主协程任务。
            end_signal (`str`, defaults to `"[END]"`):
                结束信号字符串。
            yield_speech (`bool`, defaults to `False`):
                是否在生成的消息中包含语音数据。

        Yields:
            `Tuple[Msg, bool] | Tuple[Msg, bool, AudioBlock | list[AudioBlock] | None]`:
                - msg: 消息对象
                - last: 布尔值，指示是否为流式消息的最后一个块
                - speech: 语音数据（仅当 yield_speech=True 时包含）

        这个方法的返回类型与官方的 `stream_printing_messages` 完全一致。
        """
        cls._message_queue = asyncio.Queue()
        cls._monitored_agent_ids.clear()

        # 设置已有 Agent 的队列
        for agent in cls._agents:
            cls._setup_agent_queue(agent)

        # 记录当前已监控的 Agent 数量
        last_checked_index = len(cls._agents)

        # 执行主任务
        task = asyncio.create_task(main_task)

        if task.done():
            await cls._message_queue.put(end_signal)
        else:
            task.add_done_callback(lambda _: cls._message_queue.put_nowait(end_signal))

        # 消息流处理
        while True:
            try:
                # 短超时检查消息队列
                msg_data = await asyncio.wait_for(cls._message_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                # 检查是否有新注册的 Agent
                async with cls._registration_lock:
                    current_agent_count = len(cls._agents)
                    if current_agent_count > last_checked_index:
                        # 有新 Agent 被注册，设置它们的队列
                        for i in range(last_checked_index, current_agent_count):
                            new_agent = cls._agents[i]
                            cls._setup_agent_queue(new_agent)
                        last_checked_index = current_agent_count
                continue

            # 检查结束信号
            if isinstance(msg_data, str) and msg_data == end_signal:
                break

            # 处理消息数据
            if yield_speech:
                # 返回 (msg, last, speech) 元组
                yield msg_data  # msg_data 已经是 (msg, last, speech) 元组
            else:
                # 返回 (msg, last) 元组，忽略 speech
                msg, last, _ = msg_data
                yield msg, last

        # 检查任务异常
        exception = task.exception()
        if exception is not None:
            raise exception from None

        # 清理
        cls._message_queue = None
        cls._monitored_agent_ids.clear()


class MyBaseReActAgent(ReActAgent):
    """
    Ari 主智能体基类。

    所有 Ari 体系内的智能体都应继承此类，以获得统一的消息流捕获能力。
    """

    def __init__(self, *args, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.set_console_output_enabled(False)
        GlobalAgentRegistry.register_agent(self)
