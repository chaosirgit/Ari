"""
结果输出区域组件
- 主内容区，支持流式渲染、Markdown、代码高亮
- 自动滚动到底部
- 支持多种消息类型（文本、工具调用、工具结果等）
"""
from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
import json


class ResultOutputDisplay(RichLog):
    """结果输出显示组件"""
    
    def __init__(self) -> None:
        super().__init__(
            id="result-output-display",
            auto_scroll=True,
            wrap=True,
            highlight=True,
            markup=True,
        )
        # 使用 CSS 控制最小宽度
        self.styles.min_width = "50"
    
    def add_message(self, sender: str, content: str, msg_type: str = "text") -> None:
        """添加消息到输出区域
        
        Args:
            sender: 发送者名称
            content: 消息内容
            msg_type: 消息类型 ("text", "thinking", "tool_use", "tool_result")
        """
        if msg_type == "thinking":
            # 思考过程 - 使用灰色斜体
            formatted_content = f"[dim italic]💭 {sender}: {content}[/dim italic]"
            self.write(formatted_content)
            
        elif msg_type == "tool_use":
            # 工具调用 - 使用蓝色
            try:
                # 尝试解析JSON内容
                tool_data = json.loads(content)
                formatted_content = f"[blue]🔧 {sender} 调用工具: {tool_data.get('name', 'unknown')}[/blue]"
                self.write(formatted_content)
                # 显示工具参数
                if "input" in tool_data:
                    input_str = json.dumps(tool_data["input"], indent=2, ensure_ascii=False)
                    syntax = Syntax(input_str, "json", theme="monokai", line_numbers=False)
                    self.write(syntax)
            except (json.JSONDecodeError, TypeError):
                formatted_content = f"[blue]🔧 {sender} 调用工具: {content}[/blue]"
                self.write(formatted_content)
                
        elif msg_type == "tool_result":
            # 工具结果 - 使用绿色
            formatted_content = f"[green]✅ {sender} 工具结果: {content}[/green]"
            self.write(formatted_content)
            
        else:
            # 普通文本消息
            # 检查是否为Markdown格式
            if self._is_markdown_like(content):
                markdown = Markdown(content)
                self.write(f"[bold]{sender}:[/bold]")
                self.write(markdown)
            else:
                formatted_content = f"[bold]{sender}:[/bold] {content}"
                self.write(formatted_content)
    
    def add_streaming_content(self, sender: str, content: str, is_complete: bool = False) -> None:
        """添加流式内容（覆盖式更新）"""
        if is_complete:
            # 完整内容，直接添加
            self.add_message(sender, content)
        else:
            # 流式内容，需要特殊处理
            # Textual 的 RichLog 不直接支持覆盖，所以我们用特殊标记
            if hasattr(self, '_last_streaming_line'):
                # 清除上一行（通过添加空行覆盖的视觉效果）
                pass
            self._last_streaming_line = content
            formatted_content = f"[bold]{sender}:[/bold] {content}▌"
            self.write(formatted_content)
    
    def _is_markdown_like(self, text: str) -> bool:
        """简单判断文本是否类似Markdown"""
        markdown_indicators = ['# ', '## ', '### ', '**', '*', '```', '`', '- ', '1. ']
        return any(indicator in text for indicator in markdown_indicators)
    
    def clear_output(self) -> None:
        """清空输出区域"""
        self.clear()