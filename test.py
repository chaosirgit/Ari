import asyncio

from agentscope.message import Msg

from core import AriAgent

async def display_thinking_stream(thinking_stream):
    """显示思考过程流"""
    thinking_received = False
    async for thinking_chunk in thinking_stream:
        if not thinking_received:
            print("\n💭 思考过程:", end="", flush=True)
            thinking_received = True
        print(thinking_chunk, end="", flush=True)

    if thinking_received:
        print()  # 思考过程结束后换行


async def display_tool_stream(tool_stream):
    """显示工具调用流"""
    tools_received = False
    async for tool_call in tool_stream:
        if not tools_received:
            print("\n🔧 工具调用:")
            tools_received = True
        print(f"   • {tool_call['name']}: {tool_call['input']}")

    if tools_received:
        print()  # 工具调用结束后换行


async def display_text_stream(text_stream):
    """显示文本回复流"""
    print("🤖 Ari: ", end="", flush=True)
    async for text_chunk in text_stream:
        print(text_chunk, end="", flush=True)
    print()  # 回复结束后换行

async def test_terminal():
    """主函数"""
    print("🚀 AriAgent 测试启动")
    print("💡 输入 'quit' 或 'exit' 退出程序")
    print("📊 支持显示: 文本回复 | 思考过程 | 工具调用")
    print("💬 开始对话吧！\n")

    # 创建 AriAgent 实例
    try:
        ari = AriAgent()
        print("✅ AriAgent 初始化成功\n")
    except Exception as e:
        print(f"❌ AriAgent 初始化失败: {e}")
        print("请检查你的配置和依赖")
        return

    # 交互式循环
    conversation_count = 1
    while True:
        try:
            # 获取用户输入
            user_input = input(f"👤 用户 [{conversation_count}]: ").strip()

            # 检查退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break

            # 跳过空输入
            if not user_input:
                continue

            # 创建消息对象
            user_msg = Msg(
                name="user",
                content=user_input,
                role="user"
            )

            print(f"\n🔄 正在处理请求...")

            # 调用 AriAgent
            response = await ari(user_msg)

            # 并行显示不同类型的流式内容
            # 注意：实际使用中可能需要按顺序显示，这里为了演示所有功能

            # 1. 显示思考过程（如果有）
            thinking_task = asyncio.create_task(display_thinking_stream(response.get_thinking_stream()))

            # 2. 显示工具调用（如果有）
            tool_task = asyncio.create_task(display_tool_stream(response.get_tool_stream()))

            # 等待思考和工具调用完成
            await asyncio.gather(thinking_task, tool_task)

            # 3. 显示最终文本回复
            await display_text_stream(response.get_text_stream())

            # 显示完整统计信息（可选）
            final_text = response.get_final_text()
            final_thinking = response.get_final_thinking()
            final_tools = response.get_final_tools()

            if final_thinking or final_tools:
                print("📋 完整摘要:")
                if final_thinking:
                    print(f"   • 思考长度: {len(final_thinking)} 字符")
                if final_tools:
                    print(f"   • 工具调用: {len(final_tools)} 次")
                if final_text:
                    print(f"   • 回复长度: {len(final_text)} 字符")
                print()

            conversation_count += 1

        except KeyboardInterrupt:
            print("\n\n👋 收到中断信号，再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            print("请检查你的网络连接、API密钥等配置\n")

async def main():
    # 创建消息对象
    user_msg = Msg(
        name="user",
        content="帮我规划一下做蛋炒饭的步骤?",
        role="user"
    )
    ari = AriAgent()
    # 调用 AriAgent
    response = await ari(user_msg)

    # 并行显示不同类型的流式内容
    # 注意：实际使用中可能需要按顺序显示，这里为了演示所有功能

    # 1. 显示思考过程（如果有）
    print("🔍 开始读取思考流...")
    thinking_task = asyncio.create_task(display_thinking_stream(response.get_thinking_stream()))
    print("\n✅ 思考流结束\n")

    # TODO 任务名称,描述,状态显示 如果有规划任务


    # 2. 显示工具调用（如果有）
    print("🔍 开始读取工具流...")
    tool_task = asyncio.create_task(display_tool_stream(response.get_tool_stream()))
    print("✅ 工具流结束\n")


    # 等待思考和工具调用完成
    await asyncio.gather(thinking_task, tool_task)

    # 3. 显示最终文本回复
    print("🔍 最终文本...")

    await display_text_stream(response.get_text_stream())
    print("\n✅ 最终文本\n")


    print("\n✅ 测试完成")


if __name__ == "__main__":

    # 运行主函数
    asyncio.run(main())