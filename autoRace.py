
import ddddocr as dd
import time
import pyautogui as gui
import pydirectinput as key
import keyboard
import global_hotkeys
# import pywintypes
# import wmi
import pygetwindow as gw
import numpy as np

# from hashlib import blake2b
from PIL import Image
from playsound import playsound
from statistics import mode

def welcomeSequence():
    # eTime = expirationDate()
    print("\n***************************************************")
    # print("* 此電腦已註冊，歡迎使用本程式")
    print("* 歡迎使用跑Online跑圖腳本!")
    print("* 請注意，這是一個*免費*軟體")
    print("* 如果你付費了，不僅你受騙了，作者也沒有收到任何收益")
    print("* 請確保您已閱讀使用說明")
    print("* 作者：文 (版本: 20240306v1)")
    print("***************************************************\n")
    return

def selectMap():
# (Re)Select map
    print("* 選擇地圖中 *")
    time.sleep(1)
    mousePos = None # click 'select map'
    while mousePos == None:
        mousePos = gui.locateCenterOnScreen('./scr/selectMap.png', confidence=0.89)
    if mousePos != None:
        if pauseFlag:
            print("* 啟用暫停, 取消選擇地圖 *")
            return
        key.click(mousePos[0], mousePos[1])
    else:
        print("* 選擇地圖失敗(selectMap == None) *")
        return

    time.sleep(1) # Click "train"
    selectMapDonePos = gui.locateCenterOnScreen('./scr/selectMapDone.png', confidence=0.89)
    if selectMapDonePos != None:
        if pauseFlag:
            print("* 啟用暫停, 取消選擇地圖 *")
            return
        key.click(selectMapDonePos[0]-392, selectMapDonePos[1]-582) # click "servive"
        key.click(selectMapDonePos[0]-512, selectMapDonePos[1]-582) # click "train"
    else:
        print("* 選擇地圖失敗(selectMapDone == None) *")
        return
    
    mousePos = None
    pressCount = 0
    while (mousePos == None and pressCount < 20):
        if pauseFlag:
            print("* 啟用暫停, 取消選擇地圖 *")
            return
        key.press('down')
        mousePos = gui.locateCenterOnScreen('./scr/selectMapRun1.png', confidence=0.89)
    if pressCount == 20:
        print("* 選擇地圖失敗(pressCount == 20) *")
        return
    else:
        if pauseFlag:
            print("* 啟用暫停, 取消選擇地圖 *")
            return
        key.click(mousePos[0], mousePos[1])
    
    time.sleep(1) # Click "select this map"
    if pauseFlag:
        print("* 啟用暫停, 取消選擇地圖 *")
        return
    key.click(selectMapDonePos[0], selectMapDonePos[1])
    
    print("* 選擇超速隧道地圖成功 *")
    time.sleep(1)

def correctMap():
# Check if current map is the desired map
# not implemented
    # result = False
    # for _ in range(8):
    #     currMapPos = gui.locateOnScreen('./scr/currMap.png', confidence=0.89)
    #     if (currMapPos != None):
    #         result = True
    #         break
    #     time.sleep(0.7)
    
    # return result
    return True

def stateLobby(lobbyPos):
# In game lobby, create a new room

    yzmPos = gui.locateOnScreen('./scr/yzm1.png',confidence=0.89)

    if (yzmPos != None):
    # Check if asked to enter vf code (YZM)
        stateYZM(find=yzmPos)
        return

    print("* 遊戲大廳中 *\n* 嘗試自行建立房間 *")
    mousePos = gui.center(lobbyPos)
    if pauseFlag:
        print("* 啟用暫停, 取消建立房間 *")
        return
    key.click(mousePos[0]-100, mousePos[1]) # Click "lobby" just in case

    time.sleep(1)
    if pauseFlag:
        print("* 啟用暫停, 取消建立房間 *")
        return
    key.click(mousePos[0]-80, mousePos[1]+60) # Click "free channel" just in case

    time.sleep(1) # Click "create room"
    mousePos = gui.locateCenterOnScreen('./scr/createRoom.png', confidence=0.89)
    if mousePos != None:
        if pauseFlag:
            print("* 啟用暫停, 取消建立房間 *")
            return
        key.click(mousePos[0], mousePos[1])
    else:
        print("* 建立房間失敗(createRoom == None) *")
        return

    time.sleep(1) # Uncheck "power-up items"
    mousePos = gui.locateCenterOnScreen('./scr/createRoomOption.png', confidence=0.89)
    if mousePos != None:
        if pauseFlag:
            print("* 啟用暫停, 取消建立房間 *")
            return
        key.click(mousePos[0]-35, mousePos[1])
    else:
        print("* 建立房間失敗(createRoomOption == None) *")
        return
    
    time.sleep(1) # Click "create room complete"
    mousePos = gui.locateCenterOnScreen('./scr/createRoomDone.png', confidence=0.89)
    if mousePos != None:
        if pauseFlag:
            print("* 啟用暫停, 取消建立房間 *")
            return
        key.click(mousePos[0], mousePos[1])
    else:
        print("* 建立房間失敗(createRoomDone == None) *")
        return

    print("* 建立房間成功 *")
    time.sleep(1)
    clearPrompt()
    selectMap()
    # print("* 创建极速拼图房间成功 *")
    return

def clearPrompt():
# Try to clear all the prompts in game
    crossPos    = gui.locateOnScreen('./scr/cross.png', confidence=0.89)
    okButtonPos = gui.locateOnScreen('./scr/okButton.png', confidence=0.89)
    denyPos     = gui.locateOnScreen('./scr/denyInvite.png',confidence=0.89)
    yzmPos      = gui.locateOnScreen('./scr/yzm1.png',confidence=0.89)

    if (yzmPos != None):
    # Check if asked to enter vf code (YZM)
        stateYZM(find=yzmPos)

    if (crossPos != None):
    # Check if item expired
        itemExpired()

    if (okButtonPos != None):
    # Check if there is an OK button
        pressButton(buttonPos=okButtonPos)
        print("\n* 已發現並按下“確認”鍵 *\n")

    if (denyPos != None):
    # Check if there is a deny button
        pressButton(buttonPos=denyPos)
        print("\n* 已發現並按下“取消”鍵 *\n")

    return

def quitRoom():
# Try to quit a room
    print("* 嘗試離開房間 *")
    backPos = gui.locateOnScreen('./scr/back.png',confidence=0.89)
    while backPos == None:
        backPos = gui.locateOnScreen('./scr/back.png',confidence=0.89)
    while backPos != None:
        # time.sleep(10)
        pressButton(buttonPos=backPos)
        time.sleep(1)
        clearPrompt()
        backPos = gui.locateOnScreen('./scr/back.png',confidence=0.89)
    print("* 已離開房間 *")
    return

def stateRacing(keyConfig):
# Racing (uses keyConfig to customize keys)
    global pauseFlag # global pause flag
    up      = keyConfig[0]
    down    = keyConfig[1]
    left    = keyConfig[2]
    right   = keyConfig[3]
    z       = keyConfig[4]
    x       = keyConfig[5]
    c       = keyConfig[6]
    a       = keyConfig[7]
    d       = keyConfig[8]

    print("* 開始跑圖 *")
    raceTime0 = time.time()

    raceImage = './scr/racing.png' # default racing image
    raceImageAlt = './scr/racing1.png' # default alternative racing image

    searchEnd = True
    changePos = True # for tunnel

    while not pauseFlag: # Keyboard sequence for racing
        key.keyDown(up)
        for _ in range(30):
            key.press(z)

        elapsedTime = time.time() - raceTime0

        if elapsedTime > 61 and changePos: # for tunnel
            key.keyDown(right)
            time.sleep(0.2)
            key.keyUp(right)
            key.keyDown(c) # sprint at the end
            changePos = False

        if elapsedTime > 120 and searchEnd:
            key.keyUp(c) # release sprint
            key.keyUp(up)
            print("* 跑圖時間異常，嘗試尋找終點 *")
            key.keyDown(down)
            time.sleep(2.2)
            key.keyUp(down)
            key.keyDown(right)
            time.sleep(4)
            key.keyUp(right)
            key.keyDown(left)
            time.sleep(4)
            key.keyUp(left)
            searchEnd = False

        if elapsedTime > 1200:
            print("** 跑圖已超過 20 分鐘，判定為死局，強制關閉遊戲 **")
            key.keyDown('alt')
            key.keyDown('f4')
            key.keyUp('alt')
            key.keyUp('f4')
            # accessDeny()

        find = gui.locateOnScreen(raceImage,confidence=0.89)
        if find == None: # Do not go out if still in a race
            find = gui.locateOnScreen(raceImageAlt,confidence=0.89)
            if find == None:
                key.keyUp(up)
                break
            else:
                tempStr = raceImage
                raceImage = raceImageAlt
                raceImageAlt = tempStr
    
    key.keyUp(c)
    return

def stateYZM(find):
# Process verification code (vf code = YZM)
    # ocr = dd.DdddOcr(beta=True, show_ad=False)

    print("")
    key.moveTo(10, 10) # Move the mouse out of the way

    binPram = 58   # Initial binarization threshold
    binInc = 2     # Threshold increment
    retry = 5      # Amount of retries 

    mousePos = None # mousePos initialization
    resultList = []
    
    vfPos = (find[0]+109, find[1]-7, 73, 48) # Screenshot region
    vfImg = gui.screenshot(region=vfPos) # Screenshot the vf code (this is PIL img)

    for _ in range(retry): # run "retry" amount of times to increase robustness
        ima = np.array(vfImg) # convert the PIL img to np array
        for i in range(vfImg.size[0]): # binarization based on blue pixels
            for j in range(vfImg.size[1]):
                (red, green, blue) = ima[j, i]
                if (blue - red > binPram) or (blue - green > binPram):
                    ima[j, i] = [255,255,255] # too blue, make it white
                else:
                    ima[j, i] = [0,0,0] # else, make it black
        yzmOut = Image.fromarray(ima) # array back to PIL img
        res = ocr.classification(yzmOut) # ocr
        if len(res) == 2: # The length of the result has to be 2
            resCheck = ""
            for s in res: # Manually adjust results for some cases
                if s == "o" or s == "O":
                    resCheck += "0"
                elif s == "i" or s == "I":
                    resCheck += "1"
                else:
                    resCheck += s
            if resCheck.isdigit(): # Result has to be digit-only
                resultList.append(resCheck) # Append it to the result list
        binPram += binInc # Increase the threshold for binarization
        
    if len(resultList) == 0: # Empty list means Vf code detection failed
        print("* 驗證碼辨識失敗，輸入 01 以重試 *") # Input 01 and retry
        for s in "01":
            numPos = gui.locateOnScreen('./scr/num'+s+'.png', confidence=0.89)
            if numPos != None:
                mousePos = gui.center(numPos)
                key.click(mousePos[0], mousePos[1])
            else:
                key.click()
            time.sleep(0.3)

    else: # Vf code detection succeeded
        result = mode(resultList)
        print("* 驗證碼辨識結果: " + result + " *")
        for s in result:
            numPos = gui.locateOnScreen('./scr/num'+s+'.png', confidence=0.89)
            if numPos != None: # Check if the result has two different digits
                mousePos = gui.center(numPos)
                key.click(mousePos[0], mousePos[1])
                key.moveTo(10, 10) # move the mouse out of the way
            else:
                key.click()
            time.sleep(0.3)
        key.press('esc')

    key.moveTo(10, 10) # move the mouse out of the way
    print("")
    return

def itemExpired():
# When an item expired
    # print("* 有物品到期, 已按下红叉 *")
    print("* 已按下紅叉 *")
    crossPos = gui.locateOnScreen('scr/cross.png', confidence=0.89)
    if crossPos == None:
        print('** 異常情況(crossPos == None) **')
    else:
        mousePos = gui.center(crossPos)
        key.click(mousePos[0], mousePos[1])
    time.sleep(1)
    return

def pressButton(buttonPos):
# Press the buttonPos button
    mousePos = gui.center(buttonPos)
    key.click(mousePos[0], mousePos[1])
    # time.sleep(1)
    return

def accessDeny():
# Basically an infinite loop to prevent access
    while True:
        time.sleep(1E6)

def pauseFlagFlip():
# The function that flips the pauseFlag
    global pauseFlag
    pauseFlag = not pauseFlag
    if pauseFlag:
        playsound('./scr/pauseOn.mp3')
    else:
        playsound('./scr/pauseOff.mp3')
    return

def setWindow(enableRestart, name, pwd):
# Search and front the game window
    trList = gw.getWindowsWithTitle("Tales Runner")
    if len(trList) != 0:
        frontWindow(trList[0])
    else:
        print("\n** 找不到 Tales Runner 視窗 **\n")
        restartSequence(enableRestart, name, pwd)
    return

def frontWindow(win32Window):
# simplify the fronting window process
# win32Window has to be a Win32Window object returned by pygetwindow.getWindowsWithTitle()
    try: # has to handle some special cases
        win32Window.restore()
        win32Window.activate()
    except gw.PyGetWindowException:
        keyboard.send("alt+tab")
        frontWindow(win32Window) # recursively repeat if the issue still exist
    return

def restartSequence(enableRestart, name, pwd):
# This function is a sequence to restart the game

    trList = gw.getWindowsWithTitle("Tales Runner")
    if len(trList) != 0:
        hwnd = trList[0] # not a real hwnd but a Win32Window object
        while len(trList)  != 0:
            print("\n* 嘗試重新啟動遊戲")
            frontWindow(hwnd) # Front the game window
            time.sleep(0.5)
            keyboard.send("alt+f4") # Force close
            time.sleep(9) # nas to wait a few seconds because force close has delay
            trList = gw.getWindowsWithTitle("Tales Runner")
    else:
        print("\n* 嘗試啟動遊戲")
        time.sleep(1)

    while enableRestart and (len(trList) == 0):
        
        # win+r
        print("* 開啟「執行」")
        keyboard.send('win+r')
        time.sleep(1)

        # Type "talesrunner"
        print("* 輸入 talesrunner 並按 Enter")
        keyboard.write("talesrunner", delay=0.05)
        time.sleep(0.05)
        key.press('enter')
        print("* 等待20秒 *")
        time.sleep(20)

        # Press "enter" to start game
        print("* 按 15 次 Enter")
        for _ in range(15):
            key.press('enter')
            time.sleep(0.5)
        
        specialCase = False
        print("* 等待50秒")
        for _ in range(50):
            time.sleep(1)
            specialWindowList = gw.getWindowsWithTitle("TalesRunner")
            if len(specialWindowList) != 0:
                specialCase = True
                break

        if specialCase: # error caused by zoom-in
            print("* 解析度縮放導致的特定錯誤，重新執行上述步驟")
            frontWindow(specialWindowList[0])
            key.press('enter')
            time.sleep(1)
            # win+r
            keyboard.send('win+r')
            time.sleep(1)

            # Type "talesrunner"
            keyboard.write("talesrunner", delay=0.07)
            time.sleep(0.5)
            key.press('enter')
            time.sleep(20)

            # Press "enter" to start game
            for _ in range(15):
                key.press('enter')
                time.sleep(0.5)
            
            time.sleep(40)
        
        trList = gw.getWindowsWithTitle("Tales Runner")
        if len(trList) != 0: # game is launched
            frontWindow(trList[0])

            # Enter account info
            print("* 輸入帳號資訊並按 Enter")
            keyboard.write(name, delay=0.07)
            time.sleep(0.3)

            key.press('tab')
            
            keyboard.write(pwd, delay=0.07)
            time.sleep(0.3)

            key.press('enter')
            time.sleep(1)

            # Hit esc for 20 times
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
                key.press("enter")
                key.press("esc")

    if not enableRestart:
        print("** 未啟用重新啟動功能，關閉遊戲並停止運作 **")
        accessDeny()

    else:
        print("* 重新啟動 Tales Runner 的步驟已執行完畢 *")
        trList = gw.getWindowsWithTitle("Tales Runner")
        if len(trList) != 0:
            frontWindow(trList[0])
    return

def mainLoop(infoList):
# main function

    # disable the failsafe
    key.FAILSAFE = False 
    gui.FAILSAFE = False

    key.PAUSE = 0.02 # PyDirectInput PAUSE parameter, 0.01 might be too low
    # timeLimit = 1E6  # Continuous running time
    timeLimit = int(infoList[3])

    if True: # just so I can collapse these initialization
        # Hotkey initialization
        global pauseFlag # Global pause flag, True = Pause program
        pauseFlag = False
        global_hotkeys.register_hotkey("control + f12", pauseFlagFlip, None, False, None) 
        global_hotkeys.start_checking_hotkeys() # Start listening to the hot key

        # Read user account info from the infoList
        usrName = infoList[0]
        usrPwd  = infoList[1]
        if usrName != '-1' and usrPwd != '-1':
            print("\n** 已啟用自動重新啟動功能\n** 請確保遊戲目錄已新增至環境變數 PATH 中")
            print("** 帳號: " + usrName)
            print("** 密碼: " + usrPwd)
            print("** 若輸入錯誤，請關閉本程式並修改設定檔")
            enableRestart = True
            
        else:
            print("\n** 未辨識到有效的使用者名稱與密碼，停用重新啟動功能 **\n")
            enableRestart = False
            
        # Read user keyboard config
        keyConfig = infoList[2]
        # keyConfig = control

    time0 = time.time() # Program start time

    print("\n* 開始執行 *")
    raceCount = 0
    failTime  = 0
    inRoomCount = 0

    while True:
        currTime = time.time()

        if pauseFlag:
            print("\n** 暫停中，再次按下 Ctrl + F12 即可解除暫停 **")
            while pauseFlag:
                time.sleep(0.1)
            print("** 已解除暫停 **\n")
            continue

        lobbyPos = gui.locateOnScreen('./scr/lobby.png',confidence=0.89)
        readyPos = gui.locateOnScreen('./scr/ready.png',confidence=0.89)
        waitPos  = gui.locateOnScreen('./scr/wait.png',confidence=0.89)
        startPos = gui.locateOnScreen('./scr/start.png',confidence=0.89)
        racePos  = gui.locateOnScreen('./scr/racing.png',confidence=0.89)
        race1Pos = gui.locateOnScreen('./scr/racing1.png',confidence=0.89)
        offlinePos = gui.locateOnScreen('./scr/offline.png',confidence=0.89)
        
        # if pauseFlag:
        #     print("\n** 暂停中, 再次按下 ctrl + f12 解除暂停 **")
        #     while pauseFlag:
        #         time.sleep(0.1)
        #     print("** 暂停已解除 **\n")
        #     continue

        clearPrompt()
        setWindow(enableRestart, usrName, usrPwd)

        # elif (racePos != None or race1Pos != None):
        if (racePos != None or race1Pos != None):
        # Check if in a race
            stateRacing(keyConfig)
            raceCount += 1
            print("* 跑圖完成次數:", raceCount, "*")
            inRoomCount = 0
            failTime = 0

        elif (lobbyPos != None):
        # Check if in the lobby
            stateLobby(lobbyPos)
            inRoomCount = 0
            failTime = 0

        elif (waitPos != None):
        # Check if is waiting
            # time.sleep(1)
            # Already in ready, do nothing
            inRoomCount += 1
            failTime = 0

        elif (readyPos != None):
        # Check if is not ready
            # time.sleep(1)
            if correctMap(): # check if the map is correct
                pressButton(buttonPos=readyPos)
                readyPos = gui.locateOnScreen('./scr/ready.png',confidence=0.89)
                if readyPos != None: # In case something blocked the button
                    key.press('f9')
                inRoomCount += 1
                failTime = 0
            else:
                print("* 偵測到地圖已被變更 *")
                quitRoom()

        elif (startPos != None):
        # Check if is room owner
            # time.sleep(1)
            if correctMap():
                pressButton(buttonPos=startPos)
                key.press('f10') # In case something blocked the button
                inRoomCount += 1
                failTime = 0
            else:
                print("* 地圖可能已被變更，重新選擇地圖 *")
                selectMap()

        else:
        # No element detected
            failTime += 1
            inRoomCount = 0
            # time.sleep(1)

        if inRoomCount > 120:
            print("* 房間長時間未開始 *")
            quitRoom()
            inRoomCount = 0
            failTime = 0

        # print("failTime: ", failTime)
        if failTime == 30: # No activity for too long
            print("\n** 長時間未辨識到關鍵圖案，請確保遊戲畫面位於最上層 **\n")
        elif failTime == 350:
            if enableRestart:
                print("\n** 辨識失敗次數超過"+str(failTime)+"次, 嘗試重新啟動遊戲 **\n")
                restartSequence(enableRestart=enableRestart, name=usrName, pwd=usrPwd)
                failTime = 0
                time0 += 420
            else:
                print("\n** 辨識失敗次數超過"+str(failTime)+"次 **\n")

        if (currTime - time0) > timeLimit:
            print("* 程式已執行" + str(timeLimit) + "秒，若要繼續使用，請重新啟動本程式 *")
            quitRoom()
            accessDeny()

        if offlinePos != None:
            print("\n** 偵測到已斷線 **")
            setWindow(enableRestart=enableRestart, name=usrName, pwd=usrPwd)
            time.sleep(3)
            restartSequence(enableRestart=enableRestart, name=usrName, pwd=usrPwd)
            failTime = 0
            time0 += 120
    return 0

def init():
# Program initialization:
# 1) check autoPWD
# 2) verify user's cdkey
# 3) return user's customized keyboard config and map selection
    try:
        print("* 嘗試尋找並開啟 autoPWD.txt")
        file = open("autoPWD.txt", 'r')
        print("* 成功開啟 autoPWD.txt")
        
    except FileNotFoundError:
        try:
            file = open("autoPWD.txt.txt", 'r')
            print("* 成功開啟 autoPWD.txt.txt")
            
        except FileNotFoundError:
            print("\n** 找不到 autoPWD.txt **\n")
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
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取前進鍵\t: " + temp)
                    forward = temp
                else:
                    print("** 無效的前進鍵設定，使用預設按鍵: " + forward)
            except IndexError:
                continue

        # control - backward
        elif s.find("backward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取後退鍵\t: " + temp)
                    backward = temp
                else:
                    print("** 無效的後退鍵設定，使用預設按鍵: " + backward)
            except IndexError:
                continue

        # control - leftward
        elif s.find("leftward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取左轉鍵\t: " + temp)
                    leftward = temp
                else:
                    print("** 無效的左轉鍵設定，使用預設按鍵: " + leftward)
            except IndexError:
                continue

        # control - rightward
        elif s.find("rightward") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取右轉鍵\t: " + temp)
                    rightward = temp
                else:
                    print("** 無效的右轉鍵設定，使用預設按鍵: " + rightward)
            except IndexError:
                continue

        # control - jump
        elif s.find("jump") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取跳躍鍵\t: " + temp)
                    jump = temp
                else:
                    print("** 無效的跳躍鍵設定，使用預設按鍵: " + jump)
            except IndexError:
                continue

        elif s.find("item2") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取道具鍵2\t: " + temp)
                    item2 = temp
                else:
                    print("** 無效的道具鍵 2 設定，使用預設按鍵: " + item2)
            except IndexError:
                continue

        elif s.find("item3") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取道具鍵3\t: " + temp)
                    item3 = temp
                else:
                    print("** 無效的道具鍵 3 設定，使用預設按鍵: " + item3)
            except IndexError:
                continue

        # control - item
        elif s.find("item") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取道具鍵\t: " + temp)
                    item = temp
                else:
                    print("** 無效的道具鍵設定，使用預設按鍵: " + item)
            except IndexError:
                continue

        # control - sprint
        elif s.find("sprint") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp in key.KEYBOARD_MAPPING:
                    print("* 已讀取衝刺鍵\t: " + temp)
                    sprint = temp
                else:
                    print("** 無效的衝刺鍵設定，使用預設按鍵: " + sprint)
            except IndexError:
                continue

        # control - sprint
        elif s.find("runtime") != -1:
            try:
                temp = s.split('=')[1].replace(" ", "").lower() # trim spaces
                if temp.isnumeric():
                    print("* 已讀取執行時間\t: " + temp + "秒")
                    runtime = temp
                else:
                    print("** 無效的執行時間，使用預設時間: " + runtime + "秒")
            except IndexError:
                continue

    control = [forward, backward, leftward, rightward, jump, item, sprint, item2, item3]
    return [usrName, usrPWD, control, runtime]

def __main__():
    welcomeSequence()
    infoList = init()
    mainLoop(infoList)

ocr = dd.DdddOcr(beta=True, show_ad=False)
__main__() #_#

