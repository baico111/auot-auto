import asyncio
import re
import time
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from playwright.async_api import async_playwright

# ================= 环境变量获取 =================
# 使用 os.environ.get 确保即使变量缺失也不会直接崩溃，而是返回 None
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TG_STRING_SESSION")
WEB_PASSWORD = os.environ.get("WENPASSWORD")
ACCOUNT_NAME = os.environ.get("TELEGRAM_ACCOUNT_ID", "未设置账户") # 变量化账户名
BOT_USERNAME = '@zo_computer_bot'

# 待发送的长指令
COMMAND_TEXT = """你先帮我重启我的哪吒探针agent.sh，确保哪吒探针agent.sh在运行后再帮我依次运行下面的代码，并发给我日志中显示的最新的域名

nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8000 >> /opt/openai-cpa/cf.log 2>&1 &

cd /opt/openai-cpa && source venv/bin/activate

nohup python wfxl_openai_regst.py >> /opt/openai-cpa/run.log 2>&1 &

grep -o 'https://.*\\.trycloudflare\\.com' /opt/openai-cpa/cf.log"""
# ===============================================

async def main():
    if not STRING_SESSION or not API_ID:
        print("错误: 缺少必要的环境变量 (SESSION 或 ID)")
        return

    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Session 已失效，请更新环境变量中的 TG_STRING_SESSION")
        return

    print("已连接 Telegram，正在向机器人发送重启与查询指令...")
    await client.send_message(BOT_USERNAME, COMMAND_TEXT)
    
    target_url = None
    
    # 监听回复
    @client.on(events.NewMessage(from_users=BOT_USERNAME))
    async def handler(event):
        nonlocal target_url
        msg_text = event.message.message
        # 匹配 trycloudflare 的域名格式
        found_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', msg_text)
        if found_urls:
            target_url = found_urls[0]
            print(f"成功捕获最新域名: {target_url}")
            # 停止监听
            client.remove_event_handler(handler)

    # 在 GitHub Actions 中建议给足等待时间（10分钟）
    timeout = 600
    start_time = time.time()
    while not target_url and (time.time() - start_time < timeout):
        await asyncio.sleep(5) # 稍微加大轮询间隔，减少 CPU 占用

    if target_url:
        print("开始执行网页自动化任务...")
        report_data = await automate_web_process(target_url)
        if report_data:
            await send_final_report(client, report_data)
        else:
            print("网页自动化操作未成功完成。")
    else:
        print("超时：未能从机器人回复中获取到域名。")

    await client.disconnect()

async def automate_web_process(url):
    async with async_playwright() as p:
        # GitHub Actions 环境必须 headless=True
        browser = await p.chromium.launch(headless=True)
        # 设置较大的视口确保按钮都在可见范围内
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        try:
            await page.goto(url, timeout=60000, wait_until="networkidle")
            
            # 1. 登录：输入密码
            pw_selector = 'input.appearance-none.border-2.border-slate-200'
            await page.wait_for_selector(pw_selector, timeout=20000)
            await page.fill(pw_selector, WEB_PASSWORD)
            
            # 2. 点击安全登录
            await page.click('button:has-text("安全登录")')
            await page.wait_for_load_state("networkidle")
            print("网页登录成功")

            # 3. 提取库存：先点按钮，等一会儿再抓数值
            await page.click('button:has-text("账号库存")')
            await asyncio.sleep(5) 
            stock_count = await page.inner_text('span.text-indigo-600.text-base.font-black')
            print(f"当前库存数值: {stock_count}")

            # 4. 启动：点击并等待 30 秒
            await page.click('button:has-text("启动")')
            print("已触发启动动作，等待 30 秒系统响应...")
            await asyncio.sleep(30)
            
            # 5. 截图存档
            screenshot_path = "result.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            
            return {"stock": stock_count, "image": screenshot_path}
        except Exception as e:
            print(f"Playwright 运行中出现错误: {e}")
            return None
        finally:
            await browser.close()

async def send_final_report(client, data):
    # 修正北京时间 (UTC+8)
    bj_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 8*3600))
    
    # 维持你要求的“梅式”UI 风格
    report_text = f"""✅ Zo-自动启用报告 by-Baico
————————————————————
👤 账户：{ACCOUNT_NAME}
🛰️ 状态：启动成功 ✅
📅 仓库帐号：{data['stock']}
🕒 北京时间：{bj_time}
————————————————————"""
    
    await client.send_file(BOT_USERNAME, data['image'], caption=report_text)
    print("最终报告已发送至 Telegram。")

if __name__ == "__main__":
    asyncio.run(main())
