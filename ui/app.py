"""
Ari 主应用容器
将所有UI组件组合成完整的终端界面
"""
import asyncio

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static
from textual.binding import Binding
import logging
import os

from .user_input import UserInput
from .thinking_display import ThinkingDisplay  
from .task_status_display import TaskStatusDisplay
from .result_output_display import ResultOutputDisplay
from .system_message_display import SystemMessageDisplay
from .theme import AriDarkTheme

# 导入Agent管理器和消息类型
from core.agent_manager import (
    AriAgentManager, 
    UpdateResultMessage, 
    UpdateTaskMessage, 
    AddTaskMessage, 
    ClearTasksMessage
)


# 设置文件日志
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "ari_debug.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)

logger = logging.getLogger("AriApp")


class AriApp(App):
    """Ari 主应用程序"""
    
    CSS = """
    Screen {
        layout: vertical;
        background: $panel;
        height: 100%;
    }
    
    #banner {
        height: 3;
        background: #EF9537;
        color: #000000;
        text-align: center;
        padding: 1 0;
        text-style: bold;
        border: none;
        margin-bottom: 1;
    }
    
    #main-layout {
        layout: horizontal;
        height: 1fr;
    }
    
    #main-area {
        width: 80%;
        height: 1fr;
        layout: vertical;
    }
    
    #sidebar-area {
        width: 20%;
        height: 1fr;
        layout: vertical;
    }
    
    #output-section {
        height: 56%;
        border: none;
    }
    
    #system-section {
        height: 17%;
        border: none;
    }
    
    #input-section {
        height: 27%;
        border: none;
    }
    
    #thinking-section {
        height: 56%;
        border: none;
    }
    
    #task-section {
        height: 44%;
        border: none;
    }
    
    .section-title {
        background: $surface;
        color: $foreground;
        padding: 0 1;
        border-bottom: solid $border;
        text-style: bold;
        height: auto;
    }
    
    RichLog {
        border: solid $border;
        background: $surface;
        height: 1fr;
    }
    
    DataTable {
        border: solid $border;
        background: $surface;
        height: 1fr;
    }
    
    TextArea {
        border: solid $border;
        background: $surface;
        height: 1fr;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),      # Ctrl+Q 退出应用
        Binding("ctrl+c", "interrupt_agent", "中断", show=True),  # Ctrl+C 中断智能体
        Binding("ctrl+l", "clear_output", "清空输出", show=True),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.agent_manager = None
        self.current_task = None
    
    def compose(self) -> ComposeResult:
        """构建UI布局"""
        # 顶部 Banner
        yield Static("Ari", id="banner")
        
        # 主布局容器 (水平分割)
        with Container(id="main-layout"):
            # 主内容区域 (80% 宽度)
            with Container(id="main-area"):
                # 结果输出区 (56% 高度，包含标题)
                with Container(id="output-section"):
                    yield Static("💬 结果输出", classes="section-title")
                    yield ResultOutputDisplay()
                
                # 系统消息区 (17% 高度，包含标题)  
                with Container(id="system-section"):
                    yield Static("📢 系统消息", classes="section-title")
                    yield SystemMessageDisplay()
                
                # 用户输入区 (27% 高度)
                with Container(id="input-section"):
                    yield UserInput()
            
            # 侧边栏区域 (20% 宽度)
            with Container(id="sidebar-area"):
                # 思考过程区 (56% 高度，包含标题)
                with Container(id="thinking-section"):
                    yield Static("💭 思考过程", classes="section-title")
                    yield ThinkingDisplay()
                
                # 任务状态区 (44% 高度，包含标题)
                with Container(id="task-section"):
                    yield Static("📋 任务状态", classes="section-title")
                    yield TaskStatusDisplay()
    
    def on_mount(self) -> None:
        """应用挂载时初始化Agent管理器"""
        logger.debug("🔍 [AriApp] 应用挂载，初始化Agent管理器")
        self.agent_manager = AriAgentManager(self)
    
    def on_user_input_submitted(self, event) -> None:
        """处理用户输入提交"""
        logger.debug(f"🔍 [AriApp] 收到用户输入: {event.value}")
        if self.current_task is not None and not self.current_task.done():
            # 如果有正在运行的任务，先取消它
            logger.debug("🔍 [AriApp] 取消当前运行的任务")
            self.current_task.cancel()
        
        # 启动新的Agent任务
        logger.debug("🔍 [AriApp] 启动新的Agent任务")
        self.current_task = asyncio.create_task(
            self.agent_manager.process_user_message(event.value)
        )
    
    def on_user_input_interrupted(self, event) -> None:
        """处理中断事件（通过快捷键触发）"""
        self.action_interrupt_agent()
    
    def action_interrupt_agent(self) -> None:
        """中断当前智能体操作"""
        if self.current_task is not None and not self.current_task.done():
            self.current_task.cancel()
            self.query_one(SystemMessageDisplay).add_message("智能体操作已中断", "warning")
    
    def action_clear_output(self) -> None:
        """清空输出区域"""
        self.query_one(ResultOutputDisplay).clear_output()
        self.query_one(ThinkingDisplay).clear()
        self.query_one(TaskStatusDisplay).clear()
        self.query_one(SystemMessageDisplay).clear_messages()
    
    # 消息处理器
    def on_update_result_message(self, message: UpdateResultMessage) -> None:
        """处理结果更新消息"""
        logger.debug(f"🔍 [AriApp] 处理结果更新消息: {message.sender} - {message.content[:50]}...")
        self.query_one(ResultOutputDisplay).add_message(
            message.sender, 
            message.content, 
            message.msg_type
        )
    
    def on_update_task_message(self, message: UpdateTaskMessage) -> None:
        """处理任务状态更新消息"""
        logger.debug(f"🔍 [AriApp] 处理任务状态更新: task_id={message.task_id}, status={message.status}")
        self.query_one(TaskStatusDisplay).update_task_status(
            message.task_id, 
            message.status
        )
    
    def on_add_task_message(self, message: AddTaskMessage) -> None:
        """处理添加任务消息"""
        logger.debug(f"🔍 [AriApp] 处理添加任务消息: task_id={message.task_id}, name={message.task_name}")
        self.query_one(TaskStatusDisplay).add_task(
            message.task_id,
            message.task_name,
            message.description,
            message.dependencies
        )
    
    def on_clear_tasks_message(self, message: ClearTasksMessage) -> None:
        """处理清空任务消息"""
        logger.debug("🔍 [AriApp] 处理清空任务消息")
        self.query_one(TaskStatusDisplay).clear()


if __name__ == "__main__":
    app = AriApp()
    app.run()