
import time
import pyautogui as gui
import pydirectinput as key
import keyboard
import global_hotkeys
import pygetwindow as gw
# import wmi
from hashlib import blake2b
from multiprocessing import Process, freeze_support
from playsound import playsound

def welcomeSequence():
    # eTime = expirationDate()
    print("\n***************************************************")
    print("* Welcome using Tales Runner fishing script!")
    print("***************************************************\n")
    return

def getGameWindows(title="Tales Runner"):
# Return all game windows whose title contains the requested text
    return gw.getWindowsWithTitle(title)

def getGameWindow():
# Return the first Tales Runner window, or None when the game is not running
    trList = getGameWindows()
    return trList[0] if len(trList) != 0 else None

def getWindowRegion(win32Window):
# Convert a PyGetWindow object to the region tuple expected by PyAutoGUI
    return (win32Window.left, win32Window.top, win32Window.width, win32Window.height)

def frontWindow(win32Window):
# Restore and bring a PyGetWindow Win32Window object to the foreground
    try:
        win32Window.restore()
        win32Window.activate()
    except gw.PyGetWindowException:
        keyboard.send("alt+tab")
        time.sleep(0.2)
        win32Window.activate()
    return

def closeGameWindows():
# Close every Tales Runner window using the same Alt+F4 method as the run script
    trList = getGameWindows()
    while len(trList) != 0:
        frontWindow(trList[0])
        keyboard.send("alt+f4")
        time.sleep(2)
        trList = getGameWindows()
    return

def pauseFlagFlip():
# The function that flips the pauseFlag
    global pauseFlag
    pauseFlag = not pauseFlag
    if pauseFlag:
        playsound('./scr/pauseOn.mp3')
    else:
        playsound('./scr/pauseOff.mp3')
    return

def accessDeny():
# Basically an infinite loop to prevent access
    while True:
        time.sleep(1E6)

def restartSequence(enableRestart, infoList):
# This function is a sequence to restart the game
    name = infoList[0]
    pwd  = infoList[1]

    trList = getGameWindows()
    if len(trList) != 0:
        print("\n* 嘗試重新啟動遊戲")
        while len(trList) != 0:
            frontWindow(trList[0])
            keyboard.send("alt+f4")
            time.sleep(9)
            trList = getGameWindows()
    else:
        print("\n* 嘗試啟動遊戲")
        time.sleep(1)

    while enableRestart and len(trList) == 0:
        # win+r
        print("* 開啟「執行」")
        keyboard.send('win+r')
        time.sleep(1)

        # Type "talesrunner"
        print("* 輸入 talesrunner 並按 Enter")
        keyboard.write("talesrunner", delay=0.05)
        key.press('enter')
        print("* 等待20秒")
        time.sleep(20)

        # Press "enter" to start game
        print("* 按 20 次 Enter")
        for _ in range(20):
            key.press('enter')
            time.sleep(0.5)

        specialCase = False
        print("* 等待50秒")
        for _ in range(50):
            time.sleep(1)
            specialWindowList = getGameWindows("TalesRunner")
            if len(specialWindowList) != 0:
                specialCase = True
                break

        if specialCase: # error caused by zoom-in
            print("* 解析度縮放導致的特定錯誤，重新執行上述步驟")
            frontWindow(specialWindowList[0])
            key.press('enter')
            time.sleep(1)
            keyboard.send('win+r')
            time.sleep(1)

            keyboard.write("talesrunner", delay=0.07)
            key.press('enter')
            print("* 等待20秒")
            time.sleep(20)

            print("* 按 20 次 Enter")
            for _ in range(20):
                key.press('enter')
                time.sleep(0.5)

            print("* 等待50秒")
            time.sleep(50)

        trList = getGameWindows()
        if len(trList) != 0: # game is launched
            frontWindow(trList[0])

            # Enter account info
            print("* 輸入帳號資訊並按 Enter")
            keyboard.write(name, delay=0.07)
            key.press('tab')
            time.sleep(0.7)
            keyboard.write(pwd, delay=0.07)
            time.sleep(0.7)
            key.press('enter')
            time.sleep(1)

            # Hit esc for 30 times
            print("* 按 30 次 Esc（每秒一次）")
            for _ in range(30):
                key.press('esc')
                time.sleep(1)

            if specialCase:
                for _ in range(2):
                    keyboard.send("alt+enter")
                    time.sleep(2)

            key.moveTo(10, 10)
        else:
            print("** 遊戲啟動失敗，嘗試重新啟動")
            for _ in range(3):
                key.press('enter')
                key.press('esc')
                time.sleep(0.1)

    if not enableRestart:
        print("** 未啟用重新啟動功能，關閉遊戲並停止運作 **")
        accessDeny()
    else:
        print("\n* 重新啟動 Tales Runner 的步驟已執行完畢 *\n")
        trWin = getGameWindow()
        if trWin is not None:
            frontWindow(trWin)
        key.moveTo(100, 100)
        toFishSequence(infoList[2])
        time.sleep(3)
    return

def toFishSequence(keyConfig):
# Try to go back to fishing position
    up      = keyConfig[0]
    down    = keyConfig[1]
    left    = keyConfig[2]
    right   = keyConfig[3]
    # z       = keyConfig[4]
    # x       = keyConfig[5]
    # c       = keyConfig[6]
    # a       = keyConfig[7]
    # d       = keyConfig[8]

    print("\n* 嘗試重回農場")
    trWin = getGameWindow()
    topButtonPos = gui.locateCenterOnScreen("scr/topButton.png", confidence=0.89)  # 圖片：藍底白字的「公園」頁籤。
    
    if topButtonPos != None:
        key.click(topButtonPos[0]+88, topButtonPos[1])
        time.sleep(1)
        key.press('enter')
        time.sleep(3)
        farmPos = gui.locateCenterOnScreen("scr/fish/myFarm.png", confidence=0.89)  # 圖片：綠底白字的「進入我的農場」按鈕。
        if farmPos != None: # go to my farm
            key.click(farmPos[0], farmPos[1])
            time.sleep(15)
            
            while True:
                if trWin == None:
                    print("** 你在搞毛啊, 遊戲呢? **")
                    break
                windowRegion = getWindowRegion(trWin)

                print("* 蠕行至陰暗的角落")
                for _ in range(75):
                    key.keyDown(up)
                    time.sleep(0.07)
                    key.keyUp(up)
                    time.sleep(0.07)

                for _ in range(5):
                    key.keyDown(left)
                    time.sleep(0.07)
                    key.keyUp(left)
                    time.sleep(0.07)

                print("* 走向釣魚點")
                key.keyDown(down)
                key.keyDown(right)
                time.sleep(1.38)
                key.keyUp(down)
                key.keyUp(right)

                time.sleep(10)
                print("* 等待10秒")
                readyPos = gui.locateCenterOnScreen('scr/fish/fishReady.png', confidence=0.89)  # 圖片：可用狀態的藍底白字「準備釣魚」按鈕。
                readyNPos = gui.locateCenterOnScreen('scr/fish/fishReadyN.png', confidence=0.89)  # 圖片：不可用狀態的灰底白字「準備釣魚」按鈕。

                if readyNPos != None:
                    print("** 未到達釣魚點, 打開農場商店重試")
                    shop = gui.locateCenterOnScreen('scr/fish/farmShop.png', confidence=0.89)  # 圖片：橙色的農場商店購物車圖示。
                    if shop != None:
                        key.click(shop[0], shop[1])
                        time.sleep(1)
                        crossPos = gui.locateOnScreen('scr/cross.png', confidence=0.89)  # 圖片：紅底白色叉號的關閉按鈕。
                        key.click(crossPos[0], crossPos[1])
                        time.sleep(5)
                elif readyPos != None:
                    print("* 成功走至釣魚點")
                    key.click(readyPos[0], readyPos[1])
                    print("* 移動畫面, 準備釣魚")
                    key.moveTo(windowRegion[0]+400, windowRegion[1]+400)
                    key.dragRel(800, 0, duration=0.5, button='left')
                    time.sleep(5)
                    break
                else:
                    print("** 不該這樣的啊, 釣魚按鈕呢? 重啟遊戲吧")
                    closeGameWindows()
                    break
        else:
            print("** 不該這樣的啊, 我的農場按鈕呢? 重啟遊戲吧")
            closeGameWindows()
    else:
        print("** 不該這樣的啊, 農場按鈕呢? 重啟遊戲吧")
        closeGameWindows()

def fishYZM(fishBag_fPos):
# Teleport fish by solving vf fish code
    print("\n* 正在將魚傳送至背包")

    # Click fishBag
    mousePos = gui.center(fishBag_fPos)
    key.click(mousePos[0], mousePos[1])
    time.sleep(3)

    # Click teleport fish
    telePos = gui.locateOnScreen('scr/fish/teleport.png', confidence=0.89)  # 圖片：綠色的「傳送到我的房間」文字。
    clickCount = 0

    while(telePos != None):
        mousePos = gui.center(telePos)
        key.click(mousePos[0], mousePos[1])

        time.sleep(1)
        clickCount = 0
        fishArr = [] # fishArr -> [(x-axis, fishName)]
        for s in "0123456789":
            fishShadow = gui.locateOnScreen('scr/fish/fish'+s+'_b.png', confidence=0.89)  # 圖片模板：魚類編號 0 至 9 的黑色驗證碼剪影。
            if fishShadow != None:
                fishArr.append((fishShadow[0], s))
                clickCount += 1
                if clickCount == 2:
                    break
        if clickCount == 2:
            if fishArr[0][0] > fishArr[1][0]: # Find the order, fishArr -> [fishName]
                fishArr = [fishArr[1][1], fishArr[0][1]]
            else:
                fishArr = [fishArr[0][1], fishArr[1][1]]
            for s in fishArr:
                fishPos = gui.locateOnScreen('scr/fish/fish'+s+'_f.png', confidence=0.89)  # 圖片模板：魚類編號 0 至 9 的彩色可選魚圖示。
                if fishPos != None:
                    mousePos = gui.center(fishPos)
                    key.click(mousePos[0], mousePos[1])
                time.sleep(1)
        telePos = gui.locateOnScreen('scr/fish/teleport.png', confidence=0.89)  # 圖片：綠色的「傳送到我的房間」文字。
    return clickCount

def pressButton(buttonPos):
# Press the buttonPos button
    mousePos = gui.center(buttonPos)
    key.click(mousePos[0], mousePos[1])
    # time.sleep(1)
    return

def startFish(startFishPos):
# Try to start fishing
    if (startFishPos == None):
        print("** 異常情況(startFishPos == None) **")
        for _ in range(5):
            key.press('esc')
        # break
    else:
        print("* 開始釣魚 *\n")
        mousePos = gui.center(startFishPos)
        key.click(mousePos[0], mousePos[1])
        time.sleep(1)
    return

def teleportFish(fishBag_fPos):
# Try to teleport fish
    global teleCount
    if fishYZM(fishBag_fPos) != 2: # Less than 2 fish recognized
        print("\n** 魚驗證碼識別失敗 **\n")
        for _ in range(3):
            key.press('esc')
    else:
        teleCount += 1
        print("* 已成功將魚傳送至背包\n* 傳送次數:", teleCount)
    time.sleep(3)
    return

def changeBait(changeBaitPos):
    # Auto change bait
    print("* 魚餌已用完\n* 嘗試更換魚餌")
    mousePos = gui.center(changeBaitPos)
    key.click(mousePos[0], mousePos[1])
    time.sleep(6)

    useBaitPos = gui.locateOnScreen('scr/fish/useBait.png', confidence=0.89)  # 圖片：綠底白字的「使用」魚餌按鈕。
    if useBaitPos == None: # No available bait in bag
        print("\n** 已無可用魚餌 **\n")
        key.press('esc')
        accessDeny()
        # time.sleep(6)
        # buyBaitPos = gui.locateOnScreen('scr/fish/baitBuy.png', confidence=0.89)  # 圖片：綠色的「購買魚餌」文字。
        # buyBait(buyBaitPos)
    else:
        usingBatePos = None
        while usingBatePos == None:
            mousePos = gui.center(useBaitPos)
            key.click(mousePos[0], mousePos[1])
            usingBatePos = gui.locateOnScreen('scr/fish/usingBait.png', confidence=0.89)  # 圖片：粉紅底白字的「使用中」魚餌狀態按鈕。
            time.sleep(6)
        print("* 更換魚餌成功")

    # final keyboard sequence
    key.press('esc')
    time.sleep(6)
    key.press('esc')
    time.sleep(6)
    return

def clearPrompt(windowRegion):
# Try to clear all the prompts in game
    changeBaitPos   = gui.locateOnScreen('scr/fish/baitBag.png', confidence=0.89, region=windowRegion)  # 圖片：藍底白字的「持有魚餌」頁籤。
    crossPos        = gui.locateOnScreen('scr/cross.png', confidence=0.89, region=windowRegion)  # 圖片：紅底白色叉號的關閉按鈕。
    okButtonPos     = gui.locateOnScreen('scr/okButton.png', confidence=0.89, region=windowRegion)  # 圖片：藍底白字的「確認」按鈕。
    denyPos         = gui.locateOnScreen('scr/denyInvite.png',confidence=0.89, region=windowRegion)  # 圖片：粉紅底白字的「取消」按鈕。
    
    if (okButtonPos != None):
    # Check if there is an OK button
        pressButton(buttonPos=okButtonPos)
        print("\n* 已發現並按下“確認”鍵 *\n")

    elif (denyPos != None):
    # Check if there is a deny button
        pressButton(buttonPos=denyPos)
        print("\n* 已發現並按下“取消”鍵 *\n")

    elif (crossPos != None):
    # Check if item expired
        pressButton(buttonPos=crossPos)
        print("\n* 已發現並按下“紅叉” *\n")
    
    elif changeBaitPos != None:
        time.sleep(10)
        key.press('enter')
        time.sleep(0.5)
        changeBait(changeBaitPos)

    return

def gameAreaDetect():
    print("* 重新搜尋讀圖區域中...")
    time0 = time.time()
    showTime = True
    while True:
        trWin = None
        while trWin is None:
            time.sleep(1)
            trWin = getGameWindow()
        windowRegion = getWindowRegion(trWin)
        startFishPos    = gui.locateOnScreen('scr/fish/startFish.png', confidence=0.89, region=windowRegion)  # 圖片：綠底黃字的「開始釣魚」按鈕。
        startFishEndPos = gui.locateOnScreen('scr/fish/startFishEnd.png', confidence=0.89, region=windowRegion)  # 圖片：粉紅底黃字的「取消釣魚」按鈕。

        if startFishEndPos is not None:
            locateArrowRegion = (startFishEndPos[0] - 244, startFishEndPos[1] - 61, 320, 48)
            locateDTypeRegion = (startFishEndPos[0] - 274, startFishEndPos[1] - 115+97, 350, 175-97)
            locateMovingRegion = (startFishEndPos[0] - 285, startFishEndPos[1] - 115, 361, 66)
            print("* 已獲得搜尋區域\n")
            break
        elif startFishPos is not None:
            locateArrowRegion = (startFishPos[0] - 241, startFishPos[1] - 59, 320, 48)
            locateDTypeRegion = (startFishPos[0] - 271, startFishPos[1] - 113+99, 350, 175-97)
            locateMovingRegion = (startFishPos[0] - 282, startFishPos[1] - 113, 361, 66)
            print("* 已獲得搜尋區域\n")
            break
        elif time.time() - time0 > 30 and showTime:
            print("\n** 超過30秒未識別到讀圖區域 **\n")
            showTime = False

    return (windowRegion, locateArrowRegion, locateDTypeRegion, locateMovingRegion)

def gameModeDetect():
# Detect if in game mode, constantly
    totalFish = 0
    dxPosList = [0]*3
    dIndexList = [0]*3
    windowRegion = None

    while True:
        trWin = getGameWindow()
        if trWin != None:
            checkRegion = getWindowRegion(trWin)
            if checkRegion != windowRegion:
                windowRegion, locateArrowRegion, locateDTypeRegion, locateMovingRegion = gameAreaDetect()

            dCount = 0
            check = time.time() # check tracking time

            for i in range(4): # tracking DType figs
                temp = gui.locateOnScreen('scr/fish/dType'+str(i)+'.png', region=locateDTypeRegion, confidence=0.8)  # 圖片模板：藍白色魚鉤道具、黃色魚、紅白色蚯蚓及紅白色魚鉤（類型 0 至 3）。
                if temp != None:
                    dxPosList[dCount] = temp[0]
                    dIndexList[dCount] = i
                    dCount = dCount + 1

            if dCount == 3: # found 3 DTypes, enter special mode
                print("* 分析遊戲模式耗時: %.4f秒" % (time.time() - check))
                print("* 進入小遊戲模式\n* 分析按鍵位置")

                i = 0  # for i in range(4)
                time0 = time.time() # time counter 1
                while True: # locate the moving DType's position (1/2/3)
                    temp = gui.locateOnScreen('scr/fish/dType'+str(dIndexList[i])+'.png', region=locateMovingRegion, confidence=0.3)  # 圖片模板：移動中的藍白色魚鉤道具、黃色魚、紅白色蚯蚓或紅白色魚鉤。
                    if temp != None: # found
                        if dxPosList[i] == max(dxPosList): # right-most position
                            targetKey = '3'
                        elif dxPosList[i] == min(dxPosList): # left-most position
                            targetKey = '1'
                        else: # mid position
                            targetKey = '2'
                        print("* 目標位於: 第" + targetKey + "位")
                        print("* 分析目標耗時: %.4f秒" % (time.time() - time0))
                        ##################################################################
                        print("* 跟蹤指針")
                        while True: # tracking the yellow-in-green arrow
                            time1 = time.time() # time counter 2
                            # arrowB = gui.locateOnScreen('scr/fish/arrowB2.png', region=locateArrowRegion, confidence=0.8)  # 圖片：黃色三角指針位於藍色目標區域。
                            arrowG = gui.locateOnScreen('scr/fish/arrowG.png', region=locateArrowRegion, confidence=0.65)  # 圖片：黃色三角指針位於綠色成功區域。
                            
                            # if arrowB == None:
                            if arrowG != None: # found the arrow
                                print("* 本次抓取總耗時: %.4f秒" % (time.time() - check))
                                key.press(targetKey)
                                totalFish = totalFish + 1
                                print("* 釣魚遊戲完成" + str(totalFish) + "次\n")
                                time.sleep(1)
                                break
                            elif time.time() - time1 > 30:
                                print("\n** 過長時間未跟蹤到指針, 放棄跟蹤 **\n")
                                break
                        break
                    elif time.time() - time0 > 30:
                        print("\n** 分析失敗時間過長, 放棄本次分析 **\n")
                        break
                    else:
                        i = (0 if i==2 else i+1)
    return

def doctorLoop(infoList):
    if True: # just so I can collapse these initialization
        # Hotkey initialization
        global pauseFlag # Global pause flag, True = Pause program
        # pauseFlag = False
        global_hotkeys.register_hotkey("control + f12", pauseFlagFlip, None, False, None)
        global_hotkeys.start_checking_hotkeys()

        # Read user account info from the infoList
        usrName = infoList[0]
        usrPwd  = infoList[1]
        if usrName != '-1' and usrPwd != '-1':
            print("\n** 已啟用自動重啟功能\n** 請確保遊戲目錄已添加至環境變數的PATH中")
            print("** 帳號: " + usrName)
            print("** 密碼: " + usrPwd)
            print("** 若輸入錯誤請關閉本程式並修改設定檔")
            enableRestart = True
            
        else:
            print("\n** 未識別到有效使用者名稱&密碼輸入, 停用重啟功能 **\n")
            enableRestart = False

    failTime = 0
    while True:
        if pauseFlag:
            print("\n** 暫停中, 再次按下 ctrl + f12 解除暫停 **")
            while pauseFlag:
                time.sleep(0.1)
            print("** 暫停已解除 **\n")
            continue

        trWin = getGameWindow()
        if trWin != None:
            frontWindow(trWin)
            windowRegion = getWindowRegion(trWin)
        else:
            restartSequence(enableRestart, infoList)
            continue

        # clearPrompt(windowRegion)
        fishBag_bPos    = gui.locateOnScreen('scr/fish/fishBag_b.png', confidence=0.89, region=windowRegion)  # 圖片：不可用狀態的灰色「漁網確認」文字。
        fishBag_fPos    = gui.locateOnScreen('scr/fish/fishBag_f.png', confidence=0.89, region=windowRegion)  # 圖片：可用狀態的橙色「漁網確認」文字。
        startFishPos    = gui.locateOnScreen('scr/fish/startFish.png', confidence=0.89, region=windowRegion)  # 圖片：綠底黃字的「開始釣魚」按鈕。

        if fishBag_bPos == None:
            if fishBag_fPos == None: # special case when fishBag icon disappears
                failTime += 1
                if failTime == 10: # cannot locate any icon, recapture window position
                    print("\n** 超過10秒未檢測到關鍵圖案 **")

                elif failTime >= 30:
                    print("** 超過30秒未檢測到關鍵圖案 **\n")
                    restartSequence(enableRestart, infoList)
                    failTime = 0
                else:
                    offline = gui.locateOnScreen('scr/offline.png', confidence=0.89, region=windowRegion)  # 圖片：綠白色韓文「全年齡」分級標誌，用作掉線畫面的識別標記。
                    if offline != None:
                        print("\n** 檢測到已斷線 **")
                        restartSequence(enableRestart, infoList)
                        failTime = 0
            else:
                failTime = 0
                if startFishPos != None:
                    teleportFish(fishBag_fPos)
                
        else:
            failTime = 0
            if startFishPos != None:
                startFish(startFishPos)
        time.sleep(1)
        clearPrompt(windowRegion)
    return

def validKey(keyName:str):
# PyDirectInput accepts keys listed in KEYBOARD_MAPPING
    return keyName.lower() in key.KEYBOARD_MAPPING

def init():
# Program initialization:
# 1) check autoPWD
# 2) verify user's cdkey
# 3) return user's customized keyboard config and map selection
    try:
        print("* 嘗試尋找並打開 autoPWD.txt")
        file = open("autoPWD.txt", 'r')
        print("* 成功打開 autoPWD.txt")
        
    except FileNotFoundError:
        try:
            file = open("autoPWD.txt.txt", 'r')
            print("* 成功打開 autoPWD.txt.txt")
            
        except FileNotFoundError:
            print("\n** 未找到 autoPWD.txt **\n")
            accessDeny()

    userInput = file.read().splitlines()
    
    # default values
    usrName     = '-1'
    usrPWD      = '-1'
    forward     = 'up'
    backward    = 'down'
    leftward    = 'left'
    rightward   = 'right'
    jump        = 'ctrl'
    item        = 'shift'
    item2       = 'a'
    item3       = 's'
    sprint      = 'z'
    runtime     = '21600'

    for s in userInput: # read various configuration
        # usrName (user's account)
        if s.find("account") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "") # trim spaces
                if len(temp) != 0:
                    print("* 已讀取使用者名稱\t: " + temp)
                    usrName = temp
                else:
                    continue
            except IndexError:
                continue

        # usrPWD (user's password)
        elif s.find("password") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "") # trim spaces
                if len(temp) != 0:
                    print("* 已讀取密碼\t: " + temp)
                    usrPWD = temp
                else:
                    continue
            except IndexError:
                continue

        # control - forward
        elif s.find("forward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取前進鍵\t: " + temp)
                    forward = temp
                else:
                    print("** 無效的前進鍵設置, 使用預設鍵位: " + forward)
            except IndexError:
                continue

        # control - backward
        elif s.find("backward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取後退鍵\t: " + temp)
                    backward = temp
                else:
                    print("** 無效的後退鍵設置, 使用預設鍵位: " + backward)
            except IndexError:
                continue

        # control - leftward
        elif s.find("leftward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取左轉鍵\t: " + temp)
                    leftward = temp
                else:
                    print("** 無效的左轉鍵設置, 使用預設鍵位: " + leftward)
            except IndexError:
                continue

        # control - rightward
        elif s.find("rightward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取右轉鍵\t: " + temp)
                    rightward = temp
                else:
                    print("** 無效的右轉鍵設置, 使用預設鍵位: " + rightward)
            except IndexError:
                continue

        # control - jump
        elif s.find("jump") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取跳躍鍵\t: " + temp)
                    jump = temp
                else:
                    print("** 無效的跳躍鍵設置, 使用預設鍵位: " + jump)
            except IndexError:
                continue

        elif s.find("item2") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取道具鍵2\t: " + temp)
                    item2 = temp
                else:
                    print("** 無效的道具鍵2設置, 使用預設鍵位: " + item2)
            except IndexError:
                continue

        elif s.find("item3") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取道具鍵3\t: " + temp)
                    item3 = temp
                else:
                    print("** 無效的道具鍵3設置, 使用預設鍵位: " + item3)
            except IndexError:
                continue

        # control - item
        elif s.find("item") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取道具鍵\t: " + temp)
                    item = temp
                else:
                    print("** 無效的道具鍵設置, 使用預設鍵位: " + item)
            except IndexError:
                continue

        # control - sprint
        elif s.find("sprint") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if validKey(temp):
                    print("* 已讀取衝刺鍵\t: " + temp)
                    sprint = temp
                else:
                    print("** 無效的衝刺鍵設置, 使用預設鍵位: " + sprint)
            except IndexError:
                continue

    control = [forward, backward, leftward, rightward, jump, item, sprint, item2, item3]
    return [usrName, usrPWD, control, runtime]

def main():
    if __name__ == '__main__':
        freeze_support()
        key.FAILSAFE = False
        gui.FAILSAFE = False
        key.PAUSE = 0.02
        welcomeSequence() # welcome
        infoList = init() # read txt file
        global teleCount # initialize fish teleport count
        teleCount = 0

        procClear = Process(target=gameModeDetect)  # instantiating clear prompt process
        procClear.start()

        doctorLoop(infoList)

pauseFlag = False # Global pause flag, True = Pause program
main()

