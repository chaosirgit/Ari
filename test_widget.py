import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from agentscope.message import Msg
from config import logger
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent

from ui.chat_widget import ChatWidget
from ui.task_list_widget import TaskListWidget
from ui.thinking_widget import ThinkingWidget
from ui.message_router import MessageRouter


class MultiAgentApp(App):
    """多智能体聊天系统"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 1;
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
        yield Footer()

    async def on_mount(self):
        logger.info("🚀 应用启动")
        asyncio.create_task(self.run_agent_task())

    async def run_agent_task(self):
        """运行多智能体任务"""
        try:
            GlobalAgentRegistry._agents.clear()

            # 获取组件
            chat_widget = self.query_one("#chat", ChatWidget)
            task_widget = self.query_one("#tasks", TaskListWidget)
            thinking_widget = self.query_one("#thinking", ThinkingWidget)

            # 创建路由器
            router = MessageRouter(chat_widget, task_widget, thinking_widget)

            # 初始化 Agent
            ari = MainReActAgent()

            # 用户消息
            user_msg = Msg(
                name="user",
                content="我现在要测试一下多智能体的并行运行,你让规划Agent规划 5 个步骤, 2个有依赖,3个无依赖,比如,3个分别计算2+3,6+3,4+3,两个有依赖的计算 3 + 2 * 5",
                role="user"
            )

            await chat_widget.add_message(user_msg, last=True)

            # 调用 Agent
            main_task = ari(user_msg)

            # 流式处理 - 只做路由
            async for msg, last in GlobalAgentRegistry.stream_all_messages(main_task=main_task):
                await router.route_message(msg, last)

            logger.info("🎉 任务完成")

        except Exception as e:
            logger.error(f"❌ 任务执行出错: {e}")

    def action_clear(self):
        """清空所有内容"""
        chat_widget = self.query_one("#chat", ChatWidget)
        task_widget = self.query_one("#tasks", TaskListWidget)
        thinking_widget = self.query_one("#thinking", ThinkingWidget)

        asyncio.create_task(chat_widget.clear_messages())
        asyncio.create_task(task_widget.clear_tasks())
        asyncio.create_task(thinking_widget.clear_thinking())


if __name__ == "__main__":
    app = MultiAgentApp()
    app.run()
