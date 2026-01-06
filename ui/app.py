"""
Ari 终端用户界面主应用模块。

基于 Textual 框架实现的现代化、分区化终端界面。
"""

import asyncio
import os
import json
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
        super().__init__(wrap=True, markup=True, highlight=True, auto_scroll=True, max_lines=50, **kwargs)
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


def format_message_log(msg, prefix=""):
    """格式化消息结构日志用于UI显示"""
    try:
        log_lines = []
        log_lines.append(f"=== {prefix} MESSAGE LOG ===")

        if isinstance(msg, Msg):
            log_lines.append(f"Type: Msg")
            log_lines.append(f"Name: {msg.name}")
            log_lines.append(f"Role: {msg.role}")
            log_lines.append(f"Content Type: {type(msg.content).__name__}")

            if isinstance(msg.content, list):
                log_lines.append("Content (list):")
                for i, item in enumerate(msg.content[:3]):  # 只显示前3项
                    if isinstance(item, dict):
                        log_lines.append(f"  [{i}] Dict with keys: {list(item.keys())}")
                        if 'text' in item:
                            preview = str(item['text'])[:100]
                            log_lines.append(f"      Text preview: {preview}")
                    else:
                        preview = str(item)[:100]
                        log_lines.append(f"  [{i}] {type(item).__name__}: {preview}")
                if len(msg.content) > 3:
                    log_lines.append(f"  ... and {len(msg.content) - 3} more items")
            else:
                content_preview = str(msg.content)[:200]
                log_lines.append(f"Content: {content_preview}")

        elif isinstance(msg, dict):
            log_lines.append(f"Type: dict")
            log_lines.append(f"Keys: {list(msg.keys())}")
            for k, v in list(msg.items())[:3]:
                preview = str(v)[:100]
                log_lines.append(f"  {k}: {preview}")
            if len(msg) > 3:
                log_lines.append(f"  ... and {len(msg) - 3} more keys")
        else:
            log_lines.append(f"Type: {type(msg).__name__}")
            preview = str(msg)[:200]
            log_lines.append(f"Value: {preview}")

        log_lines.append("=" * 50)
        return "\n".join(log_lines)

    except Exception as e:
        return f"Error formatting message log: {e}"


def extract_ai_response_text(response: Msg) -> str:
    """
    从AgentScope响应中提取真正的AI回复文本，过滤掉系统日志。
    
    Args:
        response: AgentScope的Msg响应对象
        
    Returns:
        str: 提取的纯文本回复
    """
    content = response.content
    
    # 如果content是字符串，直接返回
    if isinstance(content, str):
        return content.strip()
    
    # 如果content是列表，需要仔细解析
    if isinstance(content, list):
        text_parts = []
        for item in content:
            # 处理字典类型的项目（可能是OpenAI格式的消息）
            if isinstance(item, dict):
                # 优先检查'text'字段
                if 'text' in item:
                    text_parts.append(str(item['text']))
                # 检查'content'字段
                elif 'content' in item:
                    content_val = item['content']
                    if isinstance(content_val, str):
                        text_parts.append(content_val)
                    elif isinstance(content_val, list):
                        # 处理content为列表的情况（如多模态消息）
                        for sub_item in content_val:
                            if isinstance(sub_item, dict) and sub_item.get('type') == 'text':
                                text_parts.append(sub_item.get('text', ''))
            # 处理字符串类型的项目
            elif isinstance(item, str):
                text_parts.append(item)
        
        return "\n".join(text_parts).strip()
    
    # 其他类型转换为字符串
    return str(content).strip()


class AriApp(App):
    """Ari 主应用程序"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 12;
        grid-rows: 3 1fr 10 12 8 5;
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
        border: double $success;
        padding: 1;
    }

    #system-messages {
        column-span: 12;
        height: 12;
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
        Binding("ctrl+l", "clear_logs", "清空日志"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.ari_agent: Optional[AriAgent] = None
        self.current_tasks: Dict[str, Dict[str, Any]] = {}
        self.is_processing = False
        # 确保logs目录存在
        os.makedirs("logs", exist_ok=True)
        self.log_file_path = "logs/debug_log.log"

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

        # 记录初始化日志到系统消息区
        self._log_to_system("ARI APP INITIALIZED", "Ari应用程序已成功启动")

    async def initialize_agent(self) -> None:
        """初始化Ari Agent"""
        try:
            # AriAgent() 返回的是同步对象，不需要 await
            self.ari_agent = AriAgent()
            # post_message 是同步方法，不需要 await
            self.post_message(SystemNotification("Ari Agent 初始化成功", "success"))
            self._log_to_system("AGENT INITIALIZED", "Ari Agent 已成功初始化")
        except Exception as e:
            # post_message 是同步方法，不需要 await
            self.post_message(SystemNotification(f"Ari Agent 初始化失败: {str(e)}", "error"))
            self._log_to_system("AGENT INIT ERROR", f"初始化失败: {str(e)}")

    def _write_log_to_file(self, title: str, message: str):
        """将日志写入文件"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] 📋 {title}\n{message}\n{'='*50}\n"

            # 使用追加模式写入文件
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # 如果文件写入失败，至少记录到UI
            error_msg = f"Failed to write to log file: {str(e)}"
            print(error_msg)  # 这会在Textual后台输出

    def _log_to_system(self, title: str, message: str):
        """将日志消息发送到系统消息区域并写入文件"""
        # 写入文件
        self._write_log_to_file(title, message)

        # 显示在UI中
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = Text.from_markup(
            f"[yellow][{timestamp}] 📋 {title}[/yellow]\n[dim]{message}[/dim]"
        )
        system_log = self.query_one("#system-log", SystemMessageLog)
        system_log.write(log_entry)

    def _log_message_structure(self, msg, prefix: str):
        """将消息结构日志发送到系统消息区域并写入文件"""
        formatted_log = format_message_log(msg, prefix)

        # 写入文件
        self._write_log_to_file(f"{prefix} MESSAGE LOG", formatted_log)

        # 显示在UI中
        system_log = self.query_one("#system-log", SystemMessageLog)
        system_log.write(Text(formatted_log))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入提交"""
        if not event.value.strip():
            return

        if self.is_processing:
            self.post_message(SystemNotification("正在处理中，请稍候...", "warning"))
            return

        user_input = event.value
        event.input.value = ""  # 清空输入框

        # 记录用户输入日志
        self._log_to_system("USER INPUT RECEIVED", f"Input: '{user_input}' (length: {len(user_input)})")

        # 显示用户消息
        try:
            user_msg = Text.from_markup(f"[bold green]👤 用户:[/bold green] {user_input}")
            result_output = self.query_one("#result-output", ResultOutput)
            result_output.write(user_msg)
            result_output.scroll_end(animate=False)

            self._log_to_system("USER MESSAGE DISPLAYED", "用户消息已成功显示在结果区域")

        except Exception as e:
            self.post_message(SystemNotification(f"显示用户消息失败: {str(e)}", "error"))
            self._log_to_system("USER MESSAGE DISPLAY ERROR", f"显示失败: {str(e)}")

        # 开始处理
        self.is_processing = True
        await self.process_user_message(user_input)
        self.is_processing = False

    async def process_user_message(self, message: str) -> None:
        """处理用户消息"""
        if not self.ari_agent:
            self.post_message(SystemNotification("Agent未初始化", "error"))
            self._log_to_system("PROCESS ERROR", "Agent未初始化，无法处理消息")
            return

        try:
            # 创建消息对象
            user_msg = Msg(name="user", content=message, role="user")

            # 记录发送给Agent的消息
            self._log_message_structure(user_msg, "SENT TO AGENT")

            # 更新思考状态
            thinking_display = self.query_one("#thinking-display", ThinkingDisplay)
            thinking_display.thinking_content = "分析任务类型..."

            # 处理消息（这将触发完整的Handoffs工作流）
            response = await self.ari_agent(user_msg)

            # 记录从Agent收到的响应
            self._log_message_structure(response, "RECEIVED FROM AGENT")

            # 提取真正的AI回复文本，过滤掉系统日志
            response_text = extract_ai_response_text(response)

            # 记录提取的文本
            self._log_to_system("EXTRACTED RESPONSE TEXT", f"Length: {len(response_text)}, Preview: {response_text[:100]}")

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
                    result_output.refresh()

                    self._log_to_system("CODE BLOCK RESPONSE DISPLAYED", "代码块响应已成功显示")

                else:
                    # 普通文本，检查是否为Markdown
                    try:
                        markdown_content = Markdown(response_text)
                        result_output = self.query_one("#result-output", ResultOutput)
                        result_output.write(markdown_content)
                        result_output.scroll_end(animate=False)
                        result_output.refresh()

                        self._log_to_system("MARKDOWN RESPONSE DISPLAYED", "Markdown响应已成功显示")

                    except Exception as md_error:
                        # 纯文本
                        ai_msg = Text.from_markup(f"[bold blue]🤖 Ari:[/bold blue] {response_text}")
                        result_output = self.query_one("#result-output", ResultOutput)
                        result_output.write(ai_msg)
                        result_output.scroll_end(animate=False)
                        result_output.refresh()

                        self._log_to_system("PLAIN TEXT RESPONSE DISPLAYED", f"纯文本响应已显示. Markdown error: {md_error}")
            else:
                ai_msg = Text.from_markup(f"[bold blue]🤖 Ari:[/bold blue] 无响应内容")
                result_output = self.query_one("#result-output", ResultOutput)
                result_output.write(ai_msg)
                result_output.scroll_end(animate=False)
                result_output.refresh()

                self._log_to_system("EMPTY RESPONSE HANDLED", "收到空响应，显示默认消息")

        except Exception as e:
            error_msg = Text.from_markup(f"[bold red]❌ 错误:[/bold red] {str(e)}")
            result_output = self.query_one("#result-output", ResultOutput)
            result_output.write(error_msg)
            result_output.scroll_end(animate=False)
            result_output.refresh()
            self.post_message(SystemNotification(f"处理消息时出错: {str(e)}", "error"))

            self._log_to_system("PROCESSING ERROR", f"异常: {str(e)}")
            import traceback
            self._log_to_system("TRACEBACK", f"{traceback.format_exc()}")
        finally:
            # 重置思考状态
            thinking_display = self.query_one("#thinking-display", ThinkingDisplay)
            thinking_display.thinking_content = ""

            self._log_to_system("MESSAGE PROCESSING COMPLETED", "消息处理流程已完成")

    async def on_agent_message(self, event: AgentMessage) -> None:
        """处理Agent消息事件"""
        pass

    async def on_task_update(self, event: TaskUpdate) -> None:
        """处理任务状态更新"""
        task_table = self.query_one("#task-table", TaskStatusTable)

        status_icons = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "error": "❌"
        }
        status_icon = status_icons.get(event.status, "❓")

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
            self.call_later(self.post_message, SystemNotification("操作已中断", "warning"))

    def action_clear_logs(self) -> None:
        """清空系统日志"""
        system_log = self.query_one("#system-log", SystemMessageLog)
        system_log.clear()
        self.post_message(SystemNotification("系统日志已清空", "info"))

    def action_quit(self) -> None:
        """退出应用"""
        self.exit()


if __name__ == "__main__":
    app = AriApp()
    app.run()