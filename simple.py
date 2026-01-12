#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ari 项目的简易终端交互（simple.py）- 完整版
- 真正的 Ctrl+C 中断（调用 agent.interrupt()）
- 中断后另起一行继续输入
- 流式显示工具参数（增量更新）
- Token 统计
"""

import asyncio
import sys
import json
import time
import warnings
from typing import AsyncGenerator, Tuple, Dict, Any
from collections import defaultdict

from agentscope.message import Msg

from config import PROJECT_NAME, logger
from core.main_agent import MainReActAgent
from core.lib.my_base_agent_lib import GlobalAgentRegistry

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.history import InMemoryHistory

# 🔑 过滤掉 asyncio.iscoroutinefunction 的弃用警告
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*asyncio.iscoroutinefunction.*"
)


class TokenCounter:
    """Token 计数器"""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self.round_count = 0

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量"""
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len([w for w in text.split() if any(c.isalpha() for c in w)])
        other_chars = len(text) - chinese_chars

        tokens = int(chinese_chars * 2 + english_words * 1.3 + other_chars * 0.5)
        return max(tokens, len(text) // 4)

    def count_message_tokens(self, msg) -> Tuple[int, int]:
        """统计消息的 token 数量"""
        content = msg.content
        text_content = ""

        if isinstance(content, str):
            text_content = content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif block.get("type") == "thinking":
                        text_content += block.get("thinking", "") or block.get("text", "") or block.get("content", "")
                    elif block.get("type") == "tool_use":
                        text_content += block.get("name", "")
                        tool_input = block.get("input", {})
                        text_content += json.dumps(tool_input, ensure_ascii=False)
                    elif block.get("type") == "tool_result":
                        result = block.get("content", "") or block.get("result", "")
                        text_content += str(result)

        tokens = self.estimate_tokens(text_content)

        msg_role = getattr(msg, "role", "assistant")
        if msg_role == "user":
            return tokens, 0
        else:
            return 0, tokens

    def add_round(self, input_tokens: int, output_tokens: int):
        """添加一轮对话的统计"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.round_count += 1

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "round_count": self.round_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "avg_tokens_per_round": self.total_tokens // max(self.round_count, 1)
        }

    def format_stats(self, round_input: int, round_output: int, elapsed_time: float) -> str:
        """格式化统计信息"""
        round_total = round_input + round_output
        stats = self.get_stats()

        lines = [
            "\n" + "─" * 60,
            f"📊 本轮统计:",
            f"   输入: {round_input:,} tokens  |  输出: {round_output:,} tokens  |  合计: {round_total:,} tokens",
            f"   耗时: {elapsed_time:.2f}秒  |  速度: {round_output / elapsed_time:.0f} tokens/秒" if elapsed_time > 0 else "",
            f"",
            f"📈 累计统计 (共 {stats['round_count']} 轮):",
            f"   总输入: {stats['total_input_tokens']:,} tokens",
            f"   总输出: {stats['total_output_tokens']:,} tokens",
            f"   总计: {stats['total_tokens']:,} tokens",
            f"   平均: {stats['avg_tokens_per_round']:,} tokens/轮",
            "─" * 60
        ]

        return "\n".join(line for line in lines if line is not None)


class ContentTracker:
    """追踪每个 Agent 已显示的内容，避免重复"""

    def __init__(self):
        self.displayed_lengths: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.displayed_tool_calls: set = set()
        self.displayed_tool_results: set = set()

        # 追踪每个工具调用的参数状态
        self.tool_params_state: Dict[str, Dict[str, Any]] = {}

        self.current_agent = None
        self.current_type = None

    def reset(self):
        """重置追踪器（新一轮对话）"""
        self.displayed_lengths.clear()
        self.displayed_tool_calls.clear()
        self.displayed_tool_results.clear()
        self.tool_params_state.clear()
        self.current_agent = None
        self.current_type = None

    def get_new_content(self, agent_name: str, content_type: str, full_text: str) -> str:
        """获取新增的内容（未显示的部分）"""
        key = f"{agent_name}:{content_type}"
        displayed_len = self.displayed_lengths[agent_name][content_type]

        if len(full_text) <= displayed_len:
            return ""

        new_content = full_text[displayed_len:]
        self.displayed_lengths[agent_name][content_type] = len(full_text)

        return new_content

    def should_print_header(self, agent_name: str, content_type: str) -> bool:
        """判断是否需要打印新的头部"""
        return self.current_agent != agent_name or self.current_type != content_type

    def update_current(self, agent_name: str, content_type: str):
        """更新当前显示的 agent 和类型"""
        self.current_agent = agent_name
        self.current_type = content_type

    def get_tool_param_changes(self, tool_id: str, current_params: dict) -> dict:
        """
        获取工具参数的变化（新增或更新的参数）

        Returns:
            dict: {param_name: new_value} 只包含变化的参数
        """
        if tool_id not in self.tool_params_state:
            self.tool_params_state[tool_id] = {}

        old_state = self.tool_params_state[tool_id]
        changes = {}

        for key, value in current_params.items():
            old_value = old_state.get(key, "")
            new_value = str(value)

            # 检查是否有变化
            if str(old_value) != new_value:
                # 如果是字符串类型且旧值是新值的前缀，只返回增量
                if isinstance(value, str) and isinstance(old_value, str) and new_value.startswith(old_value):
                    if len(new_value) > len(old_value):
                        changes[key] = new_value[len(old_value):]  # 增量部分
                else:
                    changes[key] = value  # 完整新值

                # 更新状态
                old_state[key] = new_value

        return changes


def format_tool_param_changes(changes: dict, is_first_display: bool = False) -> str:
    """
    格式化工具参数的变化

    Args:
        changes: 参数变化字典
        is_first_display: 是否是首次显示

    Returns:
        格式化后的字符串
    """
    if not changes:
        return ""

    lines = []

    for key, value in changes.items():
        value_str = str(value)

        # 如果是首次显示，显示完整的键值对
        if is_first_display or not isinstance(value, str):
            lines.append(f"    • {key}: {value_str}")
        else:
            # 增量显示：只显示新增的值
            lines.append(value_str)

    return "\n".join(lines) if lines else ""


def format_content_blocks(content, tracker: ContentTracker, agent_name: str) -> str:
    """格式化并提取内容块的增量部分"""
    output = []

    # 处理字符串类型
    if isinstance(content, str):
        new_text = tracker.get_new_content(agent_name, "text", content)
        if new_text:
            if tracker.should_print_header(agent_name, "text"):
                output.append(f"\n💬 [{agent_name}] ")
                tracker.update_current(agent_name, "text")
            output.append(new_text)
        return "".join(output)

    # 处理列表类型
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")

            # 1. 处理思考块
            if block_type == "thinking":
                thinking_text = block.get("thinking", "") or block.get("text", "") or block.get("content", "")
                new_thinking = tracker.get_new_content(agent_name, "thinking", thinking_text)
                if new_thinking:
                    if tracker.should_print_header(agent_name, "thinking"):
                        output.append(f"\n🤔 [{agent_name}] 思考中...\n")
                        tracker.update_current(agent_name, "thinking")
                    output.append(f"\033[90m{new_thinking}\033[0m")

            # 2. 处理工具调用块（流式参数）
            elif block_type == "tool_use":
                tool_name = block.get("name")
                tool_id = block.get("id", "")
                tool_input = block.get("input", {})

                # 首次显示工具调用
                if tool_id and tool_id not in tracker.displayed_tool_calls:
                    output.append(f"\n🔧 [{agent_name}] 调用工具: \033[1;33m{tool_name}\033[0m")
                    tracker.displayed_tool_calls.add(tool_id)

                    # 如果有参数，显示参数头
                    if tool_input:
                        output.append(f"\n\033[93m")

                # 获取参数变化（增量）
                if tool_id and tool_input:
                    is_first = tool_id not in tracker.tool_params_state
                    changes = tracker.get_tool_param_changes(tool_id, tool_input)

                    if changes:
                        formatted_changes = format_tool_param_changes(changes, is_first)
                        if formatted_changes:
                            output.append(formatted_changes)

                # 如果参数显示完毕，关闭颜色
                if tool_input:
                    output.append("\033[0m")

            # 3. 处理工具结果块
            elif block_type == "tool_result":
                tool_id = block.get("tool_use_id", "") or block.get("id", "")

                if tool_id and tool_id in tracker.displayed_tool_results:
                    continue

                result_content = block.get("content", "") or block.get("result", "")
                is_error = block.get("is_error", False)

                if is_error:
                    output.append(f"\n❌ [{agent_name}] 工具执行失败:\n")
                    output.append(f"\033[91m    {result_content}\033[0m\n")
                else:
                    output.append(f"\n📊 [{agent_name}] 工具结果:\n")
                    display_result = str(result_content)
                    # 🆕 移除截断，完整显示
                    display_result = "\n".join(f"    {line}" for line in display_result.split("\n"))
                    output.append(f"\033[92m{display_result}\033[0m\n")

                if tool_id:
                    tracker.displayed_tool_results.add(tool_id)

            # 4. 处理文本块
            elif block_type == "text":
                text_content = block.get("text", "")
                new_text = tracker.get_new_content(agent_name, "text", text_content)
                if new_text:
                    if tracker.should_print_header(agent_name, "text"):
                        output.append(f"\n💬 [{agent_name}] ")
                        tracker.update_current(agent_name, "text")
                    output.append(new_text)

    return "".join(output)


class MessageStreamer:
    """消息流处理器，支持真正的中断"""

    def __init__(self, main_coro, agent: MainReActAgent, end_signal: str = "[END]") -> None:
        self._end_signal = end_signal
        self._main_coro = main_coro
        self._agent = agent  # 保存 agent 引用，用于调用 interrupt()
        self._task = None
        self._interrupted = False

    async def __aiter__(self) -> AsyncGenerator[Tuple, None]:
        cls = GlobalAgentRegistry
        cls._message_queue = asyncio.Queue()
        cls._monitored_agent_ids.clear()

        for agent in cls._agents:
            cls._setup_agent_queue(agent)

        last_checked_index = len(cls._agents)

        self._task = asyncio.create_task(self._main_coro)

        # 🔧 修复：定义命名函数而非 lambda，便于后续移除
        def safe_done_callback(_):
            """安全的完成回调，检查队列是否存在"""
            if cls._message_queue is not None:
                try:
                    cls._message_queue.put_nowait(self._end_signal)
                except Exception as e:
                    logger.debug(f"队列已关闭，忽略结束信号: {e}")

        # 保存回调引用，以便在 finally 中移除
        self._done_callback = safe_done_callback

        if self._task.done():
            await cls._message_queue.put(self._end_signal)
        else:
            self._task.add_done_callback(safe_done_callback)

        try:
            while True:
                try:
                    msg_data = await asyncio.wait_for(
                        cls._message_queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    async with cls._registration_lock:
                        current_agent_count = len(cls._agents)
                        if current_agent_count > last_checked_index:
                            for i in range(last_checked_index, current_agent_count):
                                new_agent = cls._agents[i]
                                cls._setup_agent_queue(new_agent)
                            last_checked_index = current_agent_count
                    continue

                if isinstance(msg_data, str) and msg_data == self._end_signal:
                    break

                if isinstance(msg_data, tuple):
                    if len(msg_data) >= 2:
                        msg = msg_data[0]
                        last = msg_data[1]
                        yield msg, last
                    else:
                        continue
        except asyncio.CancelledError:
            self._interrupted = True
            raise
        finally:
            # 🔧 先移除回调，避免在队列清理后触发
            if self._task and not self._task.done():
                try:
                    # remove_done_callback() 返回移除的回调数量
                    removed_count = self._task.remove_done_callback(self._done_callback)
                    if removed_count > 0:
                        logger.debug(f"成功移除 {removed_count} 个回调")
                except Exception as e:
                    logger.debug(f"移除回调时出错（可忽略）: {e}")

            # 检查任务异常
            try:
                if self._task and not self._task.cancelled():
                    exc = self._task.exception()
                    if exc is not None:
                        logger.error(f"主任务异常: {exc}")
            except Exception:
                pass

            # 最后清理队列
            cls._message_queue = None
            cls._monitored_agent_ids.clear()

    async def interrupt(self):
        """
        真正的中断：调用 agent.interrupt() 方法
        根据 AgentScope 文档，这会取消当前的 reply 函数并执行 handle_interrupt
        """
        try:
            self._interrupted = True

            # 调用 AgentScope 的 interrupt 方法
            if hasattr(self._agent, 'interrupt'):
                logger.info("调用 agent.interrupt() 方法")
                self._agent.interrupt()

            # 同时取消当前任务
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    # 🆕 添加超时等待，避免无限阻塞
                    await asyncio.wait_for(self._task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("任务取消超时，强制终止")
                except asyncio.CancelledError:
                    logger.info("任务已成功取消")
        except Exception as e:
            logger.error(f"中断任务时出错: {e}")

    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self._interrupted


async def run_once(ari: MainReActAgent, user_text: str, token_counter: TokenCounter) -> bool:
    """
    执行一次问答，流式显示所有内容

    Returns:
        bool: True 表示正常完成，False 表示被中断
    """
    start_time = time.time()

    user_msg = Msg(name="user", content=user_text, role="user")
    main_coro = ari(user_msg)

    streamer = MessageStreamer(main_coro, ari)
    tracker = ContentTracker()

    printed_any = False
    round_input_tokens = 0
    round_output_tokens = 0

    user_input_tokens, _ = token_counter.count_message_tokens(user_msg)
    round_input_tokens += user_input_tokens

    try:
        async for msg, last in streamer:
            agent_name = getattr(msg, "name", "Agent")

            _, output_tokens = token_counter.count_message_tokens(msg)
            round_output_tokens += output_tokens

            incremental_text = format_content_blocks(msg.content, tracker, agent_name)

            if incremental_text:
                print(incremental_text, end="", flush=True)
                printed_any = True

        if printed_any:
            print("\n")

        elapsed_time = time.time() - start_time
        token_counter.add_round(round_input_tokens, round_output_tokens)
        print(token_counter.format_stats(round_input_tokens, round_output_tokens, elapsed_time))
        print()

        return True  # 正常完成

    except KeyboardInterrupt:
        # Ctrl+C 被按下
        print("\n\n⚠️  正在中断...", flush=True)
        await streamer.interrupt()

        elapsed_time = time.time() - start_time
        token_counter.add_round(round_input_tokens, round_output_tokens)
        print(token_counter.format_stats(round_input_tokens, round_output_tokens, elapsed_time))
        print("\n❌ 已中断\n")

        return False  # 被中断

    except asyncio.CancelledError:
        # 任务被取消
        elapsed_time = time.time() - start_time
        token_counter.add_round(round_input_tokens, round_output_tokens)
        print(token_counter.format_stats(round_input_tokens, round_output_tokens, elapsed_time))
        print("\n❌ 已中断\n")

        return False  # 被中断

    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        logger.exception("运行时错误")
        return False


def make_prompt_session() -> PromptSession:
    """创建增强的输入会话"""
    kb = KeyBindings()

    @kb.add('c-n')
    def _(event):
        """Ctrl+N 插入换行"""
        event.current_buffer.insert_text('\n')

    history = InMemoryHistory()

    session = PromptSession(
        key_bindings=kb,
        history=history,
        multiline=False,
        enable_history_search=True,
    )
    return session


async def main() -> None:
    """主函数"""
    ari = MainReActAgent()
    token_counter = TokenCounter()

    print(f"\n{'=' * 60}")
    print(f"  {PROJECT_NAME} - 简易终端交互")
    print(f"{'=' * 60}")
    print("💡 提示:")
    print("  - 输入内容后按 Enter 发送")
    print("  - Ctrl+N 插入换行（多行输入）")
    print("  - Ctrl+C 中断当前生成（另起一行继续输入）")
    print("  - Ctrl+D 退出程序")
    print(f"{'=' * 60}\n")

    session = make_prompt_session()

    while True:
        try:
            user_text = await session.prompt_async('你 > ')
        except EOFError:
            # Ctrl+D 退出
            stats = token_counter.get_stats()
            print(f"\n{'=' * 60}")
            print(f"📊 会话总结:")
            print(f"   对话轮数: {stats['round_count']}")
            print(f"   总 Tokens: {stats['total_tokens']:,}")
            print(f"   平均每轮: {stats['avg_tokens_per_round']:,} tokens")
            print(f"{'=' * 60}")
            print("\n👋 再见！")
            break
        except KeyboardInterrupt:
            # 在输入阶段按 Ctrl+C
            print("\n^C (已取消输入)")
            continue

        if not user_text or not user_text.strip():
            continue

        # 执行对话（可能被中断）
        completed = await run_once(ari, user_text, token_counter)

        # 无论是否被中断，都会另起一行继续等待输入


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 已退出")
    except Exception as e:
        print(f"\n❌ 致命错误: {e}", file=sys.stderr)
        logger.exception("程序异常退出")
        sys.exit(1)
