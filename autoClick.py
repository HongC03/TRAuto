"""Template for a simple Tales Runner automation task.

Copy this file, set TARGET_IMAGE_NAME and the desired action, then implement any
extra behavior in run_task_step(). Keep each step short so GameSupervisor can
check the game and handle OCR frequently.
"""

import time

import keyboard
import pydirectinput

LOOP_INTERVAL = 0.5

def main():
    while True:
        if keyboard.is_pressed("f12"):
            print("偵測到停止訊號，程式結束。")
            break

        pydirectinput.click()
        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()
