"""
WMS App 自动登录脚本
基于 Appium + UiAutomator2，使用 resource-id / class 定位，不依赖坐标。
使用方式：
    python wms_login.py --user <用户名> --pwd "<密码>" --warehouse NJ
    python wms_login.py --user <用户名> --pwd "<密码>" --warehouse NJ --target consolidation
    python wms_login.py --target load-truck   # 账号密码取自环境变量 WMS_APP_USER / WMS_APP_PASSWORD
环境变量：
    WMS_APP_USER       默认用户名（未传 --user 时使用）
    WMS_APP_PASSWORD   默认密码（未传 --pwd 时使用）
    WMS_DEVICE_UDID    设备序列号（adb devices 显示的 ID）
    WMS_SCREENSHOT_DIR 截图输出目录（可选，默认 当前目录/docs/tmp/wms_test）
"""

import argparse
import os
import time
import sys
import subprocess

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
try:
    from appium.options import UiAutomator2Options
except ImportError:
    # Appium-Python-Client >= 3.x
    from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ── 配置 ─────────────────────────────────────────────────
APPIUM_URL   = "http://127.0.0.1:4723"
APP_PKG      = "com.wmsrn"
APP_ACTIVITY = ".MainActivity"
DEVICE_UDID  = os.environ.get("WMS_DEVICE_UDID", "")
# 截图输出目录：优先环境变量 WMS_SCREENSHOT_DIR，否则用当前目录（主工作空间根）下的 docs/tmp/wms_test
SCREENSHOT_DIR = os.environ.get("WMS_SCREENSHOT_DIR") or os.path.join(os.getcwd(), "docs", "tmp", "wms_test")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 默认账号（UAT / NJ 仓）：从环境变量读取，不在脚本中保存明文
DEFAULT_USER      = os.environ.get("WMS_APP_USER", "")
DEFAULT_PASSWORD  = os.environ.get("WMS_APP_PASSWORD", "")
DEFAULT_WAREHOUSE = "NJ"

# ── Appium 连接选项（优化速度）────────────────────────────
def build_options() -> UiAutomator2Options:
    opts = UiAutomator2Options()
    opts.platform_name           = "Android"
    opts.device_name             = DEVICE_UDID
    opts.udid                    = DEVICE_UDID
    opts.app_package             = APP_PKG
    opts.app_activity            = APP_ACTIVITY
    opts.no_reset                = True   # 保留登录态（避免清 app 数据）
    opts.auto_launch             = True
    opts.skip_server_installation       = True  # 跳过 UiAutomator2 server 安装
    opts.skip_device_initialization     = True
    opts.skip_unlock                     = True
    opts.disable_window_animation        = True  # 关动画，操作更快
    opts.uiautomator2_server_launch_timeout  = 30000
    opts.uiautomator2_server_install_timeout = 30000
    return opts


class WmsApp:
    def __init__(self):
        self.driver = None

    def connect(self):
        print("🔌 连接 Appium...")
        self.driver = webdriver.Remote(APPIUM_URL, options=build_options())
        self.driver.implicitly_wait(0)  # 用显式等待，不用隐式
        print("✅ 已连接")

    def screenshot(self, name: str):
        path = f"{SCREENSHOT_DIR}\\{name}.png"
        self.driver.save_screenshot(path)
        print(f"📸 截图: {path}")

    def wait_for_text(self, text: str, timeout: int = 8) -> bool:
        """等待页面出现指定文字，忽略 StaleElement"""
        def check(d):
            try:
                for el in d.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView"):
                    try:
                        if text in (el.text or ""):
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
            return False
        try:
            WebDriverWait(self.driver, timeout).until(check)
            return True
        except TimeoutException:
            return False

    def wait_for_any_text(self, keywords: list, timeout: int = 8) -> bool:
        """等待页面出现任意一个关键词，忽略 StaleElement"""
        def check(d):
            try:
                els = d.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                for el in els:
                    try:
                        t = el.text or ""
                        if any(k in t for k in keywords):
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
            return False
        try:
            WebDriverWait(self.driver, timeout).until(check)
            return True
        except TimeoutException:
            return False

    def wait_for_page_change(self, old_texts_joined: str, timeout: int = 5) -> bool:
        """等待页面文字发生变化（用于点击后等待跳转）"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: " ".join(
                    el.text for el in d.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                    if el.text
                ) != old_texts_joined
            )
            return True
        except TimeoutException:
            return False

    def get_all_texts(self) -> list:
        """获取页面所有文字（一次调用，Python 端判断）"""
        try:
            els = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
            result = []
            for el in els:
                try:
                    t = el.text
                    if t and t.strip():
                        result.append(t)
                except Exception:
                    pass  # StaleElement 直接跳过
            return result
        except Exception:
            return []

    def find_clickable_by_text(self, text: str, timeout: int = 5):
        """找包含指定文字的可点击元素（React Native 按钮是 ViewGroup）"""
        try:
            # 优先找 content-desc 匹配的
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (AppiumBy.XPATH,
                     f'//*[@content-desc="{text}" and @clickable="true"]')
                )
            )
            return el
        except TimeoutException:
            pass
        try:
            # 找文字子节点的可点击父元素
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (AppiumBy.XPATH,
                     f'//*[@text="{text}"]/ancestor::*[@clickable="true"][1]')
                )
            )
            return el
        except TimeoutException:
            return None

    def close_keyboard(self):
        """关闭系统键盘"""
        try:
            self.driver.hide_keyboard()
        except Exception:
            pass  # 键盘不在时不报错

    def dismiss_upgrade_dialog(self):
        """全局处理升级弹窗（Later 按钮）"""
        try:
            texts = self.get_all_texts()
            if "Later" in texts or "Update Available" in " ".join(texts):
                btn = self.find_clickable_by_text("Later", timeout=2)
                if btn:
                    btn.click()
                    print("  ⚠️  升级弹窗已关闭")
                    time.sleep(0.3)  # 等关闭动画
        except Exception:
            pass

    def login(self, username: str, password: str, warehouse: str):
        """执行登录流程"""
        print(f"\n🚀 开始登录 user={username} warehouse={warehouse}")

        # ── 等待主页/登录页加载 ──────────────────────────────
        MAIN_PAGE_KEYWORDS = ["Pre-Receive", "Receive", "Put Away", "Consolidation",
                              "Picking", "Restock", "RMA", "Inbound", "Inventory",
                              "Load Truck", "Unload Truck", "Scan Slot",
                              "Scan Tote", "Confirm Arrival", "Change Slot", "Truck ID"]
        # 等界面稳定（最多3秒，检测到内容立即继续）
        self.wait_for_any_text(MAIN_PAGE_KEYWORDS + ["WMS", "User", "password"], timeout=3)
        texts = self.get_all_texts()
        joined = " ".join(texts)

        # 已在主页或功能页（严格匹配模块名，避免 log 文字误判）
        if any(k in joined for k in MAIN_PAGE_KEYWORDS):
            print("✅ 已在 App 内，跳过登录")
            return True

        if not self.wait_for_text("WMS", timeout=10):
            print("❌ 登录页未加载，当前页面文字:", self.get_all_texts())
            sys.exit(1)

        self.dismiss_upgrade_dialog()
        self.screenshot("01_login_page")

        # ── 输入用户名 ──────────────────────────────────────
        print("⌨️  输入用户名...")
        user_input = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located(
                (AppiumBy.XPATH, '//android.widget.EditText[@resource-id="email-input"]')
            )
        )
        user_input.click()
        time.sleep(0.3)
        user_input.clear()
        user_input.send_keys(username)
        self.close_keyboard()
        time.sleep(0.3)

        # ── 输入密码 ──────────────────────────────────────
        print("🔑 输入密码...")
        pass_input = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located(
                (AppiumBy.XPATH, '//android.widget.EditText[@resource-id="password-input"]')
            )
        )
        pass_input.click()
        time.sleep(0.3)
        pass_input.clear()
        pass_input.send_keys(password)
        self.close_keyboard()
        time.sleep(0.3)

        self.screenshot("02_login_filled")

        # ── 点击 Login 按钮（第一步）────────────────────────
        print("🖱️  点击 Login（第一步）...")
        login_btn = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located(
                (AppiumBy.XPATH, '//*[@resource-id="login-button" or @content-desc="Login"]')
            )
        )
        login_btn.click()
        # 等待登录完成（主页或仓库选择框出现则继续，最多8秒）
        self.wait_for_any_text(["Pre-Receive", "Receive", "NJ Warehouse", "Select Warehouse",
                                "warehouse_number", "Inbound"], timeout=8)

        self.dismiss_upgrade_dialog()

        # ── 检查是否出现仓库选择下拉框（多仓库情况）─────────
        texts = self.get_all_texts()
        print("  第一步登录后页面文字:", texts[:8])

        warehouse_dropdown = None
        try:
            warehouse_dropdown = self.driver.find_element(
                AppiumBy.XPATH,
                '//*[@resource-id="warehouse_number-dropdown" or @content-desc="Select Warehouse"]'
            )
        except NoSuchElementException:
            pass

        if warehouse_dropdown is not None:
            # 多仓库：需要选择仓库后再次点 Login
            print(f"🏭 检测到仓库选择框，选择: {warehouse}")
            warehouse_dropdown.click()
            # 等待下拉选项出现
            self.wait_for_text(warehouse, timeout=3)

            # 在下拉选项里找匹配的仓库（按名称或编号）
            try:
                wh_option = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (AppiumBy.XPATH,
                         f'//*[contains(@text, "{warehouse}") and @clickable="true"]')
                    )
                )
                wh_option.click()
                print(f"  ✅ 已选择仓库: {warehouse}")
            except TimeoutException:
                # 如果找不到精确匹配，打印可用选项
                options = self.driver.find_elements(
                    AppiumBy.CLASS_NAME, "android.widget.TextView"
                )
                print(f"  ⚠️  未找到 '{warehouse}'，可用选项:", [o.text for o in options if o.text])
                # 尝试部分匹配
                for opt in options:
                    if warehouse.upper() in opt.text.upper():
                        opt.click()
                        print(f"  ✅ 部分匹配选择: {opt.text}")
                        break
            time.sleep(0.3)  # 短暂等下拉关闭动画

            # 第二步：再次点 Login
            print("🖱️  点击 Login（第二步，完成登录）...")
            login_btn2 = self.driver.find_element(
                AppiumBy.XPATH,
                '//*[@resource-id="login-button" or @content-desc="Login"]'
            )
            login_btn2.click()
            # 等待主页加载
            self.wait_for_any_text(["Pre-Receive", "Receive", "Inbound"], timeout=8)

        elif any("Warehouse" in t for t in texts) and "Select" in " ".join(texts):
            print(f"🏭 检测到独立仓库选择页，查找: {warehouse}")
            wh_btn = self.find_clickable_by_text(warehouse, timeout=5)
            if wh_btn:
                wh_btn.click()
                # 等待跳转完成
                self.wait_for_any_text(["Pre-Receive", "Receive", "Inbound"], timeout=8)
                print(f"✅ 已选择仓库: {warehouse}")

        self.dismiss_upgrade_dialog()
        self.screenshot("03_after_login")

        # ── 验证登录成功 ───────────────────────────────────
        texts = self.get_all_texts()
        print("  登录后页面文字:", texts[:10])

        # 主页包含模块菜单名，任意一个命中即为成功
        success_keywords = ["Pre-Receive", "Receive", "Put Away", "Consolidation",
                            "Picking", "Restock", "RMA", "Inbound", "Inventory"]
        if any(k in " ".join(texts) for k in success_keywords):
            print(f"✅ 登录成功！当前在主页")
            return True
        else:
            print(f"❌ 登录可能失败，请查看截图: {SCREENSHOT_DIR}\\03_after_login.png")
            return False

    def navigate_to(self, target: str):
        """导航到目标界面"""
        target_map = {
            "consolidation": "Consolidation",
            "load-truck":    "Load Truck",
            "unload-truck":  "Unload Truck",
            "receiving":     "Receiving",
        }
        label = target_map.get(target.lower(), target)
        print(f"\n🧭 导航到: {label}")

        # 先 dump 当前页面所有文字
        texts = self.get_all_texts()
        joined = " ".join(texts)

        # 如果目标不在当前页面，尝试切 tab
        if label not in joined:
            for tab in ["Inbound", "Inventory", "TS/CD", "PS"]:
                btn = self.find_clickable_by_text(tab, timeout=2)
                if btn:
                    btn.click()
                    # 等 tab 切换完成
                    self.wait_for_any_text([label, tab], timeout=3)
                    texts = self.get_all_texts()
                    if label in " ".join(texts):
                        print(f"  在 {tab} tab 下找到 {label}")
                        break

        if target.lower() in ("load-truck", "unload-truck"):
            # 先确保切到包含 Consolidation 的 tab
            texts_now = self.get_all_texts()
            if "Consolidation" not in " ".join(texts_now):
                for tab in ["TS/CD", "PS", "Inbound", "Inventory"]:
                    btn = self.find_clickable_by_text(tab, timeout=2)
                    if btn:
                        btn.click()
                        self.wait_for_any_text(["Consolidation"], timeout=3)
                        if "Consolidation" in " ".join(self.get_all_texts()):
                            break

            # 进 Consolidation（点击后等待 Consolidation 子菜单出现）
            con_btn = self.find_clickable_by_text("Consolidation", timeout=5)
            if con_btn:
                con_btn.click()
                self.wait_for_any_text(["Load Truck", "Unload Truck", "Scan Slot"], timeout=5)
                self.screenshot("04_consolidation")

            # 进目标功能
            btn = self.find_clickable_by_text(label, timeout=5)
            if btn:
                btn.click()
                self.wait_for_any_text(["Truck ID", "Scan to Load", "Scan to Unload"], timeout=5)
                self.screenshot(f"05_{target}")
                print(f"✅ 已进入 {label}")
            else:
                print(f"❌ 未找到 '{label}'，当前文字:", self.get_all_texts()[:8])
        else:
            btn = self.find_clickable_by_text(label, timeout=5)
            if btn:
                btn.click()
                # 等待目标页面出现标志性文字
                self.wait_for_page_change(" ".join(self.get_all_texts()), timeout=4)
                self.screenshot(f"04_{target}")
                print(f"✅ 已进入 {label}")
            else:
                print(f"❌ 未找到 '{label}'，当前文字:", self.get_all_texts()[:8])


def main():
    parser = argparse.ArgumentParser(description="WMS App 自动登录")
    parser.add_argument("--user",      default=DEFAULT_USER,      help="用户名（默认取环境变量 WMS_APP_USER）")
    parser.add_argument("--pwd",       default=DEFAULT_PASSWORD,  help="密码（默认取环境变量 WMS_APP_PASSWORD）")
    parser.add_argument("--warehouse", default=DEFAULT_WAREHOUSE, help="仓库（默认 NJ）")
    parser.add_argument("--target",    default="",     help="登录后导航目标: consolidation, load-truck, unload-truck")
    args = parser.parse_args()

    # 缺少凭证或设备号时直接退出，避免用空账号登录
    if not args.user or not args.pwd:
        print("❌ 缺少账号或密码：请传 --user/--pwd，或设置环境变量 WMS_APP_USER / WMS_APP_PASSWORD")
        sys.exit(1)
    if not DEVICE_UDID:
        print("❌ 缺少设备序列号：请设置环境变量 WMS_DEVICE_UDID（adb devices 显示的 ID）")
        sys.exit(1)

    app = WmsApp()
    app.connect()

    try:
        ok = app.login(args.user, args.pwd, args.warehouse)
        if ok and args.target:
            app.navigate_to(args.target)
    finally:
        # 不 quit，保持 session（方便后续继续操作）
        print("\n🏁 脚本执行完成，App 保持运行")


if __name__ == "__main__":
    main()
