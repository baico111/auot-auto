import time
import os
import json
import re
import random
import requests

# ================= 环境配置 =================
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"

if "XAUTHORITY" not in os.environ:
    if os.path.exists("/home/headless/.Xauthority"):
        os.environ["XAUTHORITY"] = "/home/headless/.Xauthority"

print(f"[DEBUG] Env DISPLAY: {os.environ.get('DISPLAY')}")
print(f"[DEBUG] Env XAUTHORITY: {os.environ.get('XAUTHORITY')}")

from seleniumbase import SB

# ================= 配置区域 =================
PROXY_URL = os.getenv("PROXY", "")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

ACCOUNTS = os.getenv("ACCOUNTS", "")

URL_LOGIN_PANEL = "https://www.bytenut.com/auth/login"


# ================= 解析多账号 =================
def parse_accounts(accounts_str):
    accounts = []
    if not accounts_str:
        return accounts

    for item in accounts_str.split("|"):
        try:
            u, p, n, a = item.split(",")
            accounts.append((u.strip(), p.strip(), n.strip(), a.strip()))
        except:
            print(f"[WARN] 格式错误: {item}")

    return accounts


# ================= 主类 =================
class BytenutRenewal:

    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # ===== 新增：结果收集器 =====
        self.results = []

    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] [INFO] {msg}", flush=True)

    def send_telegram_notify(self, message, photo_path=None):
        if not TG_TOKEN or not TG_CHAT_ID:
            self.log("⚠️ 未配置 TG，跳过")
            return

        try:
            if photo_path and os.path.exists(photo_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(photo_path, "rb") as f:
                    requests.post(url, data={
                        "chat_id": TG_CHAT_ID,
                        "caption": message
                    }, files={"photo": f})
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={
                    "chat_id": TG_CHAT_ID,
                    "text": message
                })
        except Exception as e:
            self.log(f"TG失败: {e}")

    def run(self):

        timestamp = time.strftime('%H:%M:%S')
        self.log(f"🚀 开始执行 ByteNut 保活 {timestamp}")

        accounts = parse_accounts(ACCOUNTS)

        if not accounts:
            self.log("❌ 没有账号")
            return

        self.log(f"🚀 共 {len(accounts)} 个账号")

        for idx, (USERNAME, PASSWORD, NUM, AREA) in enumerate(accounts, 1):

            URL_SERVER_PANEL = f"https://www.bytenut.com/free-gamepanel/{NUM}"

            self.log("=" * 60)
            self.log(f"🚀 [{idx}] 开始账号: {USERNAME} | Server {NUM}")
            self.log("=" * 60)

            with SB(
                uc=True,
                test=True,
                headed=True,
                headless=False,
                xvfb=False,
                chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-position=0,0,--start-maximized",
                proxy=PROXY_URL if PROXY_URL else None
            ) as sb:

                try:
                    # ================= IP检测 =================
                    self.log("🌍 检测IP...")
                    try:
                        sb.open("https://api.ipify.org?format=json")
                        ip_val = json.loads(re.search(r'\{.*\}', sb.get_text("body")).group(0)).get("ip", "Unknown")
                        parts = ip_val.split(".")
                        self.log(f"IP: {parts[0]}.{parts[1]}.***.{parts[-1]}")
                    except:
                        self.log("⚠️ IP跳过")

                    # ================= 登录 =================
                    self.log("📂 打开登录页")
                    sb.uc_open_with_reconnect(URL_LOGIN_PANEL, reconnect_time=5)

                    sb.wait_for_element_visible('input[placeholder="Username"]', timeout=25)
                    sb.type('input[placeholder="Username"]', USERNAME)
                    sb.type('input[placeholder="Password"]', PASSWORD)

                    self.log("🖱️ 登录")
                    sb.click('//button[contains(., "Sign In")]')
                    time.sleep(10)

                    # ================= Consent =================
                    try:
                        sb.click('//button[contains(., "Consent")]')
                    except:
                        pass

                    # ================= 进入服务器 =================
                    self.log("📂 进入服务器页面")
                    sb.uc_open_with_reconnect(URL_SERVER_PANEL, reconnect_time=6)

                    time.sleep(5)

                    self.log("🖱️ RENEW SERVER")
                    sb.click('//li[contains(., "RENEW SERVER")]')

                    time.sleep(3)

                    # ================= Cloudflare =================
                    try:
                        sb.uc_gui_click_captcha()
                        sb.uc_gui_handle_captcha()
                    except:
                        pass

                    # ================= Extend Time =================
                    self.log("🖱️ 检查 Extend Time 状态...")

                    extend_selector = '//button[contains(., "Extend")]'

                    try:
                        if sb.is_element_present(extend_selector):

                            if sb.is_element_enabled(extend_selector):

                                sb.click(extend_selector)
                                self.log("✅ 已执行续期")

                                self.results.append(
                                    f"✅ 成功 | {USERNAME} | {NUM} | {AREA}"
                                )

                            else:
                                self.log("⏳ 冷却中")

                                self.results.append(
                                    f"⏳ 冷却 | {USERNAME} | {NUM} | {AREA}"
                                )

                                continue

                        else:
                            self.log("⚠️ 未找到按钮")

                            self.results.append(
                                f"⚠️ 未找到 | {USERNAME} | {NUM} | {AREA}"
                            )

                            continue

                    except Exception as e:
                        self.log(f"⚠️ Extend异常: {e}")

                        self.results.append(
                            f"❌ Extend异常 | {USERNAME} | {NUM} | {AREA}"
                        )

                        continue

                    time.sleep(5)

                    # ================= 成功截图 =================
                    shot = f"{self.screenshot_dir}/ok_{USERNAME}.png"
                    sb.save_screenshot(shot)

                    self.log(f"✅ 完成 {USERNAME}")

                except Exception as e:

                    self.log(f"❌ 失败 {USERNAME}: {e}")

                    err = f"{self.screenshot_dir}/err_{USERNAME}.png"
                    try:
                        sb.save_screenshot(err)
                    except:
                        pass

                    self.results.append(
                        f"❌ 失败 | {USERNAME} | {NUM} | {AREA} | {e}"
                    )

        # ================= 最终TG汇总（新增重点） =================
        self.log("📊 生成最终汇总...")

        summary = "\n".join(self.results)

        final_msg = (
            "📊 ByteNut 续期汇总\n\n"
            f"{summary}\n\n"
            f"总计: {len(self.results)} 条记录"
        )

        self.send_telegram_notify(final_msg)

        self.log("✅ TG汇总已发送")


# ================= 启动 =================
if __name__ == "__main__":
    BytenutRenewal().run()
