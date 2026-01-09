from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Header, Static, Markdown
from textual.containers import VerticalScroll
from agentscope.message import Msg


class ChatWidget(Widget):
    """聊天区组件，用于显示聊天历史和流式消息"""

    DEFAULT_CSS = """
    ChatWidget {
        width: 100%;
        height: 100%;
    }

    ChatWidget > Header {
        dock: top;
    }

    #chat-scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }

    .message-sender {
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }

    .message-content {
        margin-bottom: 1;
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

    def compose(self) -> ComposeResult:
        """构建UI组件"""
        yield Header(show_clock=True)
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
            if sender_name in self.stream_widgets:
                widgets = self.stream_widgets[sender_name]
                sender_widget = widgets["sender"]
                content_widget = widgets["content"]

                sender_widget.update(sender_name)
                sender_widget.remove_class("streaming")
                sender_widget.add_class("completed")

                try:
                    await content_widget.update(display_text)
                except Exception:
                    await content_widget.update(f"```\n{display_text}\n```")

                del self.stream_widgets[sender_name]
            else:
                if sender_name and display_text:
                    sender_widget = Static(
                        sender_name,
                        classes="message-sender completed"
                    )
                    content_widget = Markdown(display_text, classes="message-content")

                    await scroll_container.mount(sender_widget)
                    await scroll_container.mount(content_widget)

            scroll_container.scroll_end(animate=False)
        else:
            if sender_name in self.stream_widgets:
                widgets = self.stream_widgets[sender_name]
                content_widget = widgets["content"]

                try:
                    await content_widget.update(display_text)
                except Exception:
                    await content_widget.update(f"```\n{display_text}\n```")
            else:
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
