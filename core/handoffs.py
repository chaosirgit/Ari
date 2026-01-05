"""
Handoffs 工作流实现模块。

负责动态创建子 Agent 并委派任务，实现完整的任务分解和协调。
"""

import os
import json
from typing import Any, Dict, List, Optional, Tuple
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit
from agentscope.memory import InMemoryMemory
from agentscope.plan import Plan, SubTask

from .ari_agent import AriAgent


class TaskDecomposer:
    """
    任务分解器类。
    
    负责将复杂任务分解为多个子任务，并规划执行顺序。
    """
    
    def __init__(self, parent_agent: AriAgent):
        self.parent_agent = parent_agent
    
    async def decompose_task(self, task_description: str) -> Tuple[Plan, Dict[str, Dict[str, Any]]]:
        """
        将复杂任务分解为结构化的计划。
        
        Args:
            task_description: 任务描述
            
        Returns:
            Tuple[Plan, Dict]: 分解后的任务计划和元数据字典
        """
        # 使用 LLM 来分解任务
        decomposition_prompt = f"""
        你是一个任务规划专家。请将以下复杂任务分解为一系列有序的子任务。
        每个子任务应该是独立的、可执行的，并且有明确的输入输出。
        
        复杂任务: {task_description}
        
        请以 JSON 格式返回，包含以下字段：
        - "plan_name": 计划名称 (简短概括)
        - "plan_description": 计划详细描述 (主要目标)
        - "plan_expected_outcome": 计划期望的最终结果
        - "subtasks": 子任务列表，每个子任务包含:
          - "name": 子任务名称 (简短描述)
          - "description": 子任务详细描述
          - "agent_type": 推荐的Agent类型 ("general", "math", "search", "coding", "analysis")
          - "expected_output": 期望的输出格式
          - "dependencies": 依赖的子任务名称列表 (可选)
        
        确保子任务之间有合理的依赖关系，并且能够按顺序执行。
        """
        
        decomposition_msg = Msg(
            name="system",
            content=decomposition_prompt,
            role="user"
        )
        
        # 使用父Agent的模型来生成分解结果
        response = await self.parent_agent.model([decomposition_msg])
        decomposition_result = response.text
        
        try:
            # 解析JSON结果
            plan_data = json.loads(decomposition_result)
            subtasks = []
            metadata_dict = {}
            
            for i, task_data in enumerate(plan_data.get("subtasks", [])):
                # 创建SubTask（只使用支持的字段）
                subtask = SubTask(
                    name=task_data["name"],
                    description=task_data["description"],
                    expected_outcome=task_data.get("expected_output", "")
                )
                subtasks.append(subtask)
                
                # 存储元数据（包括依赖关系和agent类型）
                metadata_dict[task_data["name"]] = {
                    "agent_type": task_data.get("agent_type", "general"),
                    "dependencies": task_data.get("dependencies", []),
                    "expected_output": task_data.get("expected_output", "")
                }
            
            # 创建Plan（使用支持的所有字段）
            plan = Plan(
                name=plan_data.get("plan_name", "任务计划"),
                description=plan_data.get("plan_description", task_description),
                expected_outcome=plan_data.get("plan_expected_outcome", "完成所有子任务并提供最终答案"),
                subtasks=subtasks
            )
            
            return plan, metadata_dict
            
        except (json.JSONDecodeError, KeyError) as e:
            # 如果解析失败，创建一个简单的默认计划
            print(f"任务分解失败: {e}, 使用默认分解")
            return self._create_default_plan(task_description)
    
    def _create_default_plan(self, task_description: str) -> Tuple[Plan, Dict[str, Dict[str, Any]]]:
        """
        创建默认的任务计划（当LLM分解失败时使用）。
        
        Args:
            task_description: 任务描述
            
        Returns:
            Tuple[Plan, Dict]: 默认任务计划和元数据
        """
        # 简单的三步分解
        subtasks = [
            SubTask(
                name="分析任务需求",
                description=f"分析任务需求: {task_description}",
                expected_outcome="任务分析报告"
            ),
            SubTask(
                name="执行核心任务", 
                description=f"执行核心任务: {task_description}",
                expected_outcome="任务执行结果"
            ),
            SubTask(
                name="总结和验证结果",
                description="总结和验证结果",
                expected_outcome="最终答案"
            )
        ]
        
        metadata_dict = {
            "分析任务需求": {
                "agent_type": "analysis",
                "dependencies": [],
                "expected_output": "任务分析报告"
            },
            "执行核心任务": {
                "agent_type": "general",
                "dependencies": ["分析任务需求"],
                "expected_output": "任务执行结果"
            },
            "总结和验证结果": {
                "agent_type": "analysis",
                "dependencies": ["执行核心任务"],
                "expected_output": "最终答案"
            }
        }
        
        plan = Plan(
            name="默认任务计划",
            description=task_description,
            expected_outcome="完成所有子任务并提供最终答案",
            subtasks=subtasks
        )
        
        return plan, metadata_dict


class SubAgentFactory:
    """
    子Agent工厂类。
    
    根据任务类型动态创建合适的子Agent。
    """
    
    def __init__(self, parent_agent: AriAgent):
        self.parent_agent = parent_agent
    
    async def create_agent_for_task(
        self, 
        subtask_name: str,
        subtask_description: str,
        agent_type: str,
        task_context: Dict[str, Any]
    ) -> ReActAgent:
        """
        为特定子任务创建合适的子Agent。
        
        Args:
            subtask_name: 子任务名称
            subtask_description: 子任务描述
            agent_type: Agent类型
            task_context: 任务上下文信息
            
        Returns:
            ReActAgent: 创建的子Agent
        """
        # 根据任务类型设置不同的系统提示词
        sys_prompts = {
            "math": "你是一个数学专家，专门处理各种数学计算、公式推导和数值分析问题。确保计算准确无误。",
            "search": "你是一个信息检索专家，专门处理网络搜索、信息收集和资料整理任务。提供准确可靠的信息来源。",
            "coding": "你是一个编程专家，专门处理代码编写、调试和优化任务。提供高质量、可运行的代码。",
            "analysis": "你是一个分析专家，专门处理数据分析、逻辑推理和问题诊断任务。提供深入的洞察和建议。",
            "general": "你是一个通用任务专家，能够处理各种类型的子任务。根据具体需求灵活调整策略。"
        }
        
        sys_prompt = sys_prompts.get(agent_type, sys_prompts["general"])
        
        # 添加任务上下文到系统提示词
        if task_context:
            context_info = "\n".join([f"{k}: {v}" for k, v in task_context.items()])
            sys_prompt += f"\n\n任务上下文:\n{context_info}"
        
        # 创建子Agent
        sub_agent = ReActAgent(
            name=f"{agent_type.capitalize()}Agent_{subtask_name.replace(' ', '_')}",
            sys_prompt=sys_prompt,
            model=self.parent_agent.model,
            formatter=self.parent_agent.formatter,
            toolkit=Toolkit(),  # 预留工具接口
            memory=InMemoryMemory(),
        )
        
        return sub_agent


class TaskExecutor:
    """
    任务执行器类。
    
    负责按照计划执行子任务，并管理子Agent的生命周期。
    """
    
    def __init__(self, parent_agent: AriAgent):
        self.parent_agent = parent_agent
        self.sub_agent_factory = SubAgentFactory(parent_agent)
        self.task_decomposer = TaskDecomposer(parent_agent)
        self.execution_results: Dict[str, Any] = {}
    
    async def execute_plan(self, plan: Plan, metadata_dict: Dict[str, Dict[str, Any]], original_message: Msg) -> Msg:
        """
        执行完整的任务计划。
        
        Args:
            plan: 任务计划
            metadata_dict: 元数据字典
            original_message: 原始用户消息
            
        Returns:
            Msg: 最终响应消息
        """
        # 重置执行结果
        self.execution_results = {}
        
        # 执行所有子任务
        for subtask in plan.subtasks:
            await self._execute_subtask(subtask, plan, metadata_dict, original_message)
        
        # 生成最终响应
        final_response = await self._generate_final_response(plan, original_message)
        return final_response
    
    async def _execute_subtask(
        self, 
        subtask: SubTask, 
        plan: Plan, 
        metadata_dict: Dict[str, Dict[str, Any]],
        original_message: Msg
    ) -> Any:
        """
        执行单个子任务。
        
        Args:
            subtask: 子任务
            plan: 完整计划
            metadata_dict: 元数据字典
            original_message: 原始消息
            
        Returns:
            Any: 子任务执行结果
        """
        subtask_name = subtask.name
        metadata = metadata_dict.get(subtask_name, {})
        agent_type = metadata.get("agent_type", "general")
        dependencies = metadata.get("dependencies", [])
        
        # 等待依赖任务完成
        await self._wait_for_dependencies(dependencies)
        
        # 准备任务上下文
        task_context = self._prepare_task_context(subtask, plan, metadata)
        
        # 创建子Agent
        sub_agent = await self.sub_agent_factory.create_agent_for_task(
            subtask_name, 
            subtask.description, 
            agent_type, 
            task_context
        )
        
        # 构建任务消息
        task_message = self._build_task_message(subtask, original_message, task_context)
        
        # 记录任务开始
        start_log = Msg(
            name=self.parent_agent.name,
            content=f"开始执行子任务 {subtask_name}: {subtask.description}",
            role="system"
        )
        await self.parent_agent.memory.add(start_log)
        
        # 执行子任务
        try:
            result = await sub_agent(task_message)
            self.execution_results[subtask_name] = result.content
            
            # 记录任务完成
            completion_log = Msg(
                name=sub_agent.name,
                content=f"完成子任务 {subtask_name}: {result.content[:100]}...",
                role="system"
            )
            await self.parent_agent.memory.add(completion_log)
            
            return result.content
            
        except Exception as e:
            error_msg = f"子任务 {subtask_name} 执行失败: {str(e)}"
            error_log = Msg(
                name=self.parent_agent.name,
                content=error_msg,
                role="system"
            )
            await self.parent_agent.memory.add(error_log)
            self.execution_results[subtask_name] = f"ERROR: {error_msg}"
            raise
    
    async def _wait_for_dependencies(self, dependencies: List[str]) -> None:
        """
        等待依赖的子任务完成。
        
        Args:
            dependencies: 依赖的子任务名称列表
        """
        for dep_name in dependencies:
            if dep_name not in self.execution_results:
                # 在实际实现中，这里可能需要更复杂的等待机制
                # 目前假设任务按顺序执行，依赖已经完成
                pass
    
    def _prepare_task_context(self, subtask: SubTask, plan: Plan, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备任务上下文信息。
        
        Args:
            subtask: 当前子任务
            plan: 完整计划
            metadata: 子任务元数据
            
        Returns:
            Dict[str, Any]: 任务上下文
        """
        context = {
            "main_goal": plan.description,  # 使用description作为主要目标
            "current_subtask": subtask.description,
            "subtask_name": subtask.name,
            "dependencies": metadata.get("dependencies", []),
            "expected_output": metadata.get("expected_output", ""),
        }
        
        # 添加已完成的依赖任务结果
        for dep_name in metadata.get("dependencies", []):
            if dep_name in self.execution_results:
                context[f"dependency_{dep_name}_result"] = self.execution_results[dep_name]
        
        return context
    
    def _build_task_message(self, subtask: SubTask, original_message: Msg, context: Dict[str, Any]) -> Msg:
        """
        构建发送给子Agent的任务消息。
        
        Args:
            subtask: 子任务
            original_message: 原始用户消息
            context: 任务上下文
            
        Returns:
            Msg: 任务消息
        """
        # 构建详细的任务指令
        task_instruction = f"""
原始用户请求: {original_message.content}

当前子任务: {subtask.description}
子任务名称: {subtask.name}
期望输出: {context.get('expected_output', '请提供详细的回答')}

任务上下文:
- 主要目标: {context.get('main_goal', '')}
"""
        
        # 添加依赖任务结果
        for key, value in context.items():
            if key.startswith("dependency_") and value:
                task_instruction += f"- {key}: {value}\n"
        
        return Msg(
            name=original_message.name,
            content=task_instruction.strip(),
            role="user"
        )
    
    async def _generate_final_response(self, plan: Plan, original_message: Msg) -> Msg:
        """
        生成最终的响应消息。
        
        Args:
            plan: 任务计划
            original_message: 原始用户消息
            
        Returns:
            Msg: 最终响应
        """
        # 收集所有子任务结果
        all_results = []
        for subtask in plan.subtasks:
            result = self.execution_results.get(subtask.name, "未执行")
            all_results.append(f"子任务 {subtask.name} ({subtask.description}): {result}")
        
        # 使用主Agent生成最终总结
        summary_prompt = f"""
原始请求: {original_message.content}
主要目标: {plan.description}
期望最终结果: {plan.expected_outcome}

所有子任务执行结果:
{'\n'.join(all_results)}

请基于以上信息，提供一个完整、连贯的最终回答，直接回应用户的原始请求。
"""
        
        summary_msg = Msg(
            name=original_message.name,
            content=summary_prompt,
            role="user"
        )
        
        final_response = await self.parent_agent(summary_msg)
        return final_response


async def handle_complex_task(parent_agent: AriAgent, message: Msg) -> Msg:
    """
    处理复杂任务的主函数。
    
    Args:
        parent_agent: Ari 主 Agent
        message: 用户消息
        
    Returns:
        Msg: 响应消息
    """
    # 创建任务执行器
    executor = TaskExecutor(parent_agent)
    
    # 分解任务
    task_decomposer = TaskDecomposer(parent_agent)
    plan, metadata_dict = await task_decomposer.decompose_task(message.content)
    
    # 记录任务分解结果
    decomposition_log = Msg(
        name=parent_agent.name,
        content=f"任务分解完成，共 {len(plan.subtasks)} 个子任务",
        role="system"
    )
    await self.parent_agent.memory.add(decomposition_log)
    
    # 执行计划
    final_response = await executor.execute_plan(plan, metadata_dict, message)
    
    return final_response


async def create_sub_agent(
    parent_agent: AriAgent,
    task_description: str,
    agent_name: str,
    sys_prompt: str,
) -> ReActAgent:
    """
    创建子 Agent（向后兼容接口）。
    
    Args:
        parent_agent: 父 Agent（Ari 主 Agent）
        task_description: 任务描述
        agent_name: 子 Agent 名称
        sys_prompt: 子 Agent 的系统提示词
        
    Returns:
        ReActAgent: 创建的子 Agent 实例
    """
    sub_agent = ReActAgent(
        name=agent_name,
        sys_prompt=sys_prompt,
        model=parent_agent.model,
        formatter=parent_agent.formatter,
        toolkit=Toolkit(),
        memory=InMemoryMemory(),
    )
    
    return sub_agent


async def delegate_task_to_sub_agent(
    parent_agent: AriAgent,
    sub_agent: ReActAgent,
    task_message: Msg,
) -> Msg:
    """
    将任务委派给子 Agent（向后兼容接口）。
    
    Args:
        parent_agent: 父 Agent
        sub_agent: 子 Agent
        task_message: 任务消息
        
    Returns:
        Msg: 子 Agent 的响应
    """
    delegation_log = Msg(
        name=parent_agent.name,
        content=f"委派任务给 {sub_agent.name}: {task_message.content}",
        role="system"
    )
    await self.parent_agent.memory.add(delegation_log)
    
    response = await sub_agent(task_message)
    
    completion_log = Msg(
        name=sub_agent.name,
        content=f"完成任务: {response.content}",
        role="system"
    )
    await self.parent_agent.memory.add(completion_log)
    
    return response