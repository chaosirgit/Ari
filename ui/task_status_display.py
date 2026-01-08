"""
任务规划与状态显示区域组件
- 结构化列表展示任务步骤
- 用图标（⏳, 🔄, ✅）和颜色动态指示执行状态
- 支持流式更新任务状态
"""
from textual.widgets import DataTable
from textual.message import Message


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
        row_key = f"task-{task_id}"
        # 检查行是否已存在，避免重复添加
        if row_key not in self.rows:
            self.add_row("⏳", str(task_id), task_name, description, dep_str, key=row_key)
    
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
        
        # 只有在行存在时才更新
        if row_key in self.rows:
            try:
                self.update_cell(row_key, "状态", icon)
            except Exception as e:
                # 记录错误但不崩溃
                print(f"更新任务状态失败: {e}")
        else:
            # 如果行不存在，可能是规划还没完成就收到了更新
            # 在这种情况下，我们可以选择忽略或者稍后重试
            pass