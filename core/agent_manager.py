"""
Ari Agent 管理器
处理多智能体交互和UI更新
"""
import asyncio
import json
from typing import List, Dict, Any
import logging
import os

from agentscope.message import Msg
from textual.app import App
from textual.message import Message

from config import PROJECT_NAME
from core.lib.my_base_agent_lib import GlobalAgentRegistry
from core.main_agent import MainReActAgent


# 设置文件日志
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "ari_debug.log")

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)

logger = logging.getLogger("AriAgentManager")


class UpdateResultMessage(Message):
    """更新结果区域的消息"""
    def __init__(self, sender: str, content: str, msg_type: str = "text") -> None:
        self.sender = sender
        self.content = content
        self.msg_type = msg_type
        super().__init__()


class UpdateTaskMessage(Message):
    """更新任务状态的消息"""
    def __init__(self, task_id: int, status: int) -> None:
        self.task_id = task_id
        self.status = status
        super().__init__()


class AddTaskMessage(Message):
    """添加新任务的消息"""
    def __init__(self, task_id: int, task_name: str, description: str, dependencies: list) -> None:
        self.task_id = task_id
        self.task_name = task_name
        self.description = description
        self.dependencies = dependencies
        super().__init__()


class ClearTasksMessage(Message):
    """清空任务的消息"""
    pass


class AriAgentManager:
    """Ari Agent 管理器"""
    
    def __init__(self, app: App):
        self.app = app
        self.steps: List[Dict[str, Any]] = []
        self.planning_completed = False
        self.current_task = None
        
    async def process_user_message(self, user_message: str) -> None:
        """处理用户消息"""
        logger.debug(f"🔍 [AgentManager] 收到用户消息: {user_message}")
        
        # 清除之前的任务状态
        self.steps = []
        self.planning_completed = False
        
        # 初始化主 Agent
        ari = MainReActAgent()
        logger.debug("🔍 [AgentManager] 主Agent初始化完成")
        
        # 创建用户消息对象
        user_msg = Msg(
            name="user",
            content=user_message,
            role="user"
        )
        
        # 发送用户消息到结果区域
        logger.debug("🔍 [AgentManager] 发送用户消息到UI")
        self.app.post_message(UpdateResultMessage("用户", user_message))
        
        # 处理流式消息
        try:
            logger.debug("🔍 [AgentManager] 开始处理流式消息...")
            async for msg, last in GlobalAgentRegistry.stream_all_messages(
                main_task=ari(user_msg),
            ):
                logger.debug(f"🔍 [AgentManager] 收到消息: name={msg.name}, last={last}, content={msg.content}")
                await self._handle_message(msg, last)
                
        except asyncio.CancelledError:
            logger.debug("🔍 [AgentManager] 任务被中断")
            self.app.post_message(UpdateResultMessage("系统", "智能体操作已中断", "warning"))
        except Exception as e:
            logger.error(f"🔍 [AgentManager] 处理消息时出错: {str(e)}", exc_info=True)
            self.app.post_message(UpdateResultMessage("系统", f"处理消息时出错: {str(e)}", "error"))
    
    def _extract_text_content(self, msg: Msg) -> str:
        """安全提取消息中的文本内容"""
        if not msg.content:
            return ""
            
        if isinstance(msg.content, str):
            return msg.content
            
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
                    
        # 如果无法解析，返回空字符串
        logger.warning(f"🔍 [_extract_text_content] 无法解析消息内容: {msg.content}")
        return ""
    
    async def _handle_message(self, msg: Msg, last: bool) -> None:
        """处理单个消息"""
        logger.debug(f"🔍 [_handle_message] 处理消息: {msg.name}, last={last}")
        
        # 安全提取文本内容
        text_content = self._extract_text_content(msg)
        logger.debug(f"🔍 [_handle_message] 提取的文本内容: {text_content[:50]}...")
        
        # 跳过空消息
        if not text_content and not (isinstance(msg.content, list) and len(msg.content) > 0 and msg.content[0].get("type") == "tool_use"):
            logger.debug("🔍 [_handle_message] 跳过空消息")
            return
        
        # 处理不同类型的Agent消息
        if msg.name == PROJECT_NAME:  # 主Agent (Ari)
            logger.debug("🔍 [_handle_message] 识别为主Agent消息")
            # 检查是否是工具调用
            if isinstance(msg.content, list) and len(msg.content) > 0:
                first_block = msg.content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "tool_use":
                    tool_name = first_block.get("name")
                    tool_input = first_block.get("input", {})
                    logger.debug(f"🔍 [_handle_message] 工具调用: {tool_name}, input={tool_input}")
                    
                    if tool_name == "_plan_task":
                        # 规划任务请求 - 流式显示
                        task_desc = tool_input.get("task_description", "")
                        if task_desc:
                            logger.debug(f"🔍 [_handle_message] 发送规划任务消息: {task_desc}")
                            self.app.post_message(UpdateResultMessage("Ari", f"规划任务: {task_desc}", "thinking"))
                    
                    elif tool_name == "create_worker":
                        # 创建子Agent - 流式显示
                        task_desc = tool_input.get("task_description", "")
                        task_id = tool_input.get("task_id")
                        if task_desc and task_id is not None:
                            logger.debug(f"🔍 [_handle_message] 发送创建子Agent消息: task_id={task_id}, desc={task_desc}")
                            self.app.post_message(UpdateResultMessage("Ari", f"分配专家给任务 {task_id}: {task_desc}", "tool_use"))
                            
                            # 更新任务状态为1 (分配专家中)
                            if self.steps and task_id <= len(self.steps):
                                self.steps[task_id - 1]["status"] = 1
                                logger.debug(f"🔍 [_handle_message] 更新任务状态: task_id={task_id}, status=1")
                                self.app.post_message(UpdateTaskMessage(task_id, 1))
                    else:
                        # 其他工具调用
                        logger.debug(f"🔍 [_handle_message] 其他工具调用: {tool_name}")
                        if text_content:
                            self.app.post_message(UpdateResultMessage("Ari", text_content, "tool_use"))
                else:
                    # 普通文本消息
                    logger.debug("🔍 [_handle_message] 主Agent普通文本消息")
                    if text_content:
                        self.app.post_message(UpdateResultMessage("Ari", text_content, "text"))
            else:
                # 非列表内容的普通消息
                logger.debug("🔍 [_handle_message] 主Agent非列表消息")
                if text_content:
                    self.app.post_message(UpdateResultMessage("Ari", text_content, "text"))
        
        elif msg.name == "Planning":  # 规划Agent
            logger.debug("🔍 [_handle_message] 识别为规划Agent消息")
            if last and text_content:
                # 完整的规划结果，解析JSON
                try:
                    logger.debug(f"🔍 [_handle_message] 解析规划结果: {text_content[:100]}...")
                    # 提取JSON内容（去除```标记）
                    json_start = text_content.find("{")
                    json_end = text_content.rfind("}") + 1
                    if json_start != -1 and json_end != -1:
                        json_str = text_content[json_start:json_end]
                        planning_result = json.loads(json_str)
                        self.steps = planning_result.get("steps", [])
                        self.planning_completed = True
                        
                        logger.debug(f"🔍 [_handle_message] 解析成功，共 {len(self.steps)} 个步骤")
                        
                        # 清空任务显示并添加新任务
                        self.app.post_message(ClearTasksMessage())
                        for i, step in enumerate(self.steps):
                            deps = step.get("dependencies", [])
                            logger.debug(f"🔍 [_handle_message] 添加任务: {step['task_id']} - {step['task_name']}")
                            self.app.post_message(AddTaskMessage(
                                task_id=step["task_id"],
                                task_name=step["task_name"],
                                description=step["description"],
                                dependencies=deps
                            ))
                        
                        self.app.post_message(UpdateResultMessage("规划Agent", f"规划完成! 共 {len(self.steps)} 个步骤", "text"))
                        
                except json.JSONDecodeError as e:
                    logger.error(f"🔍 [_handle_message] JSON解析失败: {e}")
                    self.app.post_message(UpdateResultMessage("系统", f"规划结果解析失败: {e}", "error"))
                    self.app.post_message(UpdateResultMessage("系统", f"原始内容: {text_content}", "text"))
        
        elif msg.name.startswith("Worker_"):  # 子Agent (专家)
            logger.debug(f"🔍 [_handle_message] 识别为子Agent消息: {msg.name}")
            # 从名字中提取 task_id (格式: Worker_xxx-task_id)
            try:
                task_id_str = msg.name.split("-")[-1]
                task_id = int(task_id_str)
                logger.debug(f"🔍 [_handle_message] 提取task_id: {task_id}")
                
                if not last:
                    # 工作中 - 流式显示
                    if text_content:
                        logger.debug(f"🔍 [_handle_message] 发送工作中消息: task_id={task_id}")
                        self.app.post_message(UpdateResultMessage(msg.name, f"任务 {task_id} 执行中: {text_content}", "thinking"))
                    
                    # 更新任务状态为2 (工作中)
                    if self.steps and task_id <= len(self.steps):
                        self.steps[task_id - 1]["status"] = 2
                        logger.debug(f"🔍 [_handle_message] 更新任务状态: task_id={task_id}, status=2")
                        self.app.post_message(UpdateTaskMessage(task_id, 2))
                
                else:
                    # 工作完成
                    if text_content:
                        logger.debug(f"🔍 [_handle_message] 发送完成消息: task_id={task_id}")
                        self.app.post_message(UpdateResultMessage(msg.name, f"任务 {task_id} 完成: {text_content}", "tool_result"))
                    
                    # 更新任务状态为3 (完成)
                    if self.steps and task_id <= len(self.steps):
                        self.steps[task_id - 1]["status"] = 3
                        logger.debug(f"🔍 [_handle_message] 更新任务状态: task_id={task_id}, status=3")
                        self.app.post_message(UpdateTaskMessage(task_id, 3))
                    
                    # 检查是否所有任务都完成了
                    if self.steps and all(step["status"] == 3 for step in self.steps):
                        logger.debug("🔍 [_handle_message] 所有任务完成!")
                        self.app.post_message(UpdateResultMessage("系统", "🎉 所有任务执行完成!", "success"))
                        
            except (ValueError, IndexError) as e:
                logger.error(f"🔍 [_handle_message] 解析task_id失败: {e}")
                # 如果无法解析task_id，直接显示内容
                if text_content:
                    self.app.post_message(UpdateResultMessage(msg.name, text_content, "text"))
        
        else:
            # 其他消息类型
            logger.debug(f"🔍 [_handle_message] 其他消息类型: {msg.name}")
            if text_content:
                self.app.post_message(UpdateResultMessage(msg.name, text_content, "text"))