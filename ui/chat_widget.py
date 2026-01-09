import sys
import base64
import subprocess
import re
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Markdown, Button
from textual.containers import VerticalScroll, Horizontal, Container, Vertical
from agentscope.message import Msg


def copy_to_clipboard(text: str) -> bool:
    """复制到剪贴板（Mac 优化）"""
    try:
        process = subprocess.Popen(
            ['pbcopy'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        process.communicate(text.encode('utf-8'))
        return process.returncode == 0
    except Exception:
        try:
            b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
            sys.stdout.write(f'\033]52;c;{b64}\a')
            sys.stdout.flush()
            return True
        except Exception:
            return False


class CodeBlockWithCopy(Container):
    """单个代码块 + 复制按钮"""

    DEFAULT_CSS = """
    CodeBlockWithCopy {
        width: 100%;
        height: auto;
        background: $panel;
        border: solid $primary;
        padding: 0;
        margin: 1 0;
    }

    CodeBlockWithCopy .code-header {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        padding: 0 1;
    }

    CodeBlockWithCopy .copy-btn {
        dock: right;
        width: 10;
        height: 1;
        min-width: 10;
        background: $primary;
    }

    CodeBlockWithCopy .copy-btn:hover {
        background: $primary-lighten-1;
    }

    CodeBlockWithCopy .code-lang {
        color: $text;
        height: 1;
        text-style: bold;
    }

    CodeBlockWithCopy .code-content {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, code: str, language: str = "", **kwargs):
        super().__init__(**kwargs)
        self.code = code
        self.language = language

    def compose(self) -> ComposeResult:
        """构建UI"""
        with Horizontal(classes="code-header"):
            yield Static(f"📝 {self.language or 'code'}", classes="code-lang")
            yield Button(label="📋 复制", classes="copy-btn",compact=True, id=f"copy-{id(self)}")

        # 使用 Markdown 渲染代码（保持高亮）
        code_md = f"```{self.language}\n{self.code}\n```"
        yield Markdown(code_md, classes="code-content")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理复制"""
        if event.button.id == f"copy-{id(self)}":
            if copy_to_clipboard(self.code):
                event.button.label = "✅ 已复制"
            else:
                event.button.label = "❌ 失败"
            self.set_timer(2, lambda: self._reset_button(event.button))

    def _reset_button(self, button: Button):
        button.label = "📋 复制"


class MessageWithCode(Vertical):
    """包含文本和代码块的消息容器"""

    DEFAULT_CSS = """
    MessageWithCode {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    MessageWithCode Markdown {
        width: 100%;
        height: auto;
        color: $text;
    }
    """

    def __init__(self, markdown_text: str, **kwargs):
        super().__init__(**kwargs)
        self.markdown_text = markdown_text
        self.parts = self._split_content(markdown_text)

    def _split_content(self, text: str) -> list[dict]:
        """分割文本和代码块"""
        pattern = r'```(\w*)\n(.*?)```'
        parts = []
        last_end = 0

        for match in re.finditer(pattern, text, re.DOTALL):
            start, end = match.span()

            # 添加代码块之前的文本
            if start > last_end:
                before_text = text[last_end:start].strip()
                if before_text:
                    parts.append({'type': 'text', 'content': before_text})

            # 添加代码块
            parts.append({
                'type': 'code',
                'language': match.group(1) or 'text',
                'content': match.group(2).strip()
            })

            last_end = end

        # 添加最后剩余的文本
        if last_end < len(text):
            after_text = text[last_end:].strip()
            if after_text:
                parts.append({'type': 'text', 'content': after_text})

        return parts

    def compose(self) -> ComposeResult:
        """渲染所有部分"""
        if not self.parts:
            # 没有代码块，直接渲染 Markdown
            yield Markdown(self.markdown_text)
        else:
            # 逐个渲染文本和代码块
            for part in self.parts:
                if part['type'] == 'text':
                    yield Markdown(part['content'])
                elif part['type'] == 'code':
                    yield CodeBlockWithCopy(
                        code=part['content'],
                        language=part['language']
                    )


class ChatWidget(Widget):
    """聊天区组件，用于显示聊天历史和流式消息"""

    DEFAULT_CSS = """
    ChatWidget {
        width: 100%;
        height: 100%;
    }

    #chat-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        background: $surface;
    }

    .message-sender {
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }

    .message-content {
        margin-bottom: 1;
        color: $text;
    }

    .streaming .message-sender {
        color: $warning;
    }

    .completed .message-sender {
        color: $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stream_widgets = {}
        self.border_title = "💬 聊天区"

    def compose(self) -> ComposeResult:
        """构建UI组件"""
        yield VerticalScroll(id="chat-scroll")

    async def add_message(self, msg: Msg, last: bool):
        """
        添加或更新消息显示（支持流式）

        Args:
            msg: AgentScope 消息对象
            last: 是否是最后一条消息（True=完成，False=流式中）
        """
        sender_name, display_text = self._parse_message(msg)

        if not sender_name or not display_text:
            return

        scroll_container = self.query_one("#chat-scroll", VerticalScroll)

        if last:
            # 消息完成
            if sender_name in self.stream_widgets:
                widgets = self.stream_widgets[sender_name]
                sender_widget = widgets["sender"]
                content_widget = widgets["content"]

                # 更新发送者状态
                sender_widget.update(sender_name)
                sender_widget.remove_class("streaming")
                sender_widget.add_class("completed")

                # 检查是否有代码块
                has_code = bool(re.search(r'```\w*\n.*?```', display_text, re.DOTALL))

                if has_code:
                    # 有代码块：替换为带复制按钮的组件
                    await content_widget.remove()
                    new_content = MessageWithCode(display_text, classes="message-content")
                    await scroll_container.mount(new_content)
                else:
                    # 无代码块：直接更新 Markdown
                    try:
                        await content_widget.update(display_text)
                    except Exception:
                        await content_widget.update(f"```\n{display_text}\n```")

                del self.stream_widgets[sender_name]
            else:
                # 非流式消息直接添加
                sender_widget = Static(
                    sender_name,
                    classes="message-sender completed"
                )

                # 检查是否有代码块
                has_code = bool(re.search(r'```\w*\n.*?```', display_text, re.DOTALL))

                if has_code:
                    content_widget = MessageWithCode(display_text, classes="message-content")
                else:
                    content_widget = Markdown(display_text, classes="message-content")

                await scroll_container.mount(sender_widget)
                await scroll_container.mount(content_widget)

            scroll_container.scroll_end(animate=False)
        else:
            # 流式更新中
            if sender_name in self.stream_widgets:
                widgets = self.stream_widgets[sender_name]
                content_widget = widgets["content"]

                # 流式更新：直接更新 Markdown（不添加复制按钮）
                try:
                    await content_widget.update(display_text)
                except Exception:
                    await content_widget.update(f"```\n{display_text}\n```")
            else:
                # 首次流式消息
                sender_widget = Static(
                    f"{sender_name} ⚡",
                    classes="message-sender streaming"
                )

                content_widget = Markdown(display_text, classes="message-content")

                self.stream_widgets[sender_name] = {
                    "sender": sender_widget,
                    "content": content_widget
                }

                await scroll_container.mount(sender_widget)
                await scroll_container.mount(content_widget)

            scroll_container.scroll_end(animate=False)

    def _parse_message(self, msg: Msg) -> tuple[str, str]:
        """
        解析消息内容

        Returns:
            (sender_name, display_text) 元组
        """
        text_content = ""
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content = block.get("text", "")
                    break
        elif isinstance(msg.content, str):
            text_content = msg.content

        if not text_content and not (isinstance(msg.content, list) and
                                     len(msg.content) > 0 and
                                     isinstance(msg.content[0], dict) and
                                     msg.content[0].get("type") == "tool_use"):
            return "", ""

        try:
            from config import PROJECT_NAME
        except ImportError:
            PROJECT_NAME = "Assistant"

        sender_name = ""
        display_text = ""

        if msg.name == PROJECT_NAME:
            if isinstance(msg.content, list) and len(msg.content) > 0:
                first_block = msg.content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "tool_use":
                    tool_name = first_block.get("name")
                    tool_input = first_block.get("input", {})

                    if tool_name == "_plan_task":
                        task_desc = tool_input.get("task_description", "")
                        if task_desc:
                            sender_name = f"🤖 {PROJECT_NAME}"
                            display_text = f"📋 **规划任务**: {task_desc}"

                    elif tool_name == "create_worker":
                        task_desc = tool_input.get("task_description", "")
                        task_id = tool_input.get("task_id")
                        if task_desc and task_id is not None:
                            sender_name = f"🤖 {PROJECT_NAME}"
                            display_text = f"👷 **分配专家给任务 {task_id}**: {task_desc}"
                else:
                    if text_content:
                        sender_name = f"🤖 {PROJECT_NAME}"
                        display_text = text_content

        elif msg.name == "user" and msg.role == "user":
            if text_content:
                sender_name = "👤 用户"
                display_text = text_content

        elif msg.name == "Planning":
            sender_name = "🧠 规划Agent"
            display_text = text_content if text_content else "正在规划..."

        elif msg.name.startswith("Worker_"):
            try:
                parts = msg.name.split("_")
                if len(parts) >= 2:
                    agent_type = parts[1].replace("Agent", "")
                    task_id = msg.name.split("-")[-1] if "-" in msg.name else "?"
                    sender_name = f"👷 {agent_type} (任务 {task_id})"
                else:
                    sender_name = f"👷 {msg.name}"

                display_text = text_content if text_content else "工作中..."
            except Exception:
                sender_name = f"👷 {msg.name}"
                display_text = text_content if text_content else "工作中..."

        elif msg.name == "system":
            sender_name = "⚙️ 系统"
            display_text = text_content

        else:
            if text_content:
                sender_name = f"💬 {msg.name}"
                display_text = text_content

        return sender_name, display_text

    async def clear_messages(self):
        """清空所有消息"""
        scroll_container = self.query_one("#chat-scroll", VerticalScroll)
        await scroll_container.remove_children()
        self.stream_widgets.clear()
