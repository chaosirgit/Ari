#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务列表组件
"""

from textual.containers import VerticalScroll  # ✅ 确保导入正确
from textual.widgets import Static
from rich.table import Table
from config import logger


class TaskListWidget(VerticalScroll):  # ✅ 继承 VerticalScroll
    """任务列表组件"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "📋 任务列表"
        self.tasks = []
        self._task_display = None

    def compose(self):
        self._task_display = Static("暂无任务", id="task_display")
        yield self._task_display

    async def update_tasks(self, steps: list):
        """更新任务列表"""
        self.tasks = steps
        await self._render_tasks()

    async def update_task_status(self, task_id: int, status: int, result: str = ""):
        """更新任务状态"""
        if task_id <= len(self.tasks):
            self.tasks[task_id - 1]["status"] = status
            if result:
                self.tasks[task_id - 1]["result"] = result
            await self._render_tasks()

    async def _render_tasks(self):
        """渲染任务列表"""
        if not self.tasks:
            self._task_display.update("暂无任务")
            return

        table = Table(title="任务列表", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("任务", style="white", width=20)
        table.add_column("状态", style="yellow", width=10)
        table.add_column("结果", style="green", width=10)

        status_map = {
            0: "⏳ 等待中",
            1: "🔄 准备中",
            2: "⚙️ 执行中",
            3: "✅ 已完成"
        }

        for task in self.tasks:
            task_id = str(task.get("task_id", ""))
            task_name = task.get("task_name", "")
            status = task.get("status", 0)
            result = task.get("result", "")

            table.add_row(
                task_id,
                task_name,
                status_map.get(status, "❓ 未知"),
                result[:10] if result else "-"
            )

        self._task_display.update(table)

    async def clear_tasks(self):
        """清空任务列表"""
        self.tasks = []
        self._task_display.update("暂无任务")
        logger.info("🧹 清空任务列表")
