"""
Ari 终端用户界面主应用模块。

基于 Textual 框架实现的现代化、分区化终端界面。
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    DataTable,
)
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax

from core import AriAgent
from agentscope.message import Msg


class AgentMessage(Message):
    """Agent消息事件"""
    
    def __init__(self, message: Msg) -> None:
        self.message = message
        super().__init__()


class TaskUpdate(Message):
    """任务状态更新事件"""
    
    def __init__(self, task_id: str, status: str, description: str) -> None:
        self.task_id = task_id
        self.status = status
        self.description = description
        super().__init__()


class SystemNotification(Message):
    """系统通知事件"""
    
    def __init__(self, message: str, level: str = "info") -> None:
        self.message = message
        self.level = level
        super().__init__()


class ThinkingDisplay(Static):
    """思考过程显示区域"""
    
    thinking_content = reactive("")
    
    def render(self) -> Text:
        if self.thinking_content:
            return Text(f"💭 {self.thinking_content}", style="yellow")
        return Text("💭 等待输入...", style="dim yellow")


class TaskStatusTable(DataTable):
    """任务状态表格"""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.show_header = True
        self.cursor_type = "none"
        self.fixed_columns = 0
        
    def on_mount(self) -> None:
        self.add_column("状态", width=4)
        self.add_column("任务", width=12)
        self.add_column("描述", width=40)
        self.add_column("进度", width=8)


class ResultOutput(RichLog):
    """结果输出区域"""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(wrap=True, markup=True, highlight=True, auto_scroll=True, **kwargs)
        self.can_focus = False


class SystemMessageLog(RichLog):
    """系统消息日志"""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(wrap=True, markup=True, highlight=True, auto_scroll=True, max_lines=10, **kwargs)
        self.can_focus = False


class UserInput(Input):
    """用户输入区域 - 完美支持中文"""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(placeholder="请输入您的消息 (Enter发送, Ctrl+C中断)...", **kwargs)
        # 不设置固定高度，让容器控制
    
    def action_cursor_left(self) -> None:
        """处理光标左移 - 完美支持中文字符"""
        if self.value and self.cursor_position > 0:
            # 检查当前位置是否在中文字符中间
            char_before = self.value[self.cursor_position - 1]
            if '\u4e00' <= char_before <= '\u9fff':  # 中文字符范围
                self.cursor_position -= 1
            else:
                self.cursor_position -= 1
    
    def action_cursor_right(self) -> None:
        """处理光标右移 - 完美支持中文字符"""
        if self.cursor_position < len(self.value):
            char_after = self.value[self.cursor_position]
            if '\u4e00' <= char_after <= '\u9fff':  # 中文字符范围
                self.cursor_position += 1
            else:
                self.cursor_position += 1
    
    def action_delete_left(self) -> None:
        """处理删除键 - 完美支持中文字符"""
        if self.value and self.cursor_position > 0:
            char_to_delete = self.value[self.cursor_position - 1]
            if '\u4e00' <= char_to_delete <= '\u9fff':  # 中文字符
                # 删除整个中文字符
                new_value = (
                    self.value[: self.cursor_position - 1] 
                    + self.value[self.cursor_position:]
                )
                self.cursor_position -= 1
                self.value = new_value
            else:
                # 删除普通字符
                super().action_delete_left()


class AriApp(App):
    """Ari 主应用程序"""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 12;
        grid-rows: 3 1fr 10 8 8 5;
        grid-gutter: 1;
        background: $surface;
    }
    
    #header {
        column-span: 12;
        height: 3;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    
    #thinking-area {
        column-span: 4;
        height: 1fr;
        background: $surface-lighten-1;
        border: round $secondary;
        padding: 1;
    }
    
    #task-status {
        column-span: 4;
        height: 1fr;
        background: $surface-lighten-1;
        border: round $secondary;
    }
    
    #result-area {
        column-span: 8;
        height: 1fr;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    
    #system-messages {
        column-span: 12;
        height: 8;
        background: $surface-darken-1;
        border: round $warning;
        padding: 1;
    }
    
    #user-input-area {
        column-span: 12;
        height: 5;
        background: $surface;
        border: round $primary;
        margin-top: 1;
    }
    
    #task-table {
        height: 100%;
        width: 100%;
    }
    
    #result-output {
        height: 100%;
        width: 100%;
    }
    
    #system-log {
        height: 100%;
        width: 100%;
    }
    
    #user-input {
        height: 100%;
        width: 100%;
        border: none;
        padding: 1;
    }
    
    DataTable {
        background: $surface;
        scrollbar-color: $primary;
        scrollbar-color-active: $secondary;
    }
    
    DataTable > .datatable--cursor {
        background: $primary-lighten-1;
    }
    
    RichLog {
        background: $surface;
    }
    
    Input {
        background: $surface;
        color: $text;
        border: none;
    }
    
    Input:focus {
        background: $surface;
        color: $text;
        border: none;
    }
    
    /* 状态图标颜色 */
    .status-pending {
        color: $warning;
    }
    
    .status-running {
        color: $success;
    }
    
    .status-completed {
        color: $success;
    }
    
    .status-error {
        color: $error;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "中断"),
        Binding("ctrl+q", "quit", "退出"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.ari_agent: Optional[AriAgent] = None
        self.current_tasks: Dict[str, Dict[str, Any]] = {}
        self.is_processing = False
    
    def compose(self) -> ComposeResult:
        """构建UI组件"""
        yield Header(show_clock=True)
        yield Container(
            ThinkingDisplay(id="thinking-display"),
            id="thinking-area"
        )
        yield Container(
            TaskStatusTable(id="task-table"),
            id="task-status"
        )
        yield Container(
            ResultOutput(id="result-output"),
            id="result-area"
        )
        yield Container(
            SystemMessageLog(id="system-log"),
            id="system-messages"
        )
        yield Container(
            UserInput(id="user-input"),
            id="user-input-area"
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """应用启动时初始化"""
        await self.initialize_agent()
        # 确保输入框获得焦点
        input_widget = self.query_one("#user-input", UserInput)
        input_widget.focus()
        
        # 显示欢迎消息
        welcome_msg = Text.from_markup(
            "[bold cyan]🌟 欢迎使用 Ari - 自主认知型AI实体[/bold cyan]\n"
            "[dim]请输入您的请求，Ari将为您提供智能协助...[/dim]"
        )
        self.query_one("#result-output", ResultOutput).write(welcome_msg)
    
    async def initialize_agent(self) -> None:
        """初始化Ari Agent"""
        try:
            # AriAgent() 返回的是同步对象，不需要 await
            self.ari_agent = AriAgent()
            # post_message 是同步方法，不需要 await
            self.post_message(SystemNotification("Ari Agent 初始化成功", "success"))
        except Exception as e:
            # post_message 是同步方法，不需要 await
            self.post_message(SystemNotification(f"Ari Agent 初始化失败: {str(e)}", "error"))
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入提交"""
        if not event.value.strip():
            return
            
        if self.is_processing:
            self.post_message(SystemNotification("正在处理中，请稍候...", "warning"))
            return
        
        user_input = event.value
        event.input.value = ""  # 清空输入框
        
        # 显示用户消息
        try:
            user_msg = Text.from_markup(f"[bold green]👤 用户:[/bold green] {user_input}")
            result_output = self.query_one("#result-output", ResultOutput)
            result_output.write(user_msg)
            # 确保自动滚动到底部
            result_output.scroll_end(animate=False)
        except Exception as e:
            self.post_message(SystemNotification(f"显示用户消息失败: {str(e)}", "error"))
        
        # 开始处理
        self.is_processing = True
        await self.process_user_message(user_input)
        self.is_processing = False
    
    async def process_user_message(self, message: str) -> None:
        """处理用户消息"""
        if not self.ari_agent:
            self.post_message(SystemNotification("Agent未初始化", "error"))
            return
        
        try:
            # 创建消息对象
            user_msg = Msg(name="user", content=message, role="user")
            
            # 更新思考状态
            thinking_display = self.query_one("#thinking-display", ThinkingDisplay)
            thinking_display.thinking_content = "分析任务类型..."
            
            # 处理消息（这将触发完整的Handoffs工作流）
            response = await self.ari_agent(user_msg)
            
            # 提取响应文本 - 处理AgentScope的响应格式
            response_text = ""
            if isinstance(response.content, list):
                # AgentScope返回的是消息列表
                text_parts = []
                for item in response.content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif isinstance(item, str):
                        text_parts.append(item)
                response_text = "\n".join(text_parts)
            else:
                # 直接是字符串
                response_text = str(response.content)
            
            # 显示响应
            if response_text:
                # 检查是否包含Markdown或代码
                if "```" in response_text:
                    # 包含代码块，使用Syntax高亮
                    lines = response_text.split('\n')
                    code_blocks = []
                    current_block = []
                    in_code_block = False
                    
                    for line in lines:
                        if line.strip().startswith('```'):
                            if in_code_block:
                                # 结束代码块
                                language = current_block[0].replace('```', '').strip() if current_block else 'python'
                                code_content = '\n'.join(current_block[1:]) if len(current_block) > 1 else ''
                                code_blocks.append(Syntax(code_content, language, theme="monokai"))
                                current_block = []
                                in_code_block = False
                            else:
                                # 开始代码块
                                in_code_block = True
                                current_block = [line]
                        elif in_code_block:
                            current_block.append(line)
                        else:
                            if current_block:
                                # 非代码内容
                                code_blocks.append(Text(line))
                            else:
                                code_blocks.append(Text(line))
                    
                    # 写入结果
                    result_output = self.query_one("#result-output", ResultOutput)
                    for block in code_blocks:
                        result_output.write(block)
                    result_output.scroll_end(animate=False)
                else:
                    # 普通文本，检查是否为Markdown
                    try:
                        markdown_content = Markdown(response_text)
                        result_output = self.query_one("#result-output", ResultOutput)
                        result_output.write(markdown_content)
                        result_output.scroll_end(animate=False)
                    except:
                        # 纯文本
                        ai_msg = Text.from_markup(f"[bold blue]🤖 Ari:[/bold blue] {response_text}")
                        result_output = self.query_one("#result-output", ResultOutput)
                        result_output.write(ai_msg)
                        result_output.scroll_end(animate=False)
            else:
                ai_msg = Text.from_markup(f"[bold blue]🤖 Ari:[/bold blue] 无响应内容")
                result_output = self.query_one("#result-output", ResultOutput)
                result_output.write(ai_msg)
                result_output.scroll_end(animate=False)
                
        except Exception as e:
            error_msg = Text.from_markup(f"[bold red]❌ 错误:[/bold red] {str(e)}")
            result_output = self.query_one("#result-output", ResultOutput)
            result_output.write(error_msg)
            result_output.scroll_end(animate=False)
            self.post_message(SystemNotification(f"处理消息时出错: {str(e)}", "error"))
        finally:
            # 重置思考状态
            thinking_display = self.query_one("#thinking-display", ThinkingDisplay)
            thinking_display.thinking_content = ""
    
    async def on_agent_message(self, event: AgentMessage) -> None:
        """处理Agent消息事件"""
        # 这里可以添加更详细的Agent内部消息处理
        pass
    
    async def on_task_update(self, event: TaskUpdate) -> None:
        """处理任务状态更新"""
        # 更新任务状态表
        task_table = self.query_one("#task-table", TaskStatusTable)
        
        # 获取状态图标和样式
        status_icons = {
            "pending": "⏳",
            "running": "🔄", 
            "completed": "✅",
            "error": "❌"
        }
        status_icon = status_icons.get(event.status, "❓")
        
        # 更新或添加任务行
        if event.task_id in self.current_tasks:
            # 更新现有任务
            row_key = f"task_{event.task_id}"
            task_table.update_cell(row_key, "状态", status_icon)
            task_table.update_cell(row_key, "任务", event.task_id)
            task_table.update_cell(row_key, "描述", event.description)
            task_table.update_cell(row_key, "进度", event.status)
        else:
            # 添加新任务
            row_key = f"task_{event.task_id}"
            task_table.add_row(
                status_icon,
                event.task_id,
                event.description,
                event.status,
                key=row_key
            )
            self.current_tasks[event.task_id] = {
                "status": event.status,
                "description": event.description
            }
    
    async def on_system_notification(self, event: SystemNotification) -> None:
        """处理系统通知"""
        system_log = self.query_one("#system-log", SystemMessageLog)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {
            "info": "cyan",
            "success": "green", 
            "warning": "yellow",
            "error": "red"
        }
        color = level_colors.get(event.level, "white")
        
        notification = Text.from_markup(
            f"[{color}][{timestamp}] [{event.level.upper()}][/]: {event.message}"
        )
        system_log.write(notification)
    
    def action_interrupt(self) -> None:
        """中断当前操作"""
        if self.is_processing:
            self.is_processing = False
            # 使用 call_later 而不是 create_task
            self.call_later(self.post_message, SystemNotification("操作已中断", "warning"))
    
    def action_quit(self) -> None:
        """退出应用"""
        self.exit()


if __name__ == "__main__":
    app = AriApp()
    app.run()