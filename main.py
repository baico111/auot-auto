import asyncio
import re
import time
import os
from pyrogram import Client, filters
from playwright.async_api import async_playwright

# ================= 环境变量获取 =================
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TG_STRING_SESSION")
WEB_PASSWORD = os.environ.get("WENPASSWORD")
ACCOUNT_NAME = os.environ.get("TELEGRAM_ACCOUNT_ID", "未设置账户")

# 通知配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MY_CHAT_ID = int(os.environ.get("TELEGRAM_API_ID", 0)) 

TARGET_BOT = "zo_computer_bot" # Pyrogram 不需要加 @

COMMAND_TEXT = """你先帮我重启我的哪吒探针agent.sh，确保哪吒探针agent.sh在运行后再帮我依次运行下面的代码，并发给我日志中显示的最新的域名

nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8000 >> /opt/openai-cpa/cf.log 2>&1 &

cd /opt/openai-cpa && source venv/bin/activate

nohup python wfxl_openai_regst.py >> /opt/openai-cpa/run.log 2>&1 &

grep -o 'https://.*\\.trycloudflare\\.com' /opt/openai-cpa/cf.log"""
# ===============================================

async def main():
    # 使用 Pyrogram 客户端
    app = Client(
        "my_account",
        session_string=STRING_SESSION,
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    # 启动用于发通知的 Bot 客户端
    bot_app = Client(
        "my_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    await app.start()
    await bot_app.start()

    print("已连接 Telegram (Pyrogram)，发送指令中...")
    await app.send_message(TARGET_BOT, COMMAND_TEXT)
    
    target_url = None
    
    # 轮询检查新消息（Pyrogram 的简单实现）
    timeout = 600
    start_time = time.time()
    while not target_url and (time.time() - start_time < timeout):
        async for message in app.get_chat_history(TARGET_BOT, limit=1):
            # 检查是否是机器人刚发的包含域名的消息
            found_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', message.text or "")
            if found_urls:
                target_url = found_urls[0]
                print(f"提取到域名: {target_url}")
                break
        if not target_url:
            await asyncio.sleep(10)

    if target_url:
        report_data = await automate_web_process(target_url)
        if report_data:
            # 构造报告文本
            bj_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 8*3600))
            report_text = f"""✅ Zo-自动启用报告 by-Baico
————————————————————
👤 账户：{ACCOUNT_NAME}
🛰️ 状态：启动成功 ✅
📅 仓库帐号：{report_data['stock']}
🕒 北京时间：{bj_time}
————————————————————"""
            
            # --- 核心修改：只发给你设置的机器人 ---
            # 使用 bot_app 发送，目标是你的个人 ID (MY_CHAT_ID)
            try:
                await bot_app.send_photo(
                    chat_id=MY_CHAT_ID, 
                    photo=report_data['image'], 
                    caption=report_text
                )
                print(f"✅ 结果已成功推送至你的 Bot (ID: {MY_CHAT_ID})")
            except Exception as e:
                print(f"❌ Bot 发送失败: {e}")

    await app.stop()
    await bot_app.stop()

async def automate_web_process(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        try:
            await page.goto(url, timeout=60000)
            pw_selector = 'input.appearance-none.border-2.border-slate-200'
            await page.wait_for_selector(pw_selector)
            await page.fill(pw_selector, WEB_PASSWORD)
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
            print(f"网页操作失败: {e}")
            return None
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
