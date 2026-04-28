import asyncio
import re
import time
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from playwright.async_api import async_playwright

# ================= 环境变量获取 =================
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TG_STRING_SESSION")
WEB_PASSWORD = os.environ.get("WENPASSWORD")
ACCOUNT_NAME = os.environ.get("TELEGRAM_ACCOUNT_ID", "未设置账户")

# --- 新增：你自己的机器人配置 ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# 接收通知的个人 ID (可以是你的 TG 数字 ID，也可以是某个频道的 ID)
MY_CHAT_ID = os.environ.get("TELEGRAM_API_ID") 

TARGET_BOT = '@zo_computer_bot'

COMMAND_TEXT = """你先帮我重启我的哪吒探针agent.sh，确保哪吒探针agent.sh在运行后再帮我依次运行下面的代码，并发给我日志中显示的最新的域名

nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8000 >> /opt/openai-cpa/cf.log 2>&1 &

cd /opt/openai-cpa && source venv/bin/activate

nohup python wfxl_openai_regst.py >> /opt/openai-cpa/run.log 2>&1 &

grep -o 'https://.*\\.trycloudflare\\.com' /opt/openai-cpa/cf.log"""
# ===============================================

async def main():
    # 使用 StringSession 登录你的个人账号
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    
    # 另外启动一个专门用于发送通知的 Bot 客户端
    my_bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

    await client.connect()
    if not await client.is_user_authorized():
        print("Session 失效")
        return

    print("已连接，发送指令中...")
    await client.send_message(TARGET_BOT, COMMAND_TEXT)
    
    target_url = None
    @client.on(events.NewMessage(from_users=TARGET_BOT))
    async def handler(event):
        nonlocal target_url
        found_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', event.message.message)
        if found_urls:
            target_url = found_urls[0]
            client.remove_event_handler(handler)

    timeout = 600
    start_time = time.time()
    while not target_url and (time.time() - start_time < timeout):
        await asyncio.sleep(5)

    if target_url:
        report_data = await automate_web_process(target_url)
        if report_data:
            # 1. 给对方机器人发报告
            await send_final_report(client, TARGET_BOT, report_data)
            
            # 2. 给【你自己】的机器人发通知
            async with my_bot:
                await send_final_report(my_bot, int(MY_CHAT_ID), report_data)
                print("通知已发送到你的个人机器人")
    
    await client.disconnect()

async def automate_web_process(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.fill('input.appearance-none.border-2.border-slate-200', WEB_PASSWORD)
            await page.click('button:has-text("安全登录")')
            await page.wait_for_load_state("networkidle")

            await page.click('button:has-text("账号库存")')
            await asyncio.sleep(5)
            stock_count = await page.inner_text('span.text-indigo-600.text-base.font-black')

            await page.click('button:has-text("启动")')
            await asyncio.sleep(30)
            
            screenshot_path = "result.png"
            await page.screenshot(path=screenshot_path)
            return {"stock": stock_count, "image": screenshot_path}
        except Exception as e:
            print(f"操作失败: {e}")
            return None
        finally:
            await browser.close()

async def send_final_report(tg_client, target, data):
    bj_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 8*3600))
    report_text = f"""✅ Zo-自动启用报告 by-Baico
————————————————————
👤 账户：{ACCOUNT_NAME}
🛰️ 状态：启动成功 ✅
📅 仓库帐号：{data['stock']}
🕒 北京时间：{bj_time}
————————————————————"""
    await tg_client.send_file(target, data['image'], caption=report_text)

if __name__ == "__main__":
    asyncio.run(main())
