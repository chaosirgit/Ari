#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多智能体聊天系统 - Textual TUI 测试界面
"""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.widgets import TextArea
from textual.containers import Container

from agentscope.message import Msg
from core.main_agent import MainReActAgent
from ui.chat_widget import ChatWidget
from ui.task_list_widget import TaskListWidget
from ui.thinking_widget import ThinkingWidget
from ui.system_message_widget import SystemMessageWidget
from ui.user_input_widget import UserInputWidget, UserInputSubmitted
from ui.message_router import MessageRouter
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from config import logger, PROJECT_NAME


class MultiAgentApp(App):
    """多智能体聊天系统"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-rows: 1fr 4 8;
        grid-columns: 2fr 1fr 1fr;
    }

    #chat { 
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
    }

    #tasks { 
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
    }

    #thinking { 
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
    }

    #system_messages {
        column-span: 3;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $surface;
    }

    #user_input {
        column-span: 3;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $surface;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("c", "clear", "清空"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_running = False  # 🔒 任务执行标志

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatWidget(id="chat")
        yield TaskListWidget(id="tasks")
        yield ThinkingWidget(id="thinking")
        yield SystemMessageWidget(id="system_messages")
        yield UserInputWidget(id="user_input")
        yield Footer()

    async def on_mount(self):
        """应用启动时执行"""
        logger.info("🚀 应用启动")

        # 🔒 程序启动时清空所有 Agent（这是你的本意）
        GlobalAgentRegistry._agents.clear()
        GlobalAgentRegistry._monitored_agent_ids.clear()
        logger.info("🧹 清空 Agent 注册表")

    async def on_user_input_submitted(self, event: UserInputSubmitted):
        """处理用户输入提交"""
        # 🔒 检查是否有任务正在执行
        if self._task_running:
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            await system_message_widget.add_message("⚠️ 任务正在执行中，请等待完成后再提交新任务", "warning")
            return

        self._task_running = True

        try:
            # 获取组件
            chat_widget = self.query_one("#chat", ChatWidget)
            task_widget = self.query_one("#tasks", TaskListWidget)
            thinking_widget = self.query_one("#thinking", ThinkingWidget)
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            user_input_widget = self.query_one("#user_input", UserInputWidget)

            # 🔒 禁用输入框
            user_input_widget.disabled = True

            # ✅ 不清空 Agent 列表（保留对话历史）
            # 只清理子 Agent（保留主 Agent）
            agents_to_keep = []
            for agent in GlobalAgentRegistry._agents:
                # 保留主 Agent（名字是 PROJECT_NAME）
                if agent.name == PROJECT_NAME:
                    agents_to_keep.append(agent)

            # 只有当有 Agent 需要清理时才执行
            if len(agents_to_keep) < len(GlobalAgentRegistry._agents):
                GlobalAgentRegistry._agents.clear()
                GlobalAgentRegistry._agents.extend(agents_to_keep)
                logger.info(f"🧹 清理子 Agent，保留 {len(agents_to_keep)} 个主 Agent")

            # 创建路由器
            router = MessageRouter(chat_widget, task_widget, thinking_widget, system_message_widget)

            # 用户消息
            user_msg = Msg(
                name="user",
                content=event.content,
                role="user"
            )

            await chat_widget.add_message(user_msg, last=True)

            # 🔒 使用单例 Agent（保留对话历史）
            ari = MainReActAgent()

            # 调用 Agent
            main_task = ari(user_msg)

            # 流式处理
            async for msg, last in GlobalAgentRegistry.stream_all_messages(main_task=main_task):
                await router.route_message(msg, last)

            logger.info("🎉 任务完成")

        except Exception as e:
            logger.error(f"❌ 任务执行出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            await system_message_widget.add_message(f"❌ 任务执行出错: {e}", "error")

        finally:
            # 🔒 释放执行标志并重新启用输入框
            self._task_running = False
            user_input_widget = self.query_one("#user_input", UserInputWidget)
            user_input_widget.disabled = False

            # 重新聚焦输入框
            input_area = user_input_widget.query_one("#input_area", TextArea)
            input_area.focus()

    def action_clear(self):
        """清空所有内容"""
        # 等待任务完成
        if self._task_running:
            logger.warning("⚠️ 任务正在执行，无法清空")
            return

        # 🔒 清理所有 Agent（包括主 Agent）
        GlobalAgentRegistry._agents.clear()
        GlobalAgentRegistry._monitored_agent_ids.clear()

        # 🔒 重置主 Agent 单例（清空对话历史）
        MainReActAgent.reset_instance()
        logger.info("🔄 主 Agent 已重置")

        # 清空 UI
        chat_widget = self.query_one("#chat", ChatWidget)
        task_widget = self.query_one("#tasks", TaskListWidget)
        thinking_widget = self.query_one("#thinking", ThinkingWidget)
        system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
        user_input_widget = self.query_one("#user_input", UserInputWidget)

        asyncio.create_task(chat_widget.clear_messages())
        asyncio.create_task(task_widget.clear_tasks())
        asyncio.create_task(thinking_widget.clear_thinking())
        asyncio.create_task(system_message_widget.clear_messages())
        asyncio.create_task(user_input_widget.clear())


if __name__ == "__main__":
    app = MultiAgentApp()
    try:
        app.theme = "tokyo-night"
    except Exception:
        pass
    app.run()
