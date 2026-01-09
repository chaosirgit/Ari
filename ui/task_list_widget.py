#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务列表组件 - 使用 DataTable（整行状态高亮，支持失败状态）
"""

from textual.containers import VerticalScroll
from textual.widgets import DataTable
from textual.app import ComposeResult
from rich.text import Text
from config import logger


class TaskListWidget(VerticalScroll):
    """任务列表组件 - 基于 DataTable，支持整行状态高亮"""

    DEFAULT_CSS = """
    TaskListWidget {
        width: 100%;
        height: 100%;
    }

    /* DataTable 自定义样式 */
    TaskListWidget DataTable {
        height: 100%;
    }

    /* 执行中的行高亮（蓝色背景） */
    TaskListWidget DataTable > .datatable--cursor {
        background: $accent 30%;
        border-left: thick $primary;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "📋 任务列表"
        self.tasks = []
        self._table = None
        self._row_keys = {}  # 存储 task_id 到 RowKey 的映射
        self._column_keys = {}  # 存储列名到 ColumnKey 的映射

        # 状态样式映射（应用到整行）
        self.status_styles = {
            0: "dim",  # 等待中 - 暗淡
            1: "cyan",  # 准备中 - 青色
            2: "bold blue",  # 执行中 - 粗体蓝色（配合光标高亮）
            3: "green",  # 已完成 - 绿色
            4: "bold red"  # 失败 - 粗体红色
        }

    def compose(self) -> ComposeResult:
        """构建组件"""
        self._table = DataTable(
            id="task_table",
            zebra_stripes=True,
            cursor_type="row",
            show_cursor=False,
        )
        yield self._table

    def on_mount(self):
        """挂载时初始化表格列"""
        # 只保留三列：步骤、描述、结果
        self._column_keys["id"] = self._table.add_column("步骤", width=8)
        self._column_keys["name"] = self._table.add_column("描述", width=35)
        self._column_keys["result"] = self._table.add_column("结果", width=25)

    async def update_tasks(self, steps: list):
        """
        更新任务列表

        Args:
            steps: 任务列表，每个任务包含 task_id, task_name, status, result
        """
        self.tasks = steps
        await self._render_tasks()

    async def update_task_status(self, task_id: int, status: int, result: str = ""):
        """
        更新单个任务的状态（整行样式）

        Args:
            task_id: 任务 ID
            status: 状态码 (0=等待中, 1=准备中, 2=执行中, 3=已完成, 4=失败)
            result: 结果文本
        """
        if task_id <= len(self.tasks):
            # 更新内部数据
            self.tasks[task_id - 1]["status"] = status
            if result:
                self.tasks[task_id - 1]["result"] = result

            # 获取该任务的 RowKey
            row_key = self._row_keys.get(task_id)
            if row_key is None:
                logger.warning(f"⚠️ 未找到任务 {task_id} 的 RowKey，尝试重新渲染")
                await self._render_tasks()
                return

            # 获取任务数据
            task = self.tasks[task_id - 1]
            task_name = task.get("task_name", "")
            result_display = result[:23] + "..." if len(result) > 23 else result

            # 获取状态样式
            style = self.status_styles.get(status, "")

            try:
                # 更新所有列（应用整行样式）
                self._table.update_cell(
                    row_key=row_key,
                    column_key=self._column_keys["id"],
                    value=Text(f"步骤 {task_id}", style=style)
                )

                self._table.update_cell(
                    row_key=row_key,
                    column_key=self._column_keys["name"],
                    value=Text(task_name, style=style)
                )

                self._table.update_cell(
                    row_key=row_key,
                    column_key=self._column_keys["result"],
                    value=Text(result_display or "-", style=style)
                )

                # 如果是执行中状态，显示光标高亮该行
                if status == 2:
                    row_index = self._table.get_row_index(row_key)
                    self._table.move_cursor(row=row_index)
                    self._table.show_cursor = True
                elif status in [3, 4]:
                    # 完成或失败后取消光标高亮
                    self._table.show_cursor = False

            except Exception as e:
                logger.error(f"❌ 更新单元格失败: {e}")
                await self._render_tasks()

    async def _render_tasks(self):
        """渲染任务列表（完整重绘）"""
        self._table.clear()
        self._row_keys.clear()

        if not self.tasks:
            self._table.add_row("", "暂无任务", "")
            return

        for task in self.tasks:
            task_id = task.get("task_id", "")
            task_name = task.get("task_name", "")
            status = task.get("status", 0)
            result = task.get("result", "")

            # 获取状态样式
            style = self.status_styles.get(status, "")

            # 截断结果文本
            result_display = result[:23] + "..." if len(result) > 23 else result

            # 添加行（应用整行样式）
            row_key = self._table.add_row(
                Text(f"步骤 {task_id}", style=style),
                Text(task_name, style=style),
                Text(result_display or "-", style=style)
            )

            # 保存 task_id 到 RowKey 的映射
            self._row_keys[task_id] = row_key

            # 如果是执行中状态，移动光标到该行
            if status == 2:
                row_index = self._table.get_row_index(row_key)
                self._table.move_cursor(row=row_index)
                self._table.show_cursor = True

    async def clear_tasks(self):
        """清空任务列表"""
        self.tasks = []
        self._row_keys.clear()
        self._table.clear()
        self._table.show_cursor = False
        self._table.add_row("", "暂无任务", "")
        logger.info("🧹 清空任务列表")

    def get_task_by_id(self, task_id: int) -> dict | None:
        """
        根据 ID 获取任务

        Args:
            task_id: 任务 ID

        Returns:
            任务字典或 None
        """
        if task_id <= len(self.tasks):
            return self.tasks[task_id - 1]
        return None
