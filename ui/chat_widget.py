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
        width: 6;
        height: 1;
        min-width: 6;
        background: $primary;
        padding: 0;
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
        self._markdown_widget = None

    def compose(self) -> ComposeResult:
        """构建UI"""
        with Horizontal(classes="code-header"):
            yield Static(f"📝 {self.language or 'code'}", classes="code-lang")
            yield Button(label="[copy]", classes="copy-btn", variant="primary", compact=True, id=f"copy-{id(self)}")

        # 使用 Markdown 渲染代码（保持高亮）
        code_md = f"```{self.language}\n{self.code}\n```"
        yield Markdown(code_md, classes="code-content")

    def on_mount(self) -> None:
        """缓存 Markdown 组件"""
        self._markdown_widget = self.query_one(".code-content", Markdown)

    def update_code(self, new_code: str):
        """更新代码内容（不重建组件）"""
        if self.code == new_code:
            return

        self.code = new_code
        if self._markdown_widget:
            code_md = f"```{self.language}\n{self.code}\n```"
            self._markdown_widget.update(code_md)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理复制"""
        if event.button.id == f"copy-{id(self)}":
            if copy_to_clipboard(self.code):
                event.button.label = "[ok]"
            else:
                event.button.label = "[x]"
            self.set_timer(2, lambda: self._reset_button(event.button))

    def _reset_button(self, button: Button):
        button.label = "[copy]"


class MessageWithCode(Vertical):
    """包含文本和代码块的消息容器（优化版 - 支持增量更新）"""

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
        self.parts = []
        self._part_widgets = []  # 缓存已渲染的组件

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
        """初始渲染"""
        self.parts = self._split_content(self.markdown_text)

        for part in self.parts:
            if part['type'] == 'text':
                widget = Markdown(part['content'])
            elif part['type'] == 'code':
                widget = CodeBlockWithCopy(
                    code=part['content'],
                    language=part['language']
                )
            self._part_widgets.append(widget)
            yield widget

    async def update_content(self, new_text: str):
        """增量更新内容（避免闪屏）"""
        if self.markdown_text == new_text:
            return

        self.markdown_text = new_text
        new_parts = self._split_content(new_text)

        # 比较新旧部分，只更新变化的部分
        old_len = len(self.parts)
        new_len = len(new_parts)

        # 更新现有部分
        for i in range(min(old_len, new_len)):
            old_part = self.parts[i]
            new_part = new_parts[i]

            # 类型相同，更新内容
            if old_part['type'] == new_part['type']:
                if old_part['content'] != new_part['content']:
                    widget = self._part_widgets[i]
                    if new_part['type'] == 'text' and isinstance(widget, Markdown):
                        widget.update(new_part['content'])
                    elif new_part['type'] == 'code' and isinstance(widget, CodeBlockWithCopy):
                        widget.update_code(new_part['content'])
            else:
                # 类型不同，需要重建（少见情况）
                await self._rebuild_from_index(i, new_parts)
                return

        # 添加新增的部分
        if new_len > old_len:
            for i in range(old_len, new_len):
                part = new_parts[i]
                if part['type'] == 'text':
                    widget = Markdown(part['content'])
                elif part['type'] == 'code':
                    widget = CodeBlockWithCopy(
                        code=part['content'],
                        language=part['language']
                    )
                self._part_widgets.append(widget)
                await self.mount(widget)

        # 移除多余的部分
        elif new_len < old_len:
            for i in range(new_len, old_len):
                widget = self._part_widgets[i]
                await widget.remove()
            self._part_widgets = self._part_widgets[:new_len]

        self.parts = new_parts

    async def _rebuild_from_index(self, start_index: int, new_parts: list[dict]):
        """从指定索引重建（类型变化时的回退方案）"""
        # 移除旧组件
        for i in range(start_index, len(self._part_widgets)):
            await self._part_widgets[i].remove()

        self._part_widgets = self._part_widgets[:start_index]

        # 添加新组件
        for i in range(start_index, len(new_parts)):
            part = new_parts[i]
            if part['type'] == 'text':
                widget = Markdown(part['content'])
            elif part['type'] == 'code':
                widget = CodeBlockWithCopy(
                    code=part['content'],
                    language=part['language']
                )
            self._part_widgets.append(widget)
            await self.mount(widget)

        self.parts = new_parts


class MessageBlock(Container):
    """单条消息块（发送者 + 内容 + 复制按钮）"""

    DEFAULT_CSS = """
    MessageBlock {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    MessageBlock .message-header {
        width: 100%;
        height: 1;
        margin-top: 1;
    }

    MessageBlock .message-copy-btn {
        width: 8;
        height: 1;
        min-width: 8;
        background: $surface-darken-1;
        padding: 0;
        margin-left: 1;
    }

    MessageBlock .message-copy-btn:hover {
        background: $primary;
    }

    MessageBlock .message-sender {
        color: $accent;
        text-style: bold;
        height: 1;
        margin-left: 1;
    }

    MessageBlock .message-content {
        width: 100%;
        height: auto;
        color: $text;
    }

    MessageBlock.streaming .message-sender {
        color: $warning;
    }

    MessageBlock.completed .message-sender {
        color: $accent;
    }
    """

    def __init__(self, sender_name: str, content_text: str, is_streaming: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.sender_name = sender_name
        self.content_text = content_text
        self.is_streaming = is_streaming
        self.has_code = bool(re.search(r'```\w*\n.*?```', content_text, re.DOTALL))
        self._content_widget = None  # 缓存内容组件
        self._sender_widget = None  # 缓存发送者组件

        if is_streaming:
            self.add_class("streaming")
        else:
            self.add_class("completed")

    def compose(self) -> ComposeResult:
        """构建UI"""
        # 消息头（复制按钮 + 发送者）
        with Horizontal(classes="message-header"):
            yield Button(label="[copy]", classes="message-copy-btn", variant="default", compact=True,
                         id=f"msg-copy-{id(self)}")
            sender_text = f"{self.sender_name} ⚡" if self.is_streaming else self.sender_name
            yield Static(sender_text, classes="message-sender")

        # 消息内容
        if self.has_code:
            yield MessageWithCode(self.content_text, classes="message-content")
        else:
            yield Markdown(self.content_text, classes="message-content")

    def on_mount(self) -> None:
        """挂载后缓存组件引用"""
        self._sender_widget = self.query_one(".message-sender", Static)
        self._content_widget = self.query_one(".message-content")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理复制整条消息"""
        if event.button.id == f"msg-copy-{id(self)}":
            if copy_to_clipboard(self.content_text):
                event.button.label = "[ok]"
            else:
                event.button.label = "[x]"
            self.set_timer(2, lambda: self._reset_button(event.button))

    def _reset_button(self, button: Button):
        button.label = "[copy]"

    async def update_content(self, new_content: str, is_streaming: bool = False):
        """更新消息内容（优化版 - 避免闪屏）"""
        # 检查内容是否真的变化
        if self.content_text == new_content and self.is_streaming == is_streaming:
            return

        old_is_streaming = self.is_streaming
        self.content_text = new_content
        self.is_streaming = is_streaming
        new_has_code = bool(re.search(r'```\w*\n.*?```', new_content, re.DOTALL))

        # 更新样式
        if is_streaming:
            self.remove_class("completed")
            self.add_class("streaming")
        else:
            self.remove_class("streaming")
            self.add_class("completed")

        # 更新发送者文本（只在状态变化时更新）
        if self._sender_widget and old_is_streaming != is_streaming:
            sender_text = f"{self.sender_name} ⚡" if is_streaming else self.sender_name
            self._sender_widget.update(sender_text)

        # 内容类型变化：纯文本 ↔ 有代码
        if new_has_code != self.has_code:
            self.has_code = new_has_code
            if self._content_widget:
                await self._content_widget.remove()

            if self.has_code:
                new_widget = MessageWithCode(new_content, classes="message-content")
            else:
                new_widget = Markdown(new_content, classes="message-content")

            await self.mount(new_widget)
            self._content_widget = new_widget
        else:
            # 内容类型相同，增量更新
            if isinstance(self._content_widget, Markdown):
                self._content_widget.update(new_content)
            elif isinstance(self._content_widget, MessageWithCode):
                # 使用增量更新而不是重建
                await self._content_widget.update_content(new_content)


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
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stream_blocks = {}
        self.border_title = "💬 聊天区"
        self._scroll_timer = None
        self._is_at_bottom = True

    def compose(self) -> ComposeResult:
        """构建UI组件"""
        yield VerticalScroll(id="chat-scroll")

    def on_mount(self) -> None:
        """挂载后监听滚动事件"""
        scroll_container = self.query_one("#chat-scroll", VerticalScroll)
        scroll_container.can_focus = False

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

        msg_id = getattr(msg, 'id', None) or f"{sender_name}_{msg.timestamp if hasattr(msg, 'timestamp') else id(msg)}"

        if last:
            # 消息完成
            if msg_id in self.stream_blocks:
                message_block = self.stream_blocks[msg_id]
                await message_block.update_content(display_text, is_streaming=False)
                del self.stream_blocks[msg_id]
            else:
                message_block = MessageBlock(
                    sender_name=sender_name,
                    content_text=display_text,
                    is_streaming=False
                )
                await scroll_container.mount(message_block)

            self._schedule_scroll()
        else:
            # 流式更新中
            if msg_id in self.stream_blocks:
                message_block = self.stream_blocks[msg_id]
                await message_block.update_content(display_text, is_streaming=True)
            else:
                message_block = MessageBlock(
                    sender_name=sender_name,
                    content_text=display_text,
                    is_streaming=True
                )
                self.stream_blocks[msg_id] = message_block
                await scroll_container.mount(message_block)

            self._schedule_scroll()

    def _schedule_scroll(self):
        """延迟滚动（防抖）"""
        if self._scroll_timer is not None:
            self.remove_timer(self._scroll_timer)

        self._scroll_timer = self.set_timer(0.05, self._do_scroll)

    def _do_scroll(self):
        """执行滚动"""
        try:
            scroll_container = self.query_one("#chat-scroll", VerticalScroll)
            scroll_container.scroll_end(animate=False, force=True)
        except Exception:
            pass
        finally:
            self._scroll_timer = None

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
        self.stream_blocks.clear()
        if self._scroll_timer is not None:
            self.remove_timer(self._scroll_timer)
            self._scroll_timer = None
