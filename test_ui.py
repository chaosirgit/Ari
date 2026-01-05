"""
简化测试版本 - 用于调试消息显示问题
"""

from textual.app import App, ComposeResult
from textual.widgets import RichLog, Input
from textual.containers import Container

class TestApp(App):
    def compose(self) -> ComposeResult:
        yield Container(
            RichLog(id="output"),
            Input(id="input", placeholder="输入测试..."),
            id="main"
        )
    
    def on_input_submitted(self, event):
        # 显示用户输入
        output = self.query_one("#output", RichLog)
        output.write(f"👤 用户: {event.value}")
        event.input.value = ""

if __name__ == "__main__":
    TestApp().run()