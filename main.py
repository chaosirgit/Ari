#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多智能体聊天系统 - Textual TUI 主界面
"""

import asyncio
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.widgets import TextArea
from textual.containers import Container, Vertical

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


class BannerWidget(Static):
    """顶部 Banner 组件"""

    def compose(self) -> ComposeResult:
        yield Static(f"🤖 {PROJECT_NAME} - 多智能体聊天系统", classes="banner_text")


class StatusBarWidget(Static):
    """底部状态栏组件"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_status = "空闲"
        self._agent_count = 0
        self._update_timer = None

    def compose(self) -> ComposeResult:
        yield Static("", id="status_content", classes="status_text")

    def on_mount(self):
        """挂载时启动定时更新"""
        self.update_status()
        # 每秒更新一次时间
        self._update_timer = self.set_interval(1.0, self.update_status)

    def update_status(self, task_status: str = None, agent_count: int = None):
        """更新状态栏"""
        if task_status is not None:
            self._task_status = task_status
        if agent_count is not None:
            self._agent_count = agent_count

        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        status_text = (
            f"🕐 {current_time} | "
            f"📊 状态: {self._task_status} | "
            f"🤖 Agent: {self._agent_count} | "
            f"⌨️  [Ctrl+Enter]发送 [Ctrl+Q]退出 [C]清空 [Ctrl+L]日志"
        )

        try:
            status_widget = self.query_one("#status_content", Static)
            status_widget.update(status_text)
        except Exception:
            pass


class MultiAgentApp(App):
    """多智能体聊天系统"""

    CSS = """
    /* 全局布局 */
    Screen {
        layout: grid;
        grid-size: 2 6;
        grid-rows: 1fr 10fr 5fr 3fr 1fr 1fr;
        grid-columns: 3fr 1fr;
    }

    /* Banner 横跨所有列 */
    #banner {
        column-span: 2;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $primary-darken-2;
        content-align: center middle;
        padding: 0;
    }

    .banner_text {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $text;
    }

    /* 聊天区 - 左侧，跨2行 */
    #chat { 
        row-span: 2;
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    /* 思考区 - 右上 */
    #thinking { 
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    /* 任务列表 - 右下 */
    #tasks { 
        width: 100%; 
        height: 100%; 
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    /* 用户输入区 - 横跨所有列 */
    #user_input {
        column-span: 2;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    /* 系统消息 - 横跨所有列 */
    #system_messages {
        column-span: 2;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    /* 底部状态栏 - 横跨所有列，无背景 */
    #status_bar {
        column-span: 2;
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: transparent;
        content-align: center middle;
        padding: 0;
    }

    .status_text {
        width: 100%;
        text-align: center;
        color: $text-muted;
        padding: 0 1;
    }

    /* 移除额外间距 */
    Container {
        padding: 0;
        margin: 0;
    }

    Widget {
        margin: 0;
    }

    /* 隐藏 Header 和 Footer */
    Header {
        display: none;
    }

    Footer {
        display: none;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "退出"),
        ("c", "clear", "清空"),
        ("ctrl+l", "toggle_log", "日志"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_running = False

    def compose(self) -> ComposeResult:
        """组件布局顺序"""
        yield BannerWidget(id="banner")
        yield ChatWidget(id="chat")
        yield ThinkingWidget(id="thinking")
        yield TaskListWidget(id="tasks")
        yield UserInputWidget(id="user_input")
        yield SystemMessageWidget(id="system_messages")
        yield StatusBarWidget(id="status_bar")

    async def on_mount(self):
        """应用启动时执行"""
        logger.info("🚀 应用启动")

        # 清空所有 Agent
        GlobalAgentRegistry._agents.clear()
        GlobalAgentRegistry._monitored_agent_ids.clear()
        logger.info("🧹 清空 Agent 注册表")

        # 更新状态栏
        self._update_status_bar()

        # 设置初始焦点到输入框
        try:
            user_input_widget = self.query_one("#user_input", UserInputWidget)
            input_area = user_input_widget.query_one("#input_area", TextArea)
            input_area.focus()
        except Exception as e:
            logger.warning(f"⚠️ 无法设置焦点: {e}")

    def _update_status_bar(self, task_status: str = "空闲"):
        """更新状态栏"""
        try:
            status_bar = self.query_one("#status_bar", StatusBarWidget)
            agent_count = len(GlobalAgentRegistry._agents)
            status_bar.update_status(task_status, agent_count)
        except Exception as e:
            logger.warning(f"⚠️ 无法更新状态栏: {e}")

    async def on_user_input_submitted(self, event: UserInputSubmitted):
        """处理用户输入提交"""
        if self._task_running:
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            await system_message_widget.add_message("⚠️ 任务正在执行中，请等待完成后再提交新任务", "warning")
            return

        self._task_running = True
        self._update_status_bar("执行中")

        try:
            # 获取组件
            chat_widget = self.query_one("#chat", ChatWidget)
            task_widget = self.query_one("#tasks", TaskListWidget)
            thinking_widget = self.query_one("#thinking", ThinkingWidget)
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            user_input_widget = self.query_one("#user_input", UserInputWidget)

            # 禁用输入框
            user_input_widget.disabled = True

            # 清理子 Agent（保留主 Agent）
            agents_to_keep = []
            for agent in GlobalAgentRegistry._agents:
                if agent.name == PROJECT_NAME:
                    agents_to_keep.append(agent)

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

            # 使用单例 Agent
            ari = MainReActAgent()

            # 调用 Agent
            main_task = ari(user_msg)

            # 流式处理
            async for msg, last in GlobalAgentRegistry.stream_all_messages(main_task=main_task):
                await router.route_message(msg, last)
                # 实时更新 Agent 数量
                self._update_status_bar("执行中")

            logger.info("🎉 任务完成")
            await system_message_widget.add_message("✅ 任务执行完成", "success")

        except Exception as e:
            logger.error(f"❌ 任务执行出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            await system_message_widget.add_message(f"❌ 任务执行出错: {e}", "error")

        finally:
            # 释放执行标志并重新启用输入框
            self._task_running = False
            self._update_status_bar("空闲")

            user_input_widget = self.query_one("#user_input", UserInputWidget)
            user_input_widget.disabled = False

            # 重新聚焦输入框
            try:
                input_area = user_input_widget.query_one("#input_area", TextArea)
                input_area.focus()
            except Exception as e:
                logger.warning(f"⚠️ 无法重新聚焦: {e}")

    def action_clear(self):
        """清空所有内容"""
        if self._task_running:
            logger.warning("⚠️ 任务正在执行，无法清空")
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            asyncio.create_task(
                system_message_widget.add_message("⚠️ 任务正在执行，无法清空", "warning")
            )
            return

        async def do_clear():
            """执行清空操作"""
            try:
                # 清理所有 Agent
                GlobalAgentRegistry._agents.clear()
                GlobalAgentRegistry._monitored_agent_ids.clear()

                # 重置主 Agent 单例
                MainReActAgent.reset_instance()
                logger.info("🔄 主 Agent 已重置")

                # 更新状态栏
                self._update_status_bar("空闲")

                # 获取组件
                chat_widget = self.query_one("#chat", ChatWidget)
                task_widget = self.query_one("#tasks", TaskListWidget)
                thinking_widget = self.query_one("#thinking", ThinkingWidget)
                system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
                user_input_widget = self.query_one("#user_input", UserInputWidget)

                # 清空各个组件
                await chat_widget.clear_messages()
                await task_widget.clear_tasks()
                await thinking_widget.clear_thinking()
                await system_message_widget.clear_messages()

                # 清空用户输入（可能是同步方法）
                try:
                    result = user_input_widget.clear()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"⚠️ 清空用户输入失败: {e}")

                await system_message_widget.add_message("✅ 已清空所有内容", "success")

            except Exception as e:
                logger.error(f"❌ 清空操作失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

        asyncio.create_task(do_clear())

    def action_toggle_log(self):
        """切换日志显示"""
        system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
        asyncio.create_task(
            system_message_widget.add_message("ℹ️ 日志功能待实现", "info")
        )


if __name__ == "__main__":
    app = MultiAgentApp()
    try:
        app.theme = "tokyo-night"
    except Exception:
        logger.warning("⚠️ 主题 'tokyo-night' 不可用，使用默认主题")
    app.run()
