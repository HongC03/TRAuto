"""Start Tales Runner, log in, restart after disconnects, and clear prompts.

This script reuses account/password from autoPWD.txt and image assets in scr/.
It is intended to run on Windows with the same dependencies as autoRace.py.
"""

from pathlib import Path
from statistics import mode
import time

import ddddocr as dd
import keyboard
import numpy as np
from PIL import Image
import pyautogui as gui
import pydirectinput as key
import pygetwindow as gw

from utils import pressButton, triggerIfDetected


BASE_DIR = Path(__file__).resolve().parent
GAME_TITLE = "Tales Runner"
LAUNCHER_TITLE = "跑Online"
TR_PATH = r"C:\Users\Public\Desktop\TalesRunner.lnk"
CHECK_INTERVAL = 1

_ocr = None
gui.useImageNotFoundException(False)

def asset(name):
    return str(BASE_DIR / "scr" / name)


def readCredentials(required=False):
    """Read account and password, requiring them only for auto-start."""
    config_paths = (BASE_DIR / "autoPWD.txt", BASE_DIR / "autoPWD.txt.txt")
    config_path = next((path for path in config_paths if path.is_file()), None)
    if config_path is None:
        if required:
            raise FileNotFoundError("找不到 autoPWD.txt")
        return "", ""

    values = {}
    with config_path.open("r", encoding="utf-8-sig") as config:
        for line in config:
            key_name, separator, value = line.partition("=")
            if separator and key_name.strip() in {"account", "password"}:
                values[key_name.strip()] = value.strip()

    account = values.get("account", "")
    password = values.get("password", "")
    if required and (not account or not password):
        raise ValueError(
            "啟用自動啟動時，autoPWD.txt 中的 account 與 password 皆不可為空"
        )

    if account:
        print(f"* 已讀取帳號: {account}")
    return account, password


def gameWindows():
    return gw.getWindowsWithTitle(GAME_TITLE)


def frontWindow(window):
    """Restore and activate a Tales Runner window."""
    try:
        window.restore()
        window.activate()
    except gw.PyGetWindowException:
        keyboard.send("alt+tab")
        time.sleep(0.5)


def itemExpired():
    if triggerIfDetected(asset("cross.png")):
        print("* 已按下紅叉 *")
        time.sleep(1)
        return True
    return False


def getOcr():
    global _ocr
    if _ocr is None:
        _ocr = dd.DdddOcr(beta=True, show_ad=False)
    return _ocr


def stateYZM(find):
    """Recognize and enter the two-digit verification code."""
    print("")
    key.moveTo(10, 10)

    threshold = 58
    results = []
    verification_region = (
        int(find[0] + 109),
        int(find[1] - 7),
        int(73),
        int(48)
    )
    verification_image = gui.screenshot(region=verification_region)

    for _ in range(5):
        pixels = np.array(verification_image)
        for x in range(verification_image.size[0]):
            for y in range(verification_image.size[1]):
                red, green, blue = (int(value) for value in pixels[y, x])
                if (blue - red > threshold) or (blue - green > threshold):
                    pixels[y, x] = [255, 255, 255]
                else:
                    pixels[y, x] = [0, 0, 0]

        result = getOcr().classification(Image.fromarray(pixels))
        if len(result) == 2:
            result = result.replace("o", "0").replace("O", "0")
            result = result.replace("i", "1").replace("I", "1")
            if result.isdigit():
                results.append(result)
        threshold += 2

    if results:
        digits = mode(results)
        print(f"* 驗證碼辨識結果: {digits} *")
    else:
        digits = "01"
        print("* 驗證碼辨識失敗，輸入 01 以重試 *")

    for digit in digits:
        number_pos = gui.locateOnScreen(asset(f"num{digit}.png"), confidence=0.89)
        if number_pos is not None:
            pressButton(number_pos)
        else:
            key.click()
        key.moveTo(10, 10)
        time.sleep(0.3)

    if results:
        key.press("esc")
    key.moveTo(10, 10)
    print("")


def clearPrompt():
    """Clear prompts and return whether any blocker was handled."""
    handled = False
    verification_pos = gui.locateOnScreen(asset("yzm1.png"), confidence=0.89)
    if verification_pos is not None:
        stateYZM(verification_pos)
        handled = True

    if itemExpired():
        handled = True
    if triggerIfDetected(asset("okButton.png"), action="click"):
        print('* 已發現並按下“確認”鍵 *')
        handled = True
    if triggerIfDetected(asset("denyInvite.png"), action="click"):
        print('* 已發現並按下“取消”鍵 *')
        handled = True
    return handled


def closeGame():
    """Close every open game window before a restart."""
    while True:
        windows = gameWindows()
        if not windows:
            return
        print("* 關閉現有遊戲視窗 *")
        for window in windows:
            frontWindow(window)
            keyboard.send("alt+f4")
            time.sleep(1)
        time.sleep(8)


def launchGame(account, password):
    """Launch Tales Runner through PATH and fill in the login form."""
    while not gameWindows():
        print("* 開啟「執行」並啟動 TalesRunner *")
        keyboard.send("win+r")
        time.sleep(1)
        keyboard.write(TR_PATH, delay=0.05)
        key.press("enter")
        time.sleep(5)

        print("* 按 15 次 Enter 啟動遊戲 *")
        "add function to get TalesRunner in foreground"
        launcher_windows = gw.getWindowsWithTitle(LAUNCHER_TITLE)
        frontWindow(launcher_windows[0])
        for _ in range(15):
            key.press("enter")
            time.sleep(0.5)

        special_case = False
        for _ in range(50):
            if gameWindows():
                break
            special_windows = gw.getWindowsWithTitle(LAUNCHER_TITLE)
            if special_windows:
                special_case = True
                break
            time.sleep(1)

        if special_case:
            print("* 處理畫面縮放導致的啟動器錯誤 *")
            frontWindow(special_windows[0])
            key.press("enter")
            time.sleep(1)
            keyboard.send("win+r")
            time.sleep(1)
            keyboard.write(TR_PATH, delay=0.07)
            key.press("enter")
            time.sleep(20)
            for _ in range(15):
                key.press("enter")
                time.sleep(0.5)
            time.sleep(40)

        if not gameWindows():
            print("** 遊戲啟動失敗，準備重試 **")
            for _ in range(3):
                key.press("enter")
                key.press("esc")
            time.sleep(2)

    window = gameWindows()[0]
    frontWindow(window)
    print("* 輸入帳號與密碼 *")
    keyboard.write(account, delay=0.07)
    key.press("tab")
    keyboard.write(password, delay=0.07)
    key.press("enter")
    time.sleep(1)

    print("* 清除登入後的啟動提示 *")
    for _ in range(30):
        key.press("esc")
        time.sleep(1)

    if 'special_case' in locals() and special_case:
        for _ in range(2):
            keyboard.send("alt+enter")
            time.sleep(2)
    key.moveTo(10, 10)
    print("* Tales Runner 啟動及登入完成 *")


def restartGame(account, password):
    print("\n* 嘗試重新啟動 Tales Runner *")
    closeGame()
    launchGame(account, password)


class GameSupervisor:
    """Own optional game startup, restart detection, and prompt/OCR handling."""

    def __init__(self, account="", password="", auto_start=False):
        if auto_start and (not account or not password):
            raise ValueError(
                "啟用 auto_start 時必須提供 account 與 password"
            )

        self.account = account
        self.password = password
        self.auto_start = auto_start
        key.FAILSAFE = False
        gui.FAILSAFE = False
        key.PAUSE = 0.02

    @classmethod
    def from_config(cls, auto_start=False):
        """Create a supervisor, loading required credentials for auto-start."""
        return cls(
            *readCredentials(required=auto_start),
            auto_start=auto_start,
        )

    def ensure_ready(self):
        """Run one supervision tick and return the resulting game state."""
        windows = gameWindows()
        if not windows:
            if not self.auto_start:
                return "not_running"
            print("** 遊戲視窗已關閉，自動重新啟動 **")
            launchGame(self.account, self.password)
            return "started"

        frontWindow(windows[0])
        if self.auto_start:
            offline_pos = gui.locateOnScreen(
                asset("offline.png"), confidence=0.89
            )
            if offline_pos is not None:
                print("** 偵測到斷線，自動重新啟動 **")
                restartGame(self.account, self.password)
                return "restarted"

        clearPrompt()
        return "ready"

    def run_forever(self, interval=CHECK_INTERVAL):
        """Continuously supervise the game until the process is interrupted."""
        if self.auto_start:
            feature_description = "自動啟動/重新啟動及提示清理"
        else:
            feature_description = "提示清理"
        print(f"* {feature_description}已啟用；按 Ctrl+C 停止 *")
        while True:
            self.ensure_ready()
            time.sleep(interval)


def main():
    GameSupervisor.from_config(auto_start=True).run_forever()


if __name__ == "__main__":
    try:
        main()
    except gui.ImageNotFoundException:
        pass
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* 程式已停止 *")
