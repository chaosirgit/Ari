"""
任务规划与状态显示区域组件
- 结构化列表展示任务步骤
- 用图标（⏳, 🔄, ✅）和颜色动态指示执行状态
- 支持流式更新任务状态
"""
from textual.widgets import DataTable
from textual.reactive import reactive


class TaskStatusDisplay(DataTable):
    """任务状态显示组件"""
    
    def __init__(self) -> None:
        super().__init__(
            id="task-status-display",
            show_header=True,
            show_cursor=False
        )
        self.cursor_type = "none"
        self.add_column("状态", width=4)
        self.add_column("任务ID", width=8)
        self.add_column("任务名称", width=15)
        self.add_column("描述", width=30)
        self.add_column("依赖", width=15)
    
    def add_task(self, task_id: int, task_name: str, description: str, dependencies: list = None) -> None:
        """添加新任务"""
        dep_str = ", ".join(str(d) for d in dependencies) if dependencies else ""
        self.add_row("⏳", str(task_id), task_name, description, dep_str, key=f"task-{task_id}")
    
    def update_task_status(self, task_id: int, status: int) -> None:
        """更新任务状态
        status: 0=等待, 1=分配中, 2=工作中, 3=完成
        """
        status_icons = {
            0: "⏳",  # 等待
            1: "🔄",  # 分配中  
            2: "⚙️",  # 工作中
            3: "✅"   # 完成
        }
        icon = status_icons.get(status, "❓")
        row_key = f"task-{task_id}"
        if row_key in self.rows:
            current_row = self.get_row(row_key)
            self.update_cell(row_key, "状态", icon)