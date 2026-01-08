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
        overflow-x: auto;  /* 允许横向滚动 */
    }

    .message-sender {
        width: auto;
        min-width: 100%;
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }

    .message-content {
        width: auto;
        min-width: 100%;
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
        # 记录每个发送者的当前组件 {sender_name: {"sender": Static, "content": Markdown}}
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
        # 提取文本内容和发送者信息
        sender_name, display_text = self._parse_message(msg)

        if not sender_name or not display_text:
            return

        scroll_container = self.query_one("#chat-scroll", VerticalScroll)

        if last:
            # 消息完成 - 只处理状态，不额外显示内容
            if sender_name in self.stream_widgets:
                widgets = self.stream_widgets[sender_name]
                sender_widget = widgets["sender"]
                content_widget = widgets["content"]

                # 移除流式标记（⚡）
                sender_widget.update(sender_name)
                sender_widget.remove_class("streaming")
                sender_widget.add_class("completed")

                # 更新内容为最终版本（Markdown 渲染）
                try:
                    await content_widget.update(display_text)
                except Exception as e:
                    # 如果 Markdown 解析失败，降级为纯文本
                    await content_widget.update(f"```\n{display_text}\n```")

                # 清理状态
                del self.stream_widgets[sender_name]

            # 滚动到底部
            scroll_container.scroll_end(animate=False)

        else:
            # 流式消息 - 在同一行增量更新
            if sender_name in self.stream_widgets:
                # 同一发送者，更新现有组件的内容
                widgets = self.stream_widgets[sender_name]
                content_widget = widgets["content"]

                # 更新 Markdown 内容
                try:
                    await content_widget.update(display_text)
                except Exception as e:
                    # 如果 Markdown 解析失败，降级为纯文本
                    await content_widget.update(f"```\n{display_text}\n```")
            else:
                # 新发送者，创建新的流式组件
                # 创建发送者标签（带流式标记 ⚡）
                sender_widget = Static(
                    f"{sender_name} ⚡",
                    classes="message-sender streaming"
                )

                # 创建内容组件（Markdown）
                content_widget = Markdown(display_text, classes="message-content")

                # 保存引用
                self.stream_widgets[sender_name] = {
                    "sender": sender_widget,
                    "content": content_widget
                }

                # 挂载到容器
                await scroll_container.mount(sender_widget)
                await scroll_container.mount(content_widget)

            # 滚动到底部
            scroll_container.scroll_end(animate=False)

    def _parse_message(self, msg: Msg) -> tuple[str, str]:
        """
        解析消息内容

        Returns:
            (sender_name, display_text) 元组
        """
        # 提取文本内容
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

        # 处理主智能体的消息
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

        # 处理用户消息
        elif msg.name == "user" and msg.role == "user":
            if text_content:
                sender_name = "👤 用户"
                display_text = text_content

        # 处理规划Agent消息
        elif msg.name == "Planning":
            sender_name = "🧠 规划Agent"
            display_text = text_content if text_content else "正在规划..."

        # 处理子Agent消息
        elif msg.name.startswith("Worker_"):
            try:
                # 从名字提取任务信息
                parts = msg.name.split("_")
                if len(parts) >= 2:
                    agent_type = parts[1].replace("Agent", "")
                    # 提取最后的数字作为任务ID
                    task_id = msg.name.split("-")[-1] if "-" in msg.name else "?"
                    sender_name = f"👷 {agent_type} (任务 {task_id})"
                else:
                    sender_name = f"👷 {msg.name}"

                display_text = text_content if text_content else "工作中..."
            except Exception:
                sender_name = f"👷 {msg.name}"
                display_text = text_content if text_content else "工作中..."

        # 处理系统消息
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
