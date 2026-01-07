import asyncio

from agentscope.message import Msg

from core.main_agent import MainReActAgent

async def main():
    # 创建消息对象
    user_msg = Msg(
        name="user",
        content="帮我规划一下做蛋炒饭的步骤?",
        role="user"
    )
    ari = MainReActAgent()
    # 调用 AriAgent
    response = await ari(user_msg)
    # TODO 流式打印步骤规划
    # TODO 流式打印文本结果

    print("\n✅ 测试完成")


if __name__ == "__main__":

    # 运行主函数
    asyncio.run(main())