"""
系统消息区域组件
- 非阻塞地显示通知、警告或错误
- 支持不同类型的消息（info, warning, error, success）
- 自动消失功能
"""
from textual.widgets import RichLog
from textual.message import Message


class SystemMessageDisplay(RichLog):
    """系统消息显示组件"""
    
    def __init__(self) -> None:
        super().__init__(
            id="system-message-display",
            auto_scroll=True,
            wrap=True,
            highlight=False,
            markup=True,
        )
        self._message_timers: dict = {}
    
    def add_message(self, message: str, msg_type: str = "info", duration: float = 5.0) -> None:
        """添加系统消息
        
        Args:
            message: 消息内容
            msg_type: 消息类型 ("info", "warning", "error", "success")
            duration: 显示持续时间（秒），None表示永久显示
        """
        color_map = {
            "info": "cyan",
            "warning": "yellow",
            "error": "red", 
            "success": "green"
        }
        
        icon_map = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "❌",
            "success": "✅"
        }
        
        color = color_map.get(msg_type, "white")
        icon = icon_map.get(msg_type, "💬")
        
        formatted_message = f"[{color} bold]{icon} {message}[/{color} bold]"
        self.write(formatted_message)
        
        # 如果有持续时间，设置自动清除
        if duration is not None:
            message_id = f"msg_{len(self._message_timers)}"
            timer = self.set_timer(duration, lambda: self._remove_message(message_id))
            self._message_timers[message_id] = timer
    
    def _remove_message(self, message_id: str) -> None:
        """移除消息（目前Textual不直接支持删除特定行，所以暂时只清空）"""
        if message_id in self._message_timers:
            del self._message_timers[message_id]
    
    def clear_messages(self) -> None:
        """清空所有系统消息"""
        # 取消所有定时器
        for timer in self._message_timers.values():
            if timer is not None and not timer.finished:
                timer.stop()
        self._message_timers.clear()
        self.clear()