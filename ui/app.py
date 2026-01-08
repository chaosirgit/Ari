"""
Ari 主应用容器
将所有UI组件组合成完整的终端界面
"""
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static
from textual.binding import Binding

from .user_input import UserInput
from .thinking_display import ThinkingDisplay  
from .task_status_display import TaskStatusDisplay
from .result_output_display import ResultOutputDisplay
from .system_message_display import SystemMessageDisplay
from .theme import AriDarkTheme


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
    
    Input {
        border: solid $border;
        background: $surface;
        height: 1fr;
    }
    
    /* 使用更明确的边框定义 */
    #system-message-display {
        border-top: solid $border;
        border-right: solid $border; 
        border-bottom: solid $border;
        border-left: solid $border;
        background: $surface;
        height: 1fr;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "退出", show=True),      # Ctrl+Q 退出应用
        Binding("ctrl+c", "interrupt_agent", "中断", show=True),  # Ctrl+C 中断智能体
        Binding("ctrl+l", "clear_output", "清空输出", show=True),
    ]
    
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
    
    def on_user_input_submitted(self, event: UserInput.Submitted) -> None:
        """处理用户输入提交"""
        self.query_one(ResultOutputDisplay).add_message("用户", event.value)
        
    def on_user_input_interrupted(self, event: UserInput.Interrupted) -> None:
        """处理中断事件"""
        self.query_one(SystemMessageDisplay).add_message("操作已中断", "warning")
    
    def action_interrupt_agent(self) -> None:
        """中断当前智能体操作"""
        self.query_one(SystemMessageDisplay).add_message("智能体操作已中断", "warning")
        # TODO: 这里需要连接到实际的智能体中断逻辑
        # 可能需要维护一个当前运行的Agent任务引用
    
    def action_clear_output(self) -> None:
        """清空输出区域"""
        self.query_one(ResultOutputDisplay).clear_output()
        self.query_one(ThinkingDisplay).clear()
        self.query_one(TaskStatusDisplay).clear()
        self.query_one(SystemMessageDisplay).clear_messages()


if __name__ == "__main__":
    app = AriApp()
    app.run()