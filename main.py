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

# 通知配置
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MY_CHAT_ID = os.environ.get("MY_CHAT_ID")

TARGET_BOT = "zo_computer_bot"

COMMAND_TEXT = """你先帮我重启我的哪吒探针agent.sh，确保哪吒探针agent.sh在运行后再帮我依次运行下面的代码，并发给我日志中显示的最新的域名。

pkill -f cloudflared

nohup /usr/local/bin/cloudflared tunnel --url http://127.0.0.1:8000 >> /opt/openai-cpa/cf.log 2>&1 &

cd /opt/openai-cpa && source venv/bin/activate

nohup python wfxl_openai_regst.py >> /opt/openai-cpa/run.log 2>&1 &

grep -o 'https://.*\\.trycloudflare\\.com' /opt/openai-cpa/cf.log"""
# ===============================================

async def main():
    app = Client(
        "my_account",
        session_string=STRING_SESSION,
        api_id=API_ID,
        api_hash=API_HASH
    )

    await app.start()

    # --- 第一步：严格的前置检测逻辑 ---
    print("[LOG] >>> 步骤 1: 开始前置域名检测...", flush=True)
    should_send_new_command = True
    
    last_message = None
    async for msg in app.get_chat_history(TARGET_BOT, limit=1):
        last_message = msg
        break

    if last_message:
        found_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', last_message.text or "")
        if found_urls:
            last_url = found_urls[0]
            print(f"[LOG] 发现历史域名: {last_url}，尝试登录验证...", flush=True)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(viewport={'width': 1280, 'height': 800})
                page = await context.new_page()
                try:
                    await page.goto(last_url, timeout=30000, wait_until="networkidle")
                    pw_input = 'input.appearance-none.border-2.border-slate-200'
                    await page.wait_for_selector(pw_input, timeout=10000)
                    await page.fill(pw_input, WEB_PASSWORD)
                    await page.click('button:has-text("安全登录")')
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(5) # 等待渲染
                    
                    content = await page.content()
                    if "停止" in content:
                        print("[LOG] 状态确认：程序正在运行中（发现停止按钮）。任务提前结束。", flush=True)
                        should_send_new_command = False
                    elif "启动" in content:
                        print("[LOG] 状态确认：页面显示启动按钮，执行点击唤醒...", flush=True)
                        await page.click('button:has-text("启动")')
                        await asyncio.sleep(5)
                        print("[LOG] 唤醒操作已完成。任务提前结束。", flush=True)
                        should_send_new_command = False
                    else:
                        print("[LOG] 状态不明：未发现启动/停止按钮，将执行发指令流程。", flush=True)
                except Exception as e:
                    print(f"[LOG] 历史域名访问失败({e})，准备发送新指令...", flush=True)
                finally:
                    await browser.close()
        else:
            print("[LOG] 历史消息中未发现域名。", flush=True)
    else:
        print("[LOG] 未找到历史消息记录。", flush=True)

    # --- 第二步：根据检测结果决定是否继续 ---
    if not should_send_new_command:
        await app.stop()
        return

    # --- 第三步：原本的发消息流程 (只有上面检测失败或判定需要时才运行) ---
    print("[LOG] >>> 步骤 2: 开始执行原定发指令流程...", flush=True)
    print("已连接 Telegram，发送指令中...", flush=True)
    await app.send_message(TARGET_BOT, COMMAND_TEXT)
    
    target_url = None
    timeout = 600
    start_time = time.time()
    
    while not target_url and (time.time() - start_time < timeout):
        async for message in app.get_chat_history(TARGET_BOT, limit=1):
            found_urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', message.text or "")
            if found_urls:
                target_url = found_urls[0]
                print(f"提取到新域名: {target_url}", flush=True)
                break
        if not target_url:
            await asyncio.sleep(10)

    if target_url:
        report_data = await automate_web_process(target_url)
        if report_data:
            send_ui_report(report_data)

    await app.stop()

def send_ui_report(data):
    bj_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 8*3600))
    report_html = (
        f"✅ <b>Zo-自动启用报告 by-Baico</b>\n"
        f"————————————————————\n"
        f"👤 <b>账户:</b> <code>{ACCOUNT_NAME}</code>\n"
        f"🛰️ <b>状态:</b> 启动成功 ✅\n"
        f"📅 <b>仓库帐号:</b> {data['stock']}\n"
        f"🕒 <b>北京时间:</b> {bj_time}\n"
        f"————————————————————"
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        photo_path = data['image']
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                r = requests.post(url, data={'chat_id': MY_CHAT_ID, 'caption': report_html, 'parse_mode': 'HTML'}, files={'photo': photo}, timeout=15)
                if r.status_code == 200:
                    print(f"✅ 推送成功", flush=True)
    except Exception as e:
        print(f"❌ 发送异常: {e}", flush=True)

async def automate_web_process(url):
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                print(f"访问网页 (第 {attempt} 次)...", flush=True)
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                pw_sel = 'input.appearance-none.border-2.border-slate-200'
                await page.wait_for_selector(pw_sel, timeout=30000)
                await page.fill(pw_sel, WEB_PASSWORD)
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
                print(f"操作失败: {e}", flush=True)
                if attempt == max_retries: return None
                await asyncio.sleep(5)
            finally:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
