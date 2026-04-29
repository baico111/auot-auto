import asyncio
import re
import time
import os
import requests  # 引入 requests 用于发图
from pyrogram import Client
from playwright.async_api import async_playwright

# ================= 环境变量获取 =================
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TG_STRING_SESSION")
WEB_PASSWORD = os.environ.get("WENPASSWORD")
ACCOUNT_NAME = os.environ.get("TELEGRAM_ACCOUNT_ID", "未设置账户")

# 通知配置 (发图逻辑的关键变量)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MY_CHAT_ID = os.environ.get("MY_CHAT_ID") # 接收通知的 ID

TARGET_BOT = "zo_computer_bot"

COMMAND_TEXT = """你先帮我重启我的哪吒探针agent.sh，确保哪吒探针agent.sh在运行后再帮我依次运行下面的代码，并发给我日志中显示的最新的域名。

nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8000 >> /opt/openai-cpa/cf.log 2>&1 &

cd /opt/openai-cpa && source venv/bin/activate

nohup python wfxl_openai_regst.py >> /opt/openai-cpa/run.log 2>&1 &

grep -o 'https://.*\\.trycloudflare\\.com' /opt/openai-cpa/cf.log"""
# ===============================================

async def main():
    # 只需要启动这一个 Client 用来交互
    app = Client(
        "my_account",
        session_string=STRING_SESSION,
        api_id=API_ID,
        api_hash=API_HASH
    )

    await app.start()

    # ================= 增加的功能：前置状态检查与旧域名尝试 =================
    print("正在检查历史域名状态...")
    should_continue_original_flow = True
    
    async for last_message in app.get_chat_history(TARGET_BOT, limit=1):
        found_last_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', last_message.text or "")
        if found_last_urls:
            last_url = found_last_urls[0]
            print(f"检测到历史域名: {last_url}，尝试访问...")
            
            # 针对旧域名的刷新/访问重试逻辑
            access_success = False
            for retry_count in range(3):
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(viewport={'width': 1280, 'height': 800})
                    page = await context.new_page()
                    try:
                        await page.goto(last_url, timeout=30000, wait_until="domcontentloaded")
                        pw_selector = 'input.appearance-none.border-2.border-slate-200'
                        await page.wait_for_selector(pw_selector, timeout=10000)
                        await page.fill(pw_selector, WEB_PASSWORD)
                        await page.click('button:has-text("安全登录")')
                        await page.wait_for_load_state("networkidle")
                        
                        access_success = True # 成功登录进去了
                        
                        # 检查按钮状态
                        stop_btn = await page.query_selector('span:has-text("停止")')
                        start_btn = await page.query_selector('span:has-text("启动")')
                        
                        if stop_btn:
                            print("界面显示『停止』，程序已在运行中，任务结束。")
                            should_continue_original_flow = False
                        elif start_btn:
                            print("界面显示『启动』，正在执行点击启动...")
                            await page.click('button:has-text("启动")')
                            await asyncio.sleep(10) # 等待启动反馈
                            print("已执行启动操作，任务结束。")
                            should_continue_original_flow = False
                        break # 既然登录成功并处理了，跳出重试循环

                    except Exception as e:
                        print(f"第 {retry_count + 1} 次尝试访问旧域名失败: {e}")
                        if retry_count < 2:
                            await asyncio.sleep(5) # 刷新前的等待
                    finally:
                        await browser.close()
                
                if not should_continue_original_flow:
                    break

    if not should_continue_original_flow:
        await app.stop()
        return
    
    print("旧域名无效或无法处理，开始执行原定 Bot 交互流程...")
    # =====================================================================

    print("已连接 Telegram，发送指令中...")
    await app.send_message(TARGET_BOT, COMMAND_TEXT)
    
    target_url = None
    timeout = 600
    start_time = time.time()
    
    while not target_url and (time.time() - start_time < timeout):
        async for message in app.get_chat_history(TARGET_BOT, limit=1):
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
            # 成功后调用发图逻辑
            send_ui_report(report_data)

    await app.stop()

def send_ui_report(data):
    """发图逻辑：完全仿照 Hax 脚本的 requests 实现方式"""
    bj_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 8*3600))
    
    # 构造 HTML 格式的报告
    report_html = (
        f"✅ <b>Zo-自动启用报告 by-Baico</b>\n"
        f"————————————————————\n"
        f"👤 <b>账户:</b> <code>{ACCOUNT_NAME}</code>\n"
        f"🛰️ <b>状态:</b> 启动成功 ✅\n"
        f"📅 <b>仓库帐号:</b> {data['stock']}\n"
        f"🕒 <b>北京时间:</b> {bj_time}\n"
        f"————————————————————"
    )
    
    # 使用 Bot API 的 sendPhoto 接口
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    try:
        photo_path = data['image']
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                r = requests.post(url, data={
                    'chat_id': MY_CHAT_ID, 
                    'caption': report_html, 
                    'parse_mode': 'HTML'
                }, files={'photo': photo}, timeout=15)
                
                if r.status_code == 200:
                    print(f"✅ 结果已通过 Bot API 成功推送至 ID: {MY_CHAT_ID}")
                else:
                    print(f"❌ Bot 发送失败，响应码: {r.status_code}, 内容: {r.text}")
        else:
            print(f"❌ 找不到截图文件: {photo_path}")
    except Exception as e:
        print(f"❌ 发送环节发生异常: {e}")

async def automate_web_process(url):
    max_retries = 3  # 最大重试次数
    for attempt in range(1, max_retries + 1):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 800})
            page = await context.new_page()
            try:
                print(f"正在尝试访问网页 (第 {attempt}/{max_retries} 次)...")
                # 增加 goto 的超时到 60 秒，并使用 wait_until 确保网络相对空闲
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                pw_selector = 'input.appearance-none.border-2.border-slate-200'
                # 等待选择器时增加重试逻辑
                await page.wait_for_selector(pw_selector, timeout=30000)
                
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
                
                print("网页操作成功！")
                return {"stock": stock_count, "image": screenshot_path}

            except Exception as e:
                print(f"第 {attempt} 次操作失败: {e}")
                if attempt < max_retries:
                    print("等待 5 秒后尝试刷新重试...")
                    await asyncio.sleep(5)
                    # 循环会继续，重新启动浏览器环境
                else:
                    print("已达到最大重试次数，放弃操作。")
                    return None
            finally:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
