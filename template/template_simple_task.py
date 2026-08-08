"""Template for a simple Tales Runner automation task.

Copy this file, set TARGET_IMAGE_NAME and the desired action, then implement any
extra behavior in run_task_step(). Keep each step short so GameSupervisor can
check the game and handle OCR frequently.
"""

import time

from game_supervisor import BASE_DIR, GameSupervisor
from utils import triggerIfDetected


TARGET_IMAGE_NAME = "replace_with_your_button.png"
ACTION = "click"  # "click" or "key"
KEYBOARD_KEY = None  # Example: "f9" when ACTION == "key"
MATCH_CONFIDENCE = 0.89
LOOP_INTERVAL = 1


def target_image_path():
    return BASE_DIR / "scr" / TARGET_IMAGE_NAME


def validate_configuration():
    image_path = target_image_path()
    if not image_path.is_file():
        raise FileNotFoundError(
            f"找不到任務圖片: {image_path}。"
            "請將圖片新增至 scr/ 並更新 TARGET_IMAGE_NAME。"
        )
    if ACTION not in {"click", "key"}:
        raise ValueError("ACTION 必須為 'click' 或 'key'")
    if ACTION == "key" and not KEYBOARD_KEY:
        raise ValueError("當 ACTION 為 'key' 時，必須設定 KEYBOARD_KEY")


def run_task_step():
    """Perform one short task step and return whether it was triggered."""
    triggered = triggerIfDetected(
        target_image_path(),
        action=ACTION,
        keyboard_key=KEYBOARD_KEY,
        confidence=MATCH_CONFIDENCE,
    )
    if triggered:
        print(f"* 已觸發 {TARGET_IMAGE_NAME} 的任務動作 *")
    return triggered


def main():
    validate_configuration()
    supervisor = GameSupervisor.from_config()

    while True:
        game_state = supervisor.ensure_ready()
        if game_state == "ready":
            run_task_step()
        else:
            print(f"* 遊戲狀態為 {game_state}，任務已暫停 *")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* 任務已停止 *")
