"""
用户输入区域组件
- 支持中文输入（单次删除键删除完整中文字符）
- 支持方向键、Home/End等标准编辑操作
- 支持粘贴内容换行和回车发送
"""
from textual.widgets import Input
from textual.message import Message


class UserInput(Input):
    """用户输入组件"""
    
    def __init__(self) -> None:
        super().__init__(
            placeholder="请输入您的消息...",
            id="user-input"
        )
    
    def action_submit(self) -> None:
        """提交消息"""
        if self.value.strip():
            self.post_message(self.Submitted(self, self.value))
            self.value = ""
    
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