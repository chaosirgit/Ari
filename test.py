import asyncio
import logging
from agentscope.message import Msg
from core.main_agent import MainReActAgent

# 配置日志，抑制 AgentScope 的底层消息打印
logging.getLogger("agentscope").setLevel(logging.WARNING)

# 导入全局消息流管理器
from ui.message_stream_manager import get_all_streams, clear_all_streams


async def stream_printer():
    """后台任务：持续打印新的、干净的回复消息。"""
    printed_counts = {}  # 记录每个智能体已打印的 reply 消息数量

    while True:
        all_streams = get_all_streams()
        has_new_message = False

        for agent_name, streams in all_streams.items():
            if agent_name not in printed_counts:
                printed_counts[agent_name] = 0

            # 只打印新的 reply 消息，并且只打印 content
            reply_msgs = streams["reply"]
            for i in range(printed_counts[agent_name], len(reply_msgs)):
                msg = reply_msgs[i]
                print(f"\n--- {agent_name} ---")
                print(msg['content'])
                printed_counts[agent_name] += 1
                has_new_message = True

        if not has_new_message:
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(0.05)


async def main():
    # 清空之前的流式消息
    clear_all_streams()

    # 初始化主 Agent
    ari = MainReActAgent()

    # 创建用户消息对象
    user_msg = Msg(
        name="user",
        content="帮我规划一下做蛋炒饭的步骤?",
        role="user"
    )

    # 启动流式打印后台任务
    printer_task = asyncio.create_task(stream_printer())

    try:
        # 将消息发送给主 Agent 并等待最终结果
        final_result = await ari(user_msg)
    finally:
        # 取消后台打印任务
        printer_task.cancel()
        try:
            await printer_task
        except asyncio.CancelledError:
            pass
    
    print("\n" + "="*60)
    print("🎯 最终结果")
    print("="*60)
    print(final_result.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())