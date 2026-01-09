#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户输入组件 - 固定高度，占满父容器
"""

from textual.widgets import TextArea
from textual.containers import Container
from textual.binding import Binding
from textual.message import Message
from textual.app import ComposeResult


class UserInputSubmitted(Message):
    """用户输入提交消息"""

    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class UserInputWidget(Container):
    """用户输入组件 - 固定高度版"""

    DEFAULT_CSS = """
    UserInputWidget {
        width: 100%;
        height: 100%;
        padding: 1 2;
        background: $surface;
    }

    UserInputWidget TextArea {
        width: 100%;
        height: 100%;
        border: none !important;
        outline: none !important;
        background: $surface;
    }

    /* 去掉所有状态的边框 */
    UserInputWidget TextArea:focus {
        border: none !important;
        outline: none !important;
    }

    UserInputWidget TextArea:hover {
        border: none !important;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "submit", "Ctrl+Enter 提交", show=True),
        Binding("escape", "clear", "Esc 清空", show=True),
        Binding("up", "history_up", "上一条历史", show=False),
        Binding("down", "history_down", "下一条历史", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history = []
        self._history_index = -1
        self._current_input = ""
        self.border_title = "⌨️  用户输入"

    def compose(self) -> ComposeResult:
        """构建组件"""
        yield TextArea(
            id="input_area",
            language="markdown",
            show_line_numbers=False,
            soft_wrap=True
        )

    def on_mount(self) -> None:
        """挂载时自动聚焦"""
        input_area = self.query_one("#input_area", TextArea)
        input_area.focus()

    def action_submit(self):
        """提交输入"""
        input_area = self.query_one("#input_area", TextArea)
        content = input_area.text

        if content.strip():
            self.add_to_history(content)
            self.post_message(UserInputSubmitted(content))
            self.clear()

    def action_clear(self):
        """清空输入框"""
        self.clear()

    def action_history_up(self):
        """切换到上一条历史记录"""
        input_area = self.query_one("#input_area", TextArea)
        cursor_row, cursor_col = input_area.cursor_location
        text_lines = input_area.text.split('\n')
        total_lines = len(text_lines)

        if cursor_row == 0 and total_lines == 1:
            if self._history:
                if self._history_index == -1:
                    self._current_input = input_area.text
                    self._history_index = len(self._history) - 1
                elif self._history_index > 0:
                    self._history_index -= 1
                else:
                    return

                input_area.text = self._history[self._history_index]
                self._move_cursor_to_end(input_area)

    def action_history_down(self):
        """切换到下一条历史记录"""
        input_area = self.query_one("#input_area", TextArea)
        cursor_row, cursor_col = input_area.cursor_location
        text_lines = input_area.text.split('\n')
        total_lines = len(text_lines)

        if cursor_row == total_lines - 1:
            if self._history_index == -1:
                return
            elif self._history_index < len(self._history) - 1:
                self._history_index += 1
                input_area.text = self._history[self._history_index]
            else:
                self._history_index = -1
                input_area.text = self._current_input

            self._move_cursor_to_end(input_area)

    def _move_cursor_to_end(self, input_area: TextArea):
        """将光标移动到文本末尾"""
        text_lines = input_area.text.split('\n')
        last_line = len(text_lines) - 1
        last_col = len(text_lines[-1]) if text_lines else 0
        input_area.move_cursor((last_line, last_col))

    def add_to_history(self, content: str):
        """添加到历史记录"""
        if content.strip():
            if not self._history or self._history[-1] != content:
                self._history.append(content)
        self._history_index = -1
        self._current_input = ""

    def clear(self):
        """清空输入框"""
        input_area = self.query_one("#input_area", TextArea)
        input_area.text = ""
        self._current_input = ""
        self._history_index = -1
        input_area.focus()
