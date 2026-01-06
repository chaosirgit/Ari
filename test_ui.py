"""
简化测试版本 - 用于调试消息显示问题
"""
import asyncio

from agentscope.message import Msg
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Input
from textual.containers import Container

from core import AriAgent


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield Container(
            RichLog(id="output"),
            Input(id="input", placeholder="输入测试..."),
            id="main"
        )
    
    async def on_input_submitted(self, event):
        # 显示用户输入
        output = self.query_one("#output", RichLog)
        output.write(f"👤 用户: {event.value}")
        user_msg = Msg(name="user", content=event.value, role="user")
        ari = AriAgent()
        responses = await ari(user_msg)
        event.input.value = ""
        async for res in responses.get_text_stream():
            output.write(res)


if __name__ == "__main__":
    asyncio.run(TestApp().run_async())