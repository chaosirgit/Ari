from textual.containers import VerticalScroll
from textual.widgets import Static
import hashlib

# 尝试导入 Msg 类，如果不存在则设为 None
try:
    from agentscope.message import Msg
except ImportError:
    Msg = None


class SystemMessageWidget(VerticalScroll):
    """系统消息组件 - 显示系统级通知、错误和状态信息"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages = []  # 存储消息组件引用，用于清理
        self._seen_message_ids = set()  # 存储已处理的消息ID，用于去重
        
    async def add_message(self, message, level: str = "info"):
        """
        添加系统消息（支持字符串和 Msg 对象）
        
        Args:
            message: 消息内容（字符串）或 Msg 对象
            level: 消息级别 ("info", "warning", "error", "success")
        """
        # 处理 Msg 对象
        if Msg is not None and isinstance(message, Msg):
            msg_id = message.id
            # 检查是否已处理过此消息ID
            if msg_id in self._seen_message_ids:
                return  # 已存在，直接返回不重复显示
            
            self._seen_message_ids.add(msg_id)
            # 从 Msg 对象提取文本内容
            if isinstance(message.content, str):
                message_text = message.content
            else:
                # 处理 content blocks
                text_blocks = []
                for block in message.content:
                    if hasattr(block, 'get') and block.get('type') == 'text':
                        text_blocks.append(block.get('text', ''))
                    elif isinstance(block, dict) and block.get('type') == 'text':
                        text_blocks.append(block.get('text', ''))
                message_text = '\n'.join(text_blocks) if text_blocks else str(message.content)
        else:
            # 处理字符串消息（保持向后兼容）
            message_text = str(message)
            # 为字符串消息使用内容哈希作为ID，相同内容不会重复显示
            msg_id = hashlib.md5(message_text.encode('utf-8')).hexdigest()
            if msg_id in self._seen_message_ids:
                return  # 已存在，直接返回不重复显示
            self._seen_message_ids.add(msg_id)
        
        # 根据消息级别添加对应的emoji前缀
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "❌",
            "success": "✅"
        }
        emoji = emoji_map.get(level, "ℹ️")
        formatted_message = f"{emoji} {message_text}"
        
        # 创建消息组件并添加到容器
        message_widget = Static(formatted_message)
        await self.mount(message_widget)
        self._messages.append(message_widget)
        
        # 限制消息数量，防止内存泄漏（保留最近50条）
        if len(self._messages) > 50:
            old_message = self._messages.pop(0)
            await old_message.remove()
            
        # 自动滚动到底部
        self.scroll_end(animate=False)
        
    async def clear_messages(self):
        """清空所有系统消息"""
        # 移除所有消息组件
        for message_widget in self._messages:
            await message_widget.remove()
        self._messages.clear()
        # 清空已处理消息ID集合
        self._seen_message_ids.clear()