import asyncio
import os
from pyrogram import Client

# ================= 环境变量获取 =================
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TG_STRING_SESSION")

# 目标机器人列表
TARGET_BOTS = ["qwenpwa_bot", "qwenpwa2_bot"]
COMMAND_TEXT = "你好，现在长沙天气怎么样，然后再帮我看看现在BTC是什么价格了。"
# ===============================================

async def main():
    app = Client(
        "my_account",
        session_string=STRING_SESSION,
        api_id=API_ID,
        api_hash=API_HASH
    )

    await app.start()
    print("[LOG] 已成功连接 Telegram", flush=True)

    for target_bot in TARGET_BOTS:
        try:
            print(f"[LOG] 正在向 {target_bot} 发送消息...", flush=True)
            await app.send_message(target_bot, COMMAND_TEXT)
            print(f"[LOG] 消息已成功发送至 {target_bot}", flush=True)
        except Exception as e:
            print(f"[LOG] 发送至 {target_bot} 失败: {e}", flush=True)

    await app.stop()
    print("[LOG] 所有任务完成，客户端已关闭。", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
