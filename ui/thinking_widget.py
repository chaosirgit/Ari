#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
思考区组件 - 显示 Agent 的思考过程
"""

from textual.widgets import Static
from textual.containers import VerticalScroll, Vertical
from rich.text import Text
from rich.panel import Panel
from config import logger


class ThinkingWidget(VerticalScroll):
    """思考区组件 - 显示 Agent 的工具调用思考过程"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "💭 思考过程"
        self._container = None
        self._current_thinking = {}  # 记录当前正在构建的思考 {agent_name: {tool_name, tool_input, widget}}

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

    def _format_thinking(self, agent_name: str, tool_name: str, tool_input: dict) -> Text:
        """格式化思考内容"""
        emoji = self._get_agent_emoji(agent_name)

        thinking_text = Text()
        thinking_text.append(f"{emoji} {agent_name} ", style="bold cyan")
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
            # 检查是否是同一个 Agent 的同一个工具调用（增量更新）
            current = self._current_thinking.get(agent_name)

            if current and current["tool_name"] == tool_name:
                # 增量更新：替换最后一条
                current["tool_input"] = tool_input
                formatted_text = self._format_thinking(agent_name, tool_name, tool_input)
                current["widget"].update(formatted_text)
                logger.debug(f"💭 更新思考: {agent_name} -> {tool_name}")
            else:
                # 新的工具调用：添加新条目
                formatted_text = self._format_thinking(agent_name, tool_name, tool_input)
                widget = Static(formatted_text)
                await self._container.mount(widget)

                # 记录当前思考
                self._current_thinking[agent_name] = {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "widget": widget
                }
                logger.debug(f"💭 添加思考: {agent_name} -> {tool_name}")

        except Exception as e:
            logger.error(f"❌ 添加思考失败: {e}")

    async def clear_thinking(self):
        """清空思考记录"""
        if self._container:
            await self._container.remove_children()
            self._current_thinking.clear()
            logger.info("🧹 清空思考区")
