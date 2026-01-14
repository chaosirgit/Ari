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
        cls._message_queue = asyncio.Queue()
        cls._monitored_agent_ids.clear()

        for agent in cls._agents:
            cls._setup_agent_queue(agent)

        last_checked_index = len(cls._agents)
        task = asyncio.create_task(main_task)

        if task.done():
            await cls._message_queue.put(end_signal)
        else:
            task.add_done_callback(lambda _: cls._message_queue.put_nowait(end_signal))

        while True:
            try:
                msg_data = await asyncio.wait_for(cls._message_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                async with cls._registration_lock:
                    current_agent_count = len(cls._agents)
                    if current_agent_count > last_checked_index:
                        for i in range(last_checked_index, current_agent_count):
                            new_agent = cls._agents[i]
                            cls._setup_agent_queue(new_agent)
                        last_checked_index = current_agent_count
                continue

            if isinstance(msg_data, str) and msg_data == end_signal:
                break

            if yield_speech:
                yield msg_data
            else:
                msg, last, _ = msg_data
                yield msg, last

        exception = task.exception()
        if exception is not None:
            raise exception from None

        cls._message_queue = None
        cls._monitored_agent_ids.clear()


def _convert_messages_for_grok(messages: list[dict]) -> list[dict]:
    """
    转换消息格式以符合 Grok API 要求。

    Grok API 限制：只有 role=user 的消息可以包含 name 字段。
    """
    if not messages:
        return messages

    formatted = []
    for msg in messages:
        new_msg = dict(msg)  # 浅拷贝

        # 🔑 关键：移除非 user 角色消息中的 name 字段
        if new_msg.get("role") != "user" and "name" in new_msg:
            del new_msg["name"]

        formatted.append(new_msg)
    return formatted


def _patch_openai_client_for_grok(model):
    """
    在 OpenAI client 层面打补丁，拦截 chat.completions.create 调用。

    这是最底层的拦截点，确保所有调用都经过格式转换。
    """
    # 检查是否是 Grok 模型
    if not (hasattr(model, 'model_name') and
            isinstance(model.model_name, str) and
            model.model_name.lower().startswith('grok')):
        return

    # 检查是否已打补丁
    if getattr(model, '_grok_client_patched', False):
        return

    # 获取 OpenAI client
    if not hasattr(model, 'client'):
        return

    client = model.client

    # 保存原始的 create 方法
    original_create = client.chat.completions.create

    async def patched_create(*args, **kwargs):
        """包装后的 create 方法"""
        # 处理 messages 参数（可能在 args 或 kwargs 中）
        if 'messages' in kwargs:
            kwargs['messages'] = _convert_messages_for_grok(kwargs['messages'])
        elif args:
            # messages 是第一个位置参数
            args = list(args)
            args[0] = _convert_messages_for_grok(args[0])
            args = tuple(args)

        return await original_create(*args, **kwargs)

    # 替换 client 的 create 方法
    client.chat.completions.create = patched_create
    model._grok_client_patched = True

    print(f"[Grok Patch] 已为模型 {model.model_name} 的 OpenAI client 打补丁")


class MyBaseReActAgent(ReActAgent):
    """
    Ari 主智能体基类。

    所有 Ari 体系内的智能体都应继承此类，以获得统一的消息流捕获能力。
    """

    def __init__(self, *args, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.set_console_output_enabled(False)

        # 🔑 在 OpenAI client 层面打补丁
        if hasattr(self, 'model'):
            _patch_openai_client_for_grok(self.model)

        GlobalAgentRegistry.register_agent(self)
