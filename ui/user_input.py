"""
用户输入区域组件
- 支持中文输入（单次删除键删除完整中文字符）
- 支持多行输入（到达宽度自动换行）
- 回车 (Enter) 提交消息
- Ctrl+N 手动换行
- 支持方向键、Home/End等标准编辑操作
"""
from textual.widgets import TextArea
from textual.message import Message
from textual.binding import Binding
from textual.events import Key


class UserInput(TextArea):
    """用户输入组件 - 支持多行输入和自定义快捷键"""
    
    BINDINGS = [
        Binding("ctrl+n", "insert_newline", "换行", show=True),
        Binding("ctrl+c", "interrupt", "中断", show=True),
        # 注意：回车键通过 on_key 事件处理，不在 BINDINGS 中
    ]
    
    def __init__(self) -> None:
        super().__init__(
            placeholder="请输入您的消息...",
            id="user-input",
            show_line_numbers=False,
            language="",
            theme="monokai",
        )
        self.styles.height = "100%"
    
    def on_key(self, event: Key) -> None:
        """处理键盘事件"""
        if event.key == "enter":
            # 回车键提交消息
            event.stop()  # 阻止默认的换行行为
            self.action_submit()
        elif event.key == "ctrl+n":
            # Ctrl+N 换行
            event.stop()  # 阻止其他处理
            self.action_insert_newline()
    
    def action_submit(self) -> None:
        """提交消息（回车键）"""
        if self.text.strip():
            self.post_message(self.Submitted(self, self.text))
            self.text = ""
    
    def action_insert_newline(self) -> None:
        """插入换行符（Ctrl+N）"""
        self.insert("\n")
    
    def action_interrupt(self) -> None:
        """中断当前操作"""
        self.post_message(self.Interrupted(self))
    
    class Submitted(Message):
        """消息提交事件"""
        def __init__(self, input_widget, value: str) -> None:
            self.input = input_widget
            self.value = value
            super().__init__()
    
    class Interrupted(Message):
        """中断事件"""
        def __init__(self, input_widget) -> None:
            self.input = input_widget
            super().__init__()