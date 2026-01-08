from agentscope.message import Msg
from textual.app import App, ComposeResult
import asyncio

from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent
from ui.chat_widget import ChatWidget


class ChatApp(App):
    """聊天应用"""

    TITLE = "Multi-Agent Chat System"

    def compose(self) -> ComposeResult:
        yield ChatWidget()

    async def on_mount(self) -> None:
        """挂载后初始化 - 快速返回，不阻塞"""
        chat = self.query_one(ChatWidget)

        # 显示启动消息
        system_msg = Msg(name="system", content="✅ 系统已启动", role="assistant")
        await chat.add_message(system_msg, last=True)

        # 🔥 关键：将 Agent 任务放到后台运行
        asyncio.create_task(self.run_agent_task())

    async def run_agent_task(self):
        """在后台运行 Agent 任务"""
        chat = self.query_one(ChatWidget)

        # 等待一下让界面先渲染
        await asyncio.sleep(0.5)

        try:
            # 初始化主 Agent
            self.log("Initializing MainReActAgent...")
            ari = MainReActAgent()

            # 创建用户消息
            user_msg = Msg(
                name="user",
                content="我现在要测试一下多智能体的并行运行,你让规划Agent规划 5 个步骤, 2个有依赖,3个无依赖,比如,3个分别计算2+3,6+3,4+3,两个有依赖的计算 3 + 2 * 5",
                role="user"
            )

            # 显示用户消息
            await chat.add_message(user_msg, last=True)
            self.log("User message added, starting agent...")

            # 流式接收并显示 Agent 响应
            async for msg, last in GlobalAgentRegistry.stream_all_messages(
                    main_task=ari(user_msg),
            ):
                self.log(f"Received: {msg.name}, last={last}")
                await chat.add_message(msg, last)

                # 🔥 关键：让出控制权，允许界面更新
                await asyncio.sleep(0)

        except Exception as e:
            self.log.error(f"Error: {e}")
            import traceback
            self.log.error(traceback.format_exc())

            # 显示错误
            error_msg = Msg(
                name="system",
                content=f"❌ 错误: {str(e)}",
                role="assistant"
            )
            await chat.add_message(error_msg, last=True)


if __name__ == "__main__":
    GlobalAgentRegistry._agents.clear()
    app = ChatApp()
    app.run()
