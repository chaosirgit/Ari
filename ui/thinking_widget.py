#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
思考区组件 - 显示 Agent 的思考过程（支持自动清空）
"""

import asyncio
from textual.widgets import Static
from textual.containers import VerticalScroll, Vertical
from rich.text import Text
from config import logger


class ThinkingWidget(VerticalScroll):
    """思考区组件 - 显示 Agent 的工具调用思考过程"""

    DEFAULT_CSS = """
    ThinkingWidget {
        width: 100%;
        height: 100%;
        padding: 1 2;
        background: $surface;
    }

    ThinkingWidget > Vertical {
        width: 100%;
        height: auto;
    }

    ThinkingWidget Static {
        width: 100%;
        margin-bottom: 1;
        color: $text;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "💭 思考过程"
        self._container = None
        self._current_thinking = {}  # 记录当前正在构建的思考 {agent_name: {tool_name, tool_input, widget, completed}}
        self._clear_timers = {}  # 记录每个 Agent 的清空定时器 {agent_name: Task}

    def on_unmount(self) -> None:
        """组件卸载时清理资源"""
        for task in self._clear_timers.values():
            task.cancel()
        self._clear_timers.clear()

    def compose(self):
        self._container = Vertical()
        yield self._container

    def _get_agent_emoji(self, agent_name: str) -> str:
        """
        根据 Agent 名称返回对应的 Emoji

        Args:
            agent_name: Agent 名称

        Returns:
            对应的 Emoji 字符
        """
        if agent_name.startswith("Worker_"):
            return "👷"
        elif agent_name == "Planning":
            return "📋"
        else:
            return "🤖"

    def _format_thinking(self, agent_name: str, tool_name: str, tool_input: dict, completed: bool = False) -> Text:
        """格式化思考内容"""
        emoji = self._get_agent_emoji(agent_name)

        thinking_text = Text()
        thinking_text.append(f"{emoji} {agent_name} ", style="bold cyan")

        if completed:
            thinking_text.append("✅ 思考完成 (3秒后清空)\n", style="italic green")
        else:
            thinking_text.append("正在思考...\n", style="italic yellow")

        thinking_text.append(f"   └─ 调用工具: ", style="dim")
        thinking_text.append(f"{tool_name}\n", style="bold yellow")

        # 显示参数
        if tool_input:
            for key, value in tool_input.items():
                thinking_text.append(f"   └─ {key}: ", style="dim")
                # 截断过长的值
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = value_str[:60] + "..."
                thinking_text.append(f"{value_str}\n", style="green")

        return thinking_text

    async def add_thinking(
            self,
            agent_name: str,
            tool_name: str,
            tool_input: dict
    ):
        """
        添加思考记录（增量显示）

        Args:
            agent_name: Agent 名称
            tool_name: 工具名称
            tool_input: 工具输入参数
        """
        try:
            # 🔥 取消该 Agent 之前的清空定时器
            if agent_name in self._clear_timers:
                self._clear_timers[agent_name].cancel()
                del self._clear_timers[agent_name]
                logger.debug(f"⏸️ 取消 {agent_name} 的清空定时器")

            # 检查是否是同一个 Agent 的同一个工具调用（增量更新）
            current = self._current_thinking.get(agent_name)

            if current and current["tool_name"] == tool_name:
                # 增量更新：替换最后一条
                current["tool_input"] = tool_input
                current["completed"] = False  # 重置完成状态
                formatted_text = self._format_thinking(agent_name, tool_name, tool_input, completed=False)
                current["widget"].update(formatted_text)
                logger.debug(f"💭 更新思考: {agent_name} -> {tool_name}")
            else:
                # 新的工具调用：添加新条目
                formatted_text = self._format_thinking(agent_name, tool_name, tool_input, completed=False)
                widget = Static(formatted_text)
                await self._container.mount(widget)

                # 记录当前思考
                self._current_thinking[agent_name] = {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "widget": widget,
                    "completed": False
                }
                logger.debug(f"💭 添加思考: {agent_name} -> {tool_name}")

            # 🚀 强制滚动到底部
            self.scroll_end(animate=False)

        except Exception as e:
            logger.error(f"❌ 添加思考失败: {e}")

    async def mark_thinking_complete(self, agent_name: str):
        """
        标记某个 Agent 的思考完成，延迟 3 秒后清空该 Agent 的思考内容

        Args:
            agent_name: Agent 名称
        """
        # 检查该 Agent 是否有思考记录
        if agent_name not in self._current_thinking:
            logger.debug(f"⚠️ {agent_name} 没有思考记录，跳过清空")
            return

        # 🔥 取消之前的定时器（如果存在）
        if agent_name in self._clear_timers:
            self._clear_timers[agent_name].cancel()

        # 🔥 更新 UI 显示为"完成"状态
        current = self._current_thinking[agent_name]
        if not current["completed"]:
            current["completed"] = True
            formatted_text = self._format_thinking(
                agent_name,
                current["tool_name"],
                current["tool_input"],
                completed=True
            )
            current["widget"].update(formatted_text)
            logger.debug(f"✅ 标记 {agent_name} 思考完成")
            
            # 🚀 强制滚动
            self.scroll_end(animate=False)

        # 🔥 创建新的清空定时器
        async def _delayed_clear():
            try:
                await asyncio.sleep(3.0)
                if agent_name in self._current_thinking:
                    await self._clear_agent_thinking(agent_name)
            except asyncio.CancelledError:
                logger.debug(f"⏸️ {agent_name} 的清空任务被取消")
            except Exception as e:
                logger.error(f"❌ 清空任务出错: {e}")
            finally:
                # 任务结束，从字典中移除（如果是自己结束的）
                if agent_name in self._clear_timers and self._clear_timers[agent_name] == asyncio.current_task():
                    del self._clear_timers[agent_name]

        self._clear_timers[agent_name] = asyncio.create_task(_delayed_clear())
        logger.debug(f"⏰ 启动 {agent_name} 的 3 秒清空任务")

    async def _clear_agent_thinking(self, agent_name: str):
        """
        清空指定 Agent 的思考内容
        """
        try:
            if agent_name in self._current_thinking:
                widget = self._current_thinking[agent_name]["widget"]
                # 检查 widget 是否还挂载着
                if widget.is_mounted:
                    await widget.remove()
                del self._current_thinking[agent_name]
                logger.info(f"🧹 清空 {agent_name} 的思考内容")

            # 强制滚动以更新布局
            self.scroll_end(animate=False)
            
        except Exception as e:
            logger.warning(f"⚠️ 清空思考内容时出错: {e}")

    async def clear_thinking(self):
        """清空所有思考记录"""
        # 🔥 取消所有定时器
        for task in self._clear_timers.values():
            task.cancel()
        self._clear_timers.clear()

        if self._container:
            await self._container.remove_children()
            self._current_thinking.clear()
            logger.info("🧹 清空思考区")
