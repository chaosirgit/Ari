#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务列表组件 - 使用 DataTable（整行状态高亮，支持失败状态，添加渲染保护）
"""

import asyncio
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
        padding: 1 2;
        background: $surface;
    }

    /* DataTable 自定义样式 */
    TaskListWidget DataTable {
        width: 100%;
        height: 100%;
        background: $surface;
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

        # 🔒 渲染保护
        self._rendering = False
        self._pending_updates = {}  # 存储渲染期间的待处理更新 {task_id: (status, result)}

        # 🔒 状态样式映射（应用到整行）+ 状态符号
        self.status_config = {
            0: {"style": "dim", "symbol": "○"},           # 等待中 - 空心圆
            1: {"style": "cyan", "symbol": "→"},          # 准备中 - 箭头
            2: {"style": "bold blue", "symbol": "⋯"},     # 执行中 - 省略号
            3: {"style": "green", "symbol": "✓"},         # 已完成 - 对勾
            4: {"style": "bold red", "symbol": "✗"}       # 失败 - 叉号
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
        self._column_keys["id"] = self._table.add_column("步骤", width=10)
        self._column_keys["name"] = self._table.add_column("描述", width=33)
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
        更新单个任务的状态（整行样式，带渲染保护）

        Args:
            task_id: 任务 ID
            status: 状态码 (0=等待中, 1=准备中, 2=执行中, 3=已完成, 4=失败)
            result: 结果文本
        """
        # 🔒 如果正在渲染，将更新加入待处理队列
        if self._rendering:
            self._pending_updates[task_id] = (status, result)
            logger.debug(f"⏳ 任务 {task_id} 更新已加入待处理队列")
            return

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

            # 🔒 获取状态配置（样式 + 符号）
            config = self.status_config.get(status, {"style": "", "symbol": ""})
            style = config["style"]
            symbol = config["symbol"]

            try:
                # 🔒 更新所有列（应用整行样式 + 状态符号）
                self._table.update_cell(
                    row_key=row_key,
                    column_key=self._column_keys["id"],
                    value=Text(f"{symbol} 步骤 {task_id}", style=style)
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
        """渲染任务列表（完整重绘，带渲染保护）"""
        # 🔒 设置渲染标志
        self._rendering = True

        try:
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

                # 🔒 获取状态配置（样式 + 符号）
                config = self.status_config.get(status, {"style": "", "symbol": ""})
                style = config["style"]
                symbol = config["symbol"]

                # 截断结果文本
                result_display = result[:23] + "..." if len(result) > 23 else result

                # 🔒 添加行（应用整行样式 + 状态符号）
                row_key = self._table.add_row(
                    Text(f"{symbol} 步骤 {task_id}", style=style),
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

        finally:
            # 🔒 释放渲染标志
            self._rendering = False

            # 🔄 处理待处理的更新
            if self._pending_updates:
                logger.debug(f"🔄 处理 {len(self._pending_updates)} 个待处理更新")
                pending = self._pending_updates.copy()
                self._pending_updates.clear()

                for task_id, (status, result) in pending.items():
                    await self.update_task_status(task_id, status, result)

    async def clear_tasks(self):
        """清空任务列表"""
        # 🔒 等待渲染完成
        while self._rendering:
            await asyncio.sleep(0.01)

        self.tasks = []
        self._row_keys.clear()
        self._pending_updates.clear()
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
