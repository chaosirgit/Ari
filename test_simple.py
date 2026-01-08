from textual.app import App, ComposeResult
from textual.widgets import Header, RichLog
from textual.widget import Widget
import asyncio


class ChatWidget(Widget):
    DEFAULT_CSS = """
    ChatWidget {
        width: 100%;
        height: 100%;
    }

    #chat-log {
        width: 100%;
        height: 1fr;
        border: solid green;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", markup=True)

    async def add_simple_message(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(text)


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield ChatWidget()

    async def on_mount(self) -> None:
        chat = self.query_one(ChatWidget)

        # 测试消息
        await chat.add_simple_message("[bold cyan]✅ 系统启动[/bold cyan]")
        await asyncio.sleep(0.5)

        await chat.add_simple_message("[bold yellow]👤 用户[/bold yellow]")
        await chat.add_simple_message("你好，测试消息")
        await asyncio.sleep(0.5)

        await chat.add_simple_message("[bold green]🤖 助手[/bold green]")
        await chat.add_simple_message("收到！这是回复")


if __name__ == "__main__":
    app = TestApp()
    app.run()
