"""
全局消息流管理器。

该模块负责集中存储和管理来自不同智能体的流式和非流式消息。
"""
from typing import Dict, List, Any

# 全局消息流存储
# 结构:
# {
#     "main_agent": {
#         "thinking": [...],
#         "reply": [...]
#     },
#     "PlanningAgent": {
#         "thinking": [...],
#         "reply": [...]
#     },
#     "worker_1": {
#         "thinking": [...],
#         "reply": [...]
#     },
#     ...
# }
GLOBAL_MESSAGE_STREAMS: Dict[str, Dict[str, List[Any]]] = {}


def get_or_create_agent_stream(agent_name: str) -> Dict[str, List[Any]]:
    """
    获取或创建指定智能体的消息流。
    
    Args:
        agent_name: 智能体的名称
        
    Returns:
        该智能体的消息流字典，包含 "thinking" 和 "reply" 列表。
    """
    if agent_name not in GLOBAL_MESSAGE_STREAMS:
        GLOBAL_MESSAGE_STREAMS[agent_name] = {
            "thinking": [],
            "reply": []
        }
    return GLOBAL_MESSAGE_STREAMS[agent_name]


def get_all_streams() -> Dict[str, Dict[str, List[Any]]]:
    """获取所有智能体的消息流。"""
    return GLOBAL_MESSAGE_STREAMS


def clear_all_streams() -> None:
    """清空所有消息流。"""
    GLOBAL_MESSAGE_STREAMS.clear()