from agentscope.agent import ReActAgent
from agentscope.message import Msg, AudioBlock
from copy import deepcopy
import asyncio
from typing import AsyncGenerator, Any, List, Dict
from dataclasses import dataclass

@dataclass
class StreamingResponse:
    """流式响应对象，包装原始Msg并提供流式获取方法"""

    final_msg: Msg
    _agent: 'StreamingReActAgent'

    async def get_text_stream(self) -> AsyncGenerator[str, None]:
        """获取文本内容的流式生成器"""
        async for chunk in self._agent._get_streaming_content('text'):
            yield chunk

    async def get_thinking_stream(self) -> AsyncGenerator[str, None]:
        """获取思考内容的流式生成器"""
        async for chunk in self._agent._get_streaming_content('thinking'):
            yield chunk

    async def get_tool_stream(self) -> AsyncGenerator[Dict, None]:
        """获取工具调用的流式生成器"""
        async for chunk in self._agent._get_streaming_content('tool_use'):
            yield chunk

    async def get_audio_stream(self) -> AsyncGenerator[Any, None]:
        """获取音频内容的流式生成器"""
        async for chunk in self._agent._get_streaming_content('audio'):
            yield chunk

    def get_final_text(self) -> str:
        """获取最终的完整文本内容"""
        return self.final_msg.get_text_content()

    def get_final_thinking(self) -> str:
        """获取最终的完整思考内容"""
        thinking_content = ""
        for block in self.final_msg.content:
            if isinstance(block, dict) and block.get('type') == 'thinking':
                thinking_content += block.get('thinking', '')
        return thinking_content

    def get_final_tools(self) -> List[Dict]:
        """获取最终的完整工具调用列表"""
        tool_calls = []
        for block in self.final_msg.content:
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                tool_calls.append({
                    'name': block.get('name', ''),
                    'input': block.get('input', ''),
                    'id': block.get('id', '')
                })
        return tool_calls


class StreamingReActAgent(ReActAgent):
    """支持流式输出的ReActAgent，保持原有使用方式不变"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 流式数据存储（每个调用独立）
        self._current_streaming_data = None
        self._current_streaming_complete = False
        self._streaming_lock = asyncio.Lock()

    async def print(
        self,
        msg: Msg,
        last: bool = True,
        speech: AudioBlock | list[AudioBlock] | None = None,
    ) -> None:
        """
        重写的print方法，保持原始功能的同时记录流式数据
        """
        # ========== 保持原始功能 ==========
        if not self._disable_msg_queue:
            await self.msg_queue.put((deepcopy(msg), last, speech))

        if not self._disable_console_output:
            await self._original_print_logic(msg, last, speech)

        # ========== 记录流式数据 ==========
        await self._record_streaming_data(msg, last, speech)

    async def _original_print_logic(
        self,
        msg: Msg,
        last: bool = True,
        speech: AudioBlock | list[AudioBlock] | None = None,
    ) -> None:
        """实现原始print方法的核心逻辑"""
        thinking_and_text_to_print = []

        for block in msg.get_content_blocks():
            if block["type"] == "text":
                self._print_text_block(
                    msg.id,
                    name_prefix=msg.name,
                    text_content=block["text"],
                    thinking_and_text_to_print=thinking_and_text_to_print,
                )

            elif block["type"] == "thinking":
                self._print_text_block(
                    msg.id,
                    name_prefix=f"{msg.name}(thinking)",
                    text_content=block["thinking"],
                    thinking_and_text_to_print=thinking_and_text_to_print,
                )

            elif last:
                self._print_last_block(block, msg)

        if isinstance(speech, list):
            for audio_block in speech:
                self._process_audio_block(msg.id, audio_block)
        elif isinstance(speech, dict):
            self._process_audio_block(msg.id, speech)

        if last and msg.id in self._stream_prefix:
            if "audio" in self._stream_prefix[msg.id]:
                player, _ = self._stream_prefix[msg.id]["audio"]
                player.close()
            stream_prefix = self._stream_prefix.pop(msg.id)
            if "text" in stream_prefix and not stream_prefix["text"].endswith("\n"):
                print()

    async def _record_streaming_data(
        self,
        msg: Msg,
        last: bool = True,
        speech: AudioBlock | list[AudioBlock] | None = None,
    ) -> None:
        """记录流式数据到当前调用的存储中"""
        if self._current_streaming_data is None:
            return

        current_text = ""
        current_thinking = ""
        current_tools = []

        # 分析所有内容块
        for block in msg.content:  # 直接访问content属性
            if isinstance(block, dict):
                block_type = block.get('type', '')

                if block_type == 'text':
                    current_text += block.get('text', '')
                elif block_type == 'thinking':
                    current_thinking += block.get('thinking', '')
                elif block_type == 'tool_use':
                    tool_info = {
                        'name': block.get('name', ''),
                        'input': block.get('input', ''),
                        'id': block.get('id', '')
                    }
                    current_tools.append(tool_info)

        async with self._streaming_lock:
            # 处理文本增量
            existing_text = "".join(self._current_streaming_data['text'])
            if current_text and len(current_text) > len(existing_text):
                new_text = current_text[len(existing_text):]
                self._current_streaming_data['text'].append(new_text)

            # 处理思考增量
            existing_thinking = "".join(self._current_streaming_data['thinking'])
            if current_thinking and len(current_thinking) > len(existing_thinking):
                new_thinking = current_thinking[len(existing_thinking):]
                self._current_streaming_data['thinking'].append(new_thinking)

            # 处理新工具调用
            existing_tool_count = len(self._current_streaming_data['tool_use'])
            if len(current_tools) > existing_tool_count:
                for i in range(existing_tool_count, len(current_tools)):
                    self._current_streaming_data['tool_use'].append(current_tools[i])

            # 处理音频
            if speech:
                self._current_streaming_data['audio'].append(speech)

            # 标记完成
            if last:
                self._current_streaming_complete = True

    async def _get_streaming_content(self, content_type: str) -> AsyncGenerator[Any, None]:
        """内部方法：获取指定类型的流式内容"""
        if self._current_streaming_data is None:
            return

        recorded_count = 0
        while not self._current_streaming_complete or recorded_count < len(self._current_streaming_data[content_type]):
            async with self._streaming_lock:
                current_items = self._current_streaming_data[content_type][:]

            # Yield new items
            while recorded_count < len(current_items):
                yield current_items[recorded_count]
                recorded_count += 1

            if not self._current_streaming_complete:
                await asyncio.sleep(0.01)  # 短暂等待新数据

    async def __call__(self, *args, **kwargs) -> StreamingResponse:
        """
        重写调用方法，返回StreamingResponse对象而不是原始Msg
        保持原有使用方式完全不变！
        """
        # 初始化本次调用的流式数据
        self._current_streaming_data = {
            'text': [],
            'thinking': [],
            'tool_use': [],
            'audio': []
        }
        self._current_streaming_complete = False

        try:
            # 调用父类的__call__方法获取最终结果
            final_msg = await super().__call__(*args, **kwargs)

            # 返回包装后的响应对象
            return StreamingResponse(final_msg=final_msg, _agent=self)

        finally:
            # 清理本次调用的流式数据
            self._current_streaming_data = None
            self._current_streaming_complete = False


#
# # 使用示例
# async def example_usage():
#     """使用示例 - 完全兼容原有方式"""
#
#     # 创建Agent（你的实际配置）
#     ari = StreamingReActAgent(
#         name="Ari",
#         sys_prompt="你是一个有用的助手",
#         model=your_model,  # 替换为你的模型实例
#         formatter=your_formatter,  # 替换为你的formatter实例
#         # ... 其他必要参数
#     )
#
#     user_msg = Msg({"role": "user", "content": "1 到 20"})
#
#     # 方式1: 原有使用方式（完全兼容）
#     response = await ari(user_msg)
#     print("最终回复:", response.get_final_text())
#
#     # 方式2: 新的流式获取方式
#     response = await ari(user_msg)
#
#     # 获取文本流式内容
#     print("流式文本内容:")
#     async for text_chunk in response.get_text_stream():
#         print(text_chunk, end="", flush=True)
#     print()
#
#     # 获取思考流式内容
#     print("流式思考内容:")
#     async for thinking_chunk in response.get_thinking_stream():
#         print(f"💭 {thinking_chunk}", end="", flush=True)
#     print()
#
#     # 获取工具调用流式内容
#     print("工具调用:")
#     async for tool_call in response.get_tool_stream():
#         print(f"🔧 调用工具: {tool_call['name']}, 参数: {tool_call['input']}")
#
#     # 获取最终完整内容
#     print("完整文本:", response.get_final_text())
#     print("完整思考:", response.get_final_thinking())
#     print("完整工具调用:", response.get_final_tools())