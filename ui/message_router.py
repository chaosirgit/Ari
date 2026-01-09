#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息路由器 - 负责将消息分发到对应的 UI 组件
"""

import json
from config import PROJECT_NAME, logger


class MessageRouter:
    """消息路由器 - 根据消息类型分发到不同组件"""

    def __init__(self, chat_widget, task_widget, thinking_widget=None, system_message_widget=None):
        self.chat_widget = chat_widget
        self.task_widget = task_widget
        self.thinking_widget = thinking_widget
        self.system_message_widget = system_message_widget        # 业务状态
        self.steps = []
        self.planning_completed = False

        logger.info("✅ MessageRouter 初始化完成")
    async def _send_system_message(self, message: str, level: str = "info"):
        """发送系统消息到系统消息组件"""
        if self.system_message_widget:
            await self.system_message_widget.add_message(message, level)

    async def route_message(self, msg, last: bool):
        """
        路由消息到对应组件

        Args:
            msg: AgentScope 消息对象
            last: 是否是最后一条消息
        """
        msg_name = msg.name
        logger.debug(f"📨 路由消息: name={msg_name}, last={last}")

        # 提取思考过程（last=False 的工具调用 或 thinking 类型）
        if not last:
            await self._extract_thinking(msg)

        # 1. 主 Agent 消息
        if msg_name == PROJECT_NAME:
            await self._handle_main_agent(msg, last)

        # 2. Planning Agent 消息
        elif msg_name == "Planning":
            # ✅ 只处理规划逻辑，不显示在聊天区
            await self._handle_planning(msg, last)

        # 3. Worker Agent 消息
        elif msg_name.startswith("Worker_"):
            await self._handle_worker(msg, last)

        # 4. 其他消息
        else:
            await self.chat_widget.add_message(msg, last)

    async def _extract_thinking(self, msg):
        """
        提取思考过程
        1. 工具调用的构建过程 (type=tool_use)
        2. 推理模型的思考内容 (type=thinking)
        """
        if not self.thinking_widget:
            return

        if not isinstance(msg.content, list):
            return

        for block in msg.content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")

            # 1. 处理工具调用
            if block_type == "tool_use":
                tool_name = block.get("name")
                tool_input = block.get("input", {})

                # 发送系统消息 - 工具调用开始
                if tool_name:
                    await self._send_system_message(f"🔧 执行工具: {tool_name}", "info")

                # 只显示有意义的工具调用（input 不为空）
                if tool_input and self.thinking_widget:
                    await self.thinking_widget.add_thinking(
                        agent_name=msg.name,
                        tool_name=tool_name,
                        tool_input=tool_input
                    )            # 2. 处理推理模型的 thinking 块
            elif block_type == "thinking":
                thinking_content = block.get("text") or block.get("content", "")

                if thinking_content:
                    # 将 thinking 内容作为特殊的"工具调用"显示
                    await self.thinking_widget.add_thinking(
                        agent_name=msg.name,
                        tool_name="💭 内部推理",
                        tool_input={"思考内容": thinking_content}
                    )

    async def _handle_main_agent(self, msg, last: bool):
        """处理主 Agent 消息"""
        await self.chat_widget.add_message(msg, last)

        # 检查思考过程中的长期记忆操作
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict):
                    # 检测长期记忆相关的思考内容
                    if block.get("type") == "thinking":
                        thinking_content = block.get("text") or block.get("content", "")
                        if "long_term_memory" in thinking_content.lower() or "长期记忆" in thinking_content:
                            if "retrieve" in thinking_content.lower() or "检索" in thinking_content:
                                await self._send_system_message("🧠 从长期记忆检索相关信息", "info")
                            elif "save" in thinking_content.lower() or "保存" in thinking_content:
                                await self._send_system_message("💾 保存重要信息到长期记忆", "info")

        # 检查工具调用
        if isinstance(msg.content, list) and len(msg.content) > 0:
            first_block = msg.content[0]
            if isinstance(first_block, dict) and first_block.get("type") == "tool_use":
                tool_name = first_block.get("name")
                tool_input = first_block.get("input", {})

                if tool_name == "create_worker":
                    task_id = tool_input.get("task_id")
                    if task_id and self.steps and task_id <= len(self.steps):
                        self.steps[task_id - 1]["status"] = 1
                        await self.task_widget.update_task_status(task_id, status=1)

    async def _handle_planning(self, msg, last: bool):
        """
        处理 Planning Agent 消息
        ✅ 只处理规划逻辑，不显示在聊天区
        """
        # ❌ 移除这行：不再添加到聊天区
        # await self.chat_widget.add_message(msg, last)

        if not last or self.planning_completed:
            return

        # 提取文本内容
        text_content = self._extract_text(msg.content)
        if not text_content:
            return

        # 解析规划结果
        try:
            json_start = text_content.find("{")
            json_end = text_content.rfind("}") + 1

            if json_start != -1 and json_end != -1:
                json_str = text_content[json_start:json_end]
                planning_result = json.loads(json_str)
                self.steps = planning_result.get("steps", [])

                # 初始化任务状态
                for step in self.steps:
                    step["status"] = 0
                    step["result"] = ""

                self.planning_completed = True
                await self.task_widget.update_tasks(self.steps)
                await self._send_system_message(f"✅ 任务规划完成，共 {len(self.steps)} 个步骤", "success")
                logger.info(f"✅ 规划完成，共 {len(self.steps)} 个任务")

        except json.JSONDecodeError as e:
            await self._send_system_message(f"❌ JSON 解析失败: {e}", "error")
            logger.error(f"❌ JSON 解析失败: {e}")
    async def _handle_worker(self, msg, last: bool):
        """处理 Worker Agent 消息"""
        await self.chat_widget.add_message(msg, last)

        try:
            # 提取Worker名称和任务ID
            worker_name_parts = msg.name.split("-")
            if len(worker_name_parts) >= 2:
                task_id = int(worker_name_parts[-1])
                worker_base_name = "-".join(worker_name_parts[:-1]).replace("Worker_", "")
                
                # 发送系统消息 - Worker创建（只在第一次接收到消息时）
                if not last and self.steps and task_id <= len(self.steps) and self.steps[task_id - 1]["status"] == 0:
                    await self._send_system_message(f"👷 创建专家助手: {worker_base_name}", "info")
            else:
                task_id = None

            text_content = self._extract_text(msg.content)

            if not text_content or not self.steps or not task_id or task_id > len(self.steps):
                return

            if not last:
                # 工作中
                self.steps[task_id - 1]["status"] = 2
                self.steps[task_id - 1]["result"] = text_content
                await self.task_widget.update_task_status(task_id, status=2, result=text_content)
            else:
                # 完成
                self.steps[task_id - 1]["status"] = 3
                self.steps[task_id - 1]["result"] = text_content
                await self.task_widget.update_task_status(task_id, status=3, result=text_content)

                # 发送系统消息 - Worker完成
                worker_base_name = "-".join(worker_name_parts[:-1]).replace("Worker_", "")
                await self._send_system_message(f"✅ 专家助手 {worker_base_name} 完成任务", "success")

                # 检查是否全部完成
                if all(step["status"] == 3 for step in self.steps):
                    await self._send_system_message("🎉 所有任务完成！", "success")
                    logger.info("🎉 所有任务完成！")

        except (ValueError, IndexError) as e:
            await self._send_system_message(f"❌ 解析 Worker 消息失败: {e}", "error")
            logger.error(f"❌ 解析 Worker 消息失败: {e}")
    @staticmethod
    def _extract_text(content) -> str:
        """提取消息文本内容"""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")

        return ""
