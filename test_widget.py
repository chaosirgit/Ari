import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer

from agentscope.message import Msg
from config import logger
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent

from ui.chat_widget import ChatWidget
from ui.task_list_widget import TaskListWidget
from ui.thinking_widget import ThinkingWidget
from ui.system_message_widget import SystemMessageWidget
from ui.message_router import MessageRouter
from ui.user_input_widget import UserInputWidget, UserInputSubmitted


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
        border: solid cyan;
    }

    #tasks { 
        width: 100%; 
        height: 100%; 
        border: solid green;
    }

    #thinking { 
        width: 100%; 
        height: 100%; 
        border: solid yellow;
    }
    
    #system_messages {
        column-span: 3;
        width: 100%;
        height: 100%;
        border: solid magenta;
    }
    
    #user_input {
        column-span: 3;
        width: 100%;
        height: 100%;
        border: solid blue;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("c", "clear", "清空"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatWidget(id="chat")
        yield TaskListWidget(id="tasks")
        yield ThinkingWidget(id="thinking")
        yield SystemMessageWidget(id="system_messages")
        yield UserInputWidget(id="user_input")
        yield Footer()

    async def on_mount(self):
        logger.info("🚀 应用启动")
        # 不再自动运行任务，等待用户输入
        
    async def on_user_input_submitted(self, event: UserInputSubmitted):
        """处理用户输入提交"""
        try:
            GlobalAgentRegistry._agents.clear()

            # 获取组件
            chat_widget = self.query_one("#chat", ChatWidget)
            task_widget = self.query_one("#tasks", TaskListWidget)
            thinking_widget = self.query_one("#thinking", ThinkingWidget)
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            user_input_widget = self.query_one("#user_input", UserInputWidget)

            # 创建路由器 - 现在包含系统消息组件
            router = MessageRouter(chat_widget, task_widget, thinking_widget, system_message_widget)

            # 用户消息
            user_msg = Msg(
                name="user",
                content=event.content,
                role="user"
            )

            await chat_widget.add_message(user_msg, last=True)

            # 初始化 Agent
            ari = MainReActAgent()

            # 调用 Agent
            main_task = ari(user_msg)

            # 流式处理 - 只做路由
            async for msg, last in GlobalAgentRegistry.stream_all_messages(main_task=main_task):
                await router.route_message(msg, last)

            logger.info("🎉 任务完成")

        except Exception as e:
            logger.error(f"❌ 任务执行出错: {e}")
            # 发送错误到系统消息
            system_message_widget = self.query_one("#system_messages", SystemMessageWidget)
            await system_message_widget.add_message(f"❌ 任务执行出错: {e}", "error")

    def action_clear(self):
        """清空所有内容"""
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
    # 启用 tokyo-night 主题（如果可用）
    try:
        app.theme = "tokyo-night"
    except Exception:
        # 如果主题不可用，使用默认主题
        pass
    app.run()