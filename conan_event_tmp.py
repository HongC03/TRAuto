"""Template for a simple Tales Runner automation task.

Copy this file, set TARGET_IMAGE_NAME and the desired action, then implement any
extra behavior in run_task_step(). Keep each step short so GameSupervisor can
check the game and handle OCR frequently.
"""

import time

import keyboard

from game_supervisor import BASE_DIR, GameSupervisor
from utils import triggerIfDetected

ACTION = "click"  # "click" or "key"
KEYBOARD_KEY = None  # Example: "f9" when ACTION == "key"
MATCH_CONFIDENCE = 0.89
LOOP_INTERVAL = 0.3


def run_task_step():
    """Perform one short task step and return whether it was triggered."""
    triggerIfDetected(
        BASE_DIR / "scr" / "conan_event_tmp" / "blue_button.png",
        action=ACTION,
        keyboard_key=KEYBOARD_KEY,
        confidence=MATCH_CONFIDENCE,
    )
    triggerIfDetected(
        BASE_DIR / "scr" / "conan_event_tmp" / "then.png",
        action=ACTION,
        keyboard_key=KEYBOARD_KEY,
        confidence=MATCH_CONFIDENCE,
    )


def main():
    while True:
        if keyboard.is_pressed("f12"):
            print("偵測到停止訊號，程式結束。")
            break
        run_task_step()

        time.sleep(LOOP_INTERVAL)




if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* 任務已停止 *")
