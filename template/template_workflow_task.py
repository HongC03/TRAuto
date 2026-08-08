"""Template for a multi-step Tales Runner automation workflow.

Copy this file and replace WORKFLOW_STEPS with your own image/action sequence.
Only one step is attempted per loop, allowing GameSupervisor to check game
health, restart when needed, and handle prompt OCR between task actions.
"""

from dataclasses import dataclass
import time

from game_supervisor import BASE_DIR, GameSupervisor
from utils import triggerIfDetected


LOOP_INTERVAL = 1
STEP_COOLDOWN = 1
REPEAT_WORKFLOW = False


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    image_name: str
    action: str = "click"
    keyboard_key: str | None = None
    confidence: float = 0.89

    @property
    def image_path(self):
        return BASE_DIR / "scr" / self.image_name

    def validate(self):
        if not self.image_path.is_file():
            raise FileNotFoundError(
                f"找不到工作流程圖片: {self.image_path}"
            )
        if self.action not in {"click", "key"}:
            raise ValueError(f"{self.name} 的 action 無效: {self.action}")
        if self.action == "key" and not self.keyboard_key:
            raise ValueError(f"步驟 {self.name} 必須設定 keyboard_key")


# Replace these examples with images placed in scr/.
WORKFLOW_STEPS = (
    WorkflowStep(
        name="點擊第一個按鈕",
        image_name="replace_with_first_button.png",
        action="click",
    ),
    WorkflowStep(
        name="為第二個按鈕按下 Enter",
        image_name="replace_with_second_button.png",
        action="key",
        keyboard_key="enter",
    ),
)


class WorkflowTask:
    def __init__(self, steps):
        if not steps:
            raise ValueError("至少需要一個工作流程步驟")
        for step in steps:
            step.validate()

        self.steps = tuple(steps)
        self.current_index = 0

    def reset(self):
        self.current_index = 0
        print("* 工作流程已重設 *")

    def run_next_step(self):
        """Attempt one step and return True when the workflow is complete."""
        step = self.steps[self.current_index]
        triggered = triggerIfDetected(
            step.image_path,
            action=step.action,
            keyboard_key=step.keyboard_key,
            confidence=step.confidence,
        )
        if not triggered:
            return False

        print(f"* 已完成工作流程步驟: {step.name} *")
        self.current_index += 1
        time.sleep(STEP_COOLDOWN)
        return self.current_index == len(self.steps)


def main():
    task = WorkflowTask(WORKFLOW_STEPS)
    supervisor = GameSupervisor.from_config()

    while True:
        game_state = supervisor.ensure_ready()
        if game_state != "ready":
            task.reset()
            time.sleep(LOOP_INTERVAL)
            continue

        if task.run_next_step():
            print("* 工作流程已完成 *")
            if not REPEAT_WORKFLOW:
                return
            task.reset()

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"** {error} **")
    except KeyboardInterrupt:
        print("\n* 工作流程已停止 *")
