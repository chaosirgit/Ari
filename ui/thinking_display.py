"""
思考过程显示区域组件
- 展示内部推理链
- 支持流式更新
- 自动滚动到底部
"""
from textual.widgets import RichLog
from textual.scroll_view import ScrollView


class ThinkingDisplay(RichLog):
    """思考过程显示组件"""
    
    def __init__(self) -> None:
        super().__init__(
            id="thinking-display",
            auto_scroll=True,
            wrap=True,
            highlight=True,
            markup=True
        )
    
    def add_thinking(self, content: str) -> None:
        """添加思考内容"""
        self.write(f"[dim]💭 {content}[/dim]")