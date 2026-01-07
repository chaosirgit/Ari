import asyncio
from typing import Any, AsyncGenerator, Optional

# 全局流存储变量
_GLOBAL_THINKING_STREAM: Optional[AsyncGenerator] = None
_GLOBAL_TEXT_STREAM: Optional[AsyncGenerator] = None
_GLOBAL_PLAN_STREAM: Optional[AsyncGenerator] = None
_GLOBAL_TOOL_STREAM: Optional[AsyncGenerator] = None

# 全局锁，确保线程安全
_STREAM_LOCK = asyncio.Lock()

async def put_thinking_stream(stream: AsyncGenerator) -> None:
    """将思考流存入全局变量"""
    global _GLOBAL_THINKING_STREAM
    async with _STREAM_LOCK:
        _GLOBAL_THINKING_STREAM = stream

async def put_text_stream(stream: AsyncGenerator) -> None:
    """将文本流存入全局变量"""
    global _GLOBAL_TEXT_STREAM
    async with _STREAM_LOCK:
        _GLOBAL_TEXT_STREAM = stream

async def put_plan_stream(stream: AsyncGenerator) -> None:
    """将规划流存入全局变量"""
    global _GLOBAL_PLAN_STREAM
    async with _STREAM_LOCK:
        _GLOBAL_PLAN_STREAM = stream

async def put_tool_stream(stream: AsyncGenerator) -> None:
    """将工具流存入全局变量"""
    global _GLOBAL_TOOL_STREAM
    async with _STREAM_LOCK:
        _GLOBAL_TOOL_STREAM = stream

def get_thinking_stream() -> Optional[AsyncGenerator]:
    """获取思考流"""
    return _GLOBAL_THINKING_STREAM

def get_text_stream() -> Optional[AsyncGenerator]:
    """获取文本流"""
    return _GLOBAL_TEXT_STREAM

def get_plan_stream() -> Optional[AsyncGenerator]:
    """获取规划流"""
    return _GLOBAL_PLAN_STREAM

def get_tool_stream() -> Optional[AsyncGenerator]:
    """获取工具流"""
    return _GLOBAL_TOOL_STREAM

async def iterate_thinking_stream() -> AsyncGenerator[Any, None]:
    """直接异步迭代思考流"""
    stream = get_thinking_stream()
    if stream is not None:
        async for chunk in stream:
            yield chunk

async def iterate_text_stream() -> AsyncGenerator[Any, None]:
    """直接异步迭代文本流"""
    stream = get_text_stream()
    if stream is not None:
        async for chunk in stream:
            yield chunk

async def iterate_plan_stream() -> AsyncGenerator[Any, None]:
    """直接异步迭代规划流"""
    stream = get_plan_stream()
    if stream is not None:
        async for chunk in stream:
            yield chunk

async def iterate_tool_stream() -> AsyncGenerator[Any, None]:
    """直接异步迭代工具流"""
    stream = get_tool_stream()
    if stream is not None:
        async for chunk in stream:
            yield chunk

async def clear_all_streams() -> None:
    """清空所有全局流"""
    global _GLOBAL_THINKING_STREAM, _GLOBAL_TEXT_STREAM, _GLOBAL_PLAN_STREAM, _GLOBAL_TOOL_STREAM
    async with _STREAM_LOCK:
        _GLOBAL_THINKING_STREAM = None
        _GLOBAL_TEXT_STREAM = None
        _GLOBAL_PLAN_STREAM = None
        _GLOBAL_TOOL_STREAM = None